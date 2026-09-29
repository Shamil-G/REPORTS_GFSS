# -*- coding: utf-8 -*-
"""Общий рендерер xlsx-отчётов.

Модуль отчёта описывает только данные - список колонок и текст SQL, - а всё
остальное (стили, шапка, нумерация, итоги, статусы, запуск в потоке) живёт здесь.
Заменяет build_formats / make_header / write_rows / thread_report, которые до
этого копировались в каждый модуль.

build_report() возвращает пару (do_report, thread_report) - тот же контракт, что
у существующих модулей, поэтому model/call_report.py и report_runner.py менять
не нужно.

Многоуровневая шапка задаётся вложенными Group - это прямой аналог дерева
фигурных скобок, которое в PL/SQL передавалось в Rep.SetPageHead.
"""
import datetime
import os
import re
import threading
from dataclasses import dataclass, field

import xlsxwriter

from db.connect import select_2, DEFAULT_PROFILE
from model.manage_reports import set_status_report
from util.logger import log
from util.period import (period_bounds, period_word, split_period, year_start,
                         period_label as _default_period_label)

STATUS_DONE = 2
STATUS_ERROR = 3

TITLE_ROW = 0
CODE_ROW = 1
COLNUM_ROW = 2
HEADER_ROW = 3          # первая строка шапки таблицы

_BIND_RE = re.compile(r':([A-Za-z_]\w*)')

# Подстановки в текстах отчёта. Нужны там, где формулировка официальной
# отчётности зависит от выбранного периода: в PL/SQL период был зашит в
# название ("... по состоянию на Август месяц 2026 года"), а подзаголовок
# всегда читался "в отчетном месяце", потому что других периодов не было.
PERIOD_SLOT = '{period}'            # в name: подставляется "Август месяц 2026 года"
PERIOD_WORD_SLOT = '{period_word}'  # в заголовке колонки: "месяце", "квартале"


@dataclass
class Col:
    """Колонка отчёта. key - алиас колонки в SQL."""
    title: str
    key: str
    kind: str = 'text'        # text | center | int | money | avg | date
    width: int = 14
    # Только для kind='avg'. Без него итог по колонке - обычная сумма, как её
    # считал Rep.SetColSumTotal в PL/SQL: официальная отчётность сверяется с
    # эталоном, поэтому по умолчанию воспроизводим оригинал.
    # С avg_of=(колонка суммы, колонка количества) итог считается верно -
    # sum(числитель)/sum(знаменатель); включать только после согласования с ДАУС.
    avg_of: tuple = None


@dataclass
class Group:
    """Объединяющий заголовок над несколькими колонками. Вложенность любая."""
    title: str
    cols: list = field(default_factory=list)


def _leaves(cols):
    out = []
    for c in cols:
        out.extend(_leaves(c.cols)) if isinstance(c, Group) else out.append(c)
    return out


def _depth(cols):
    return max((1 + _depth(c.cols)) if isinstance(c, Group) else 1 for c in cols)


def _build_formats(workbook):
    return {
        'title': workbook.add_format({
            'align': 'center', 'valign': 'vcenter',
            'font_size': 14, 'bold': True, 'text_wrap': True}),
        'code': workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'font_size': 12, 'bold': True}),
        'period': workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'font_size': 11, 'italic': True}),
        'subtitle': workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'font_size': 11, 'italic': True}),
        'header': workbook.add_format({
            'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 11,
            'border': 1, 'bg_color': '#E0F7FF', 'text_wrap': True}),
        'colnum': workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'font_size': 9,
            'border': 1, 'bg_color': '#E0F7FF'}),
        'text': workbook.add_format({
            'align': 'left', 'valign': 'vcenter', 'border': 1, 'bg_color': '#f2f2f2'}),
        'center': workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#f2f2f2', 'num_format': '@'}),
        'int': workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#f2f2f2', 'num_format': '### ### ##0'}),
        'money': workbook.add_format({
            'align': 'right', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#f2f2f2', 'num_format': '### ### ### ##0.00'}),
        'date': workbook.add_format({
            'align': 'center', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#f2f2f2', 'num_format': 'dd.mm.yyyy'}),
        'total_text': workbook.add_format({
            'bold': True, 'align': 'right', 'valign': 'vcenter',
            'border': 1, 'bg_color': '#E0F7FF'}),
        'total_int': workbook.add_format({
            'bold': True, 'align': 'right', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#E0F7FF', 'num_format': '### ### ##0'}),
        'total_money': workbook.add_format({
            'bold': True, 'align': 'right', 'valign': 'vcenter', 'border': 1,
            'bg_color': '#E0F7FF', 'num_format': '### ### ### ##0.00'}),
        'footnote': workbook.add_format({
            'align': 'left', 'valign': 'top', 'font_size': 9,
            'italic': True, 'text_wrap': True}),
        'sql': workbook.add_format({
            'border': 1, 'align': 'left', 'valign': 'top',
            'fg_color': '#FAFAD7', 'text_wrap': True}),
    }


# 'avg' печатается как деньги; отдельный формат не нужен
_CELL_FORMAT = {'text': 'text', 'center': 'center', 'int': 'int',
                'money': 'money', 'avg': 'money', 'date': 'date'}
_NUMERIC = ('int', 'money', 'avg')


def _merge(ws, r1, c1, r2, c2, text, fmt):
    """merge_range отказывается объединять одну ячейку - пишем напрямую."""
    if r1 == r2 and c1 == c2:
        ws.write(r1, c1, text, fmt)
    else:
        ws.merge_range(r1, c1, r2, c2, text, fmt)


def _draw_header_tree(ws, fmt, cols, row, col, rows_left, word=''):
    """Рекурсивно рисует дерево заголовков. Возвращает занятое число колонок."""
    used = 0
    for c in cols:
        title = c.title.replace(PERIOD_WORD_SLOT, word)
        if isinstance(c, Group):
            span = len(_leaves(c.cols))
            _merge(ws, row, col + used, row, col + used + span - 1,
                   title, fmt['header'])
            _draw_header_tree(ws, fmt, c.cols, row + 1, col + used,
                              rows_left - 1, word)
            used += span
        else:
            # лист тянется вниз до конца шапки
            _merge(ws, row, col + used, row + rows_left - 1, col + used,
                   title, fmt['header'])
            used += 1
    return used


def _used_binds(stmt, candidates):
    """Только те значения, что реально упомянуты в тексте запроса.

    Oracle ругается на бинд, которого нет в SQL, поэтому лишние отбрасываем:
    модуль отчёта не обязан объявлять, какие из параметров формы он использует.
    """
    names = set(_BIND_RE.findall(stmt))
    return {k: v for k, v in candidates.items() if k in names}


def build_report(*, code, name, columns, stmt,
                 profile=DEFAULT_PROFILE,
                 period=False,
                 totals=False,
                 footnote=None,
                 blank_zero=False,
                 period_label=None,   # см. make_period_label() в util/period.py
                 sheet_name='Отчёт',
                 max_rows=500_000):
    """Собирает отчёт из описания. Возвращает (do_report, thread_report)."""
    # формулировка подписи периода у каждого отчёта своя, по умолчанию - общая
    label_of = period_label or _default_period_label
    leaves = _leaves(columns)
    header_depth = _depth(columns)
    data_row0 = HEADER_ROW + header_depth
    total_cols = len(leaves) + 1          # +1 на колонку "№"

    def _make_header(ws, title, subtitle, word):
        ws.set_row(TITLE_ROW, 30)
        ws.set_row(CODE_ROW, 18)
        ws.set_row(COLNUM_ROW, 14)
        for r in range(HEADER_ROW, data_row0):
            ws.set_row(r, 32)

        _merge(ws, TITLE_ROW, 0, TITLE_ROW, total_cols - 1, title, fmt['title'])
        ws.write(CODE_ROW, 0, code, fmt['code'])
        # Справа в этой же строке будет дата формирования - её пишет
        # _write_stamp() уже после выгрузки данных, когда известно время
        # окончания. Поэтому подпись периода стоит слева, рядом с кодом.
        if subtitle:
            ws.write(CODE_ROW, 1, subtitle, fmt['subtitle'])

        ws.set_column(0, 0, 6)
        for i, c in enumerate(leaves, start=1):
            ws.set_column(i, i, c.width)

        for i in range(total_cols):
            ws.write(COLNUM_ROW, i, str(i + 1), fmt['colnum'])

        _merge(ws, HEADER_ROW, 0, data_row0 - 1, 0, '№', fmt['header'])
        _draw_header_tree(ws, fmt, columns, HEADER_ROW, 1, header_depth, word)

        ws.freeze_panes(data_row0, 0)
        ws.repeat_rows(HEADER_ROW, data_row0 - 1)

    def _write_cell(ws, row, col, value, kind):
        f = fmt[_CELL_FORMAT[kind]]
        if value is None or (blank_zero and kind in _NUMERIC and not value):
            ws.write_blank(row, col, None, f)
        elif kind in _NUMERIC:
            ws.write_number(row, col, float(value), f)
        elif kind == 'date':
            ws.write_datetime(row, col, value, f)
        else:
            ws.write_string(row, col, str(value), f)

    def _write_totals(ws, row, records):
        # подпись растягивается по ведущим нечисловым колонкам ("№", "Вид риска")
        last_label_col = next((i for i, c in enumerate(leaves, start=1)
                               if c.kind in _NUMERIC), total_cols) - 1
        _merge(ws, row, 0, row, last_label_col, 'Итого', fmt['total_text'])
        for i, c in enumerate(leaves, start=1):
            if i <= last_label_col:
                continue
            if c.kind == 'avg' and c.avg_of:
                # арифметически верный итог: сумма числителей / сумма знаменателей
                num = sum(float(r.get(c.avg_of[0]) or 0) for r in records)
                den = sum(float(r.get(c.avg_of[1]) or 0) for r in records)
                value = num / den if den else 0
                ws.write_number(row, i, value, fmt['total_money'])
            elif c.kind in ('int', 'money', 'avg'):
                # 'avg' без avg_of складывается как есть - так делал
                # Rep.SetColSumTotal; см. комментарий к Col.avg_of
                value = sum(float(r.get(c.key) or 0) for r in records)
                ws.write_number(row, i, value,
                                fmt['total_int'] if c.kind == 'int'
                                else fmt['total_money'])
            else:
                ws.write_blank(row, i, None, fmt['total_text'])

    def _write_stamp(sheets, start_time):
        """Дата и время формирования - справа в строке с кодом отчёта.

        Формулировка и место как в остальных отчётах проекта (dsr_01,
        rep_aktuar_0702_01 и др.). Пишется в самом конце: раньше время
        окончания неизвестно.
        """
        stop_time = datetime.datetime.now()
        stamp = (f'Дата формирования: {stop_time:%d.%m.%Y} '
                 f'({start_time:%H:%M:%S} - {stop_time:%H:%M:%S})')
        for ws in sheets:
            ws.write(CODE_ROW, total_cols - 1, stamp, fmt['period'])

    def _write_sql_sheet(workbook):
        sheet = workbook.add_worksheet('SQL')
        sheet.set_column(0, 8, 14)
        lines = stmt.splitlines()
        sheet.merge_range(0, 0, max(len(lines) - 1, 1), 8, stmt, fmt['sql'])

    def _bind_values(params):
        """Кандидаты в бинды: параметры формы плюс границы периода."""
        candidates = {k: (v if v != '' else None)
                      for k, v in params.items() if k != 'file_name'}
        title, subtitle, word = name, '', ''
        if period:
            rep_year = params['rep_year']
            # одно поле формы "период" несёт и тип, и номер: "2.3" = III квартал
            date_type, date_start = split_period(params['period'])
            d_from, d_to = period_bounds(rep_year, date_type, date_start)
            candidates.update(d_from=d_from, d_to=d_to,
                              y_from=year_start(rep_year))
            phrase = label_of(rep_year, date_type, date_start)
            word = period_word(date_type)
            # период либо встроен в название (как было в PL/SQL), либо
            # выводится отдельной подписью справа
            if PERIOD_SLOT in name:
                title = name.replace(PERIOD_SLOT, phrase)
            else:
                subtitle = f'За период: {phrase}'
        return _used_binds(stmt, candidates), title, subtitle, word

    fmt = None          # заполняется внутри do_report, живёт в замыкании

    def do_report(file_name: str, **params):
        nonlocal fmt

        if os.path.isfile(file_name):
            log.info(f'Отчёт уже существует {file_name}')
            return file_name

        start_time = datetime.datetime.now()
        log.info(f'DO REPORT. START {code}. PARAMS: {params}, FILE: {file_name}')

        try:
            binds, title, subtitle, word = _bind_values(params)
            log.info(f'REPORT: {code}. BINDS: {binds}')

            # raise_on_error=True: пустой результат не должен маскировать ошибку
            # запроса, иначе отчёт тихо запишется пустым и получит статус "готов"
            records = select_2(stmt, binds, profile=profile, raise_on_error=True)

            with xlsxwriter.Workbook(file_name) as workbook:
                fmt = _build_formats(workbook)

                sheets = []
                row = data_row0
                sheet = None
                for n, record in enumerate(records):
                    if n % max_rows == 0:
                        suffix = f' {len(sheets) + 1}' if len(records) > max_rows else ''
                        sheet = workbook.add_worksheet(f'{sheet_name}{suffix}')
                        _make_header(sheet, title, subtitle, word)
                        sheets.append(sheet)
                        row = data_row0
                    sheet.write_number(row, 0, n + 1, fmt['center'])
                    for i, c in enumerate(leaves, start=1):
                        _write_cell(sheet, row, i, record.get(c.key), c.kind)
                    row += 1

                if not sheets:
                    sheet = workbook.add_worksheet(sheet_name)
                    _make_header(sheet, title, subtitle, word)
                    sheet.write(data_row0, 0, 'Нет данных для отображения')
                    sheets.append(sheet)
                    row = data_row0 + 1

                if totals and records:
                    _write_totals(sheets[-1], row, records)
                    row += 1

                if footnote:
                    sheets[-1].merge_range(row + 1, 0, row + 2, total_cols - 1,
                                           footnote, fmt['footnote'])

                _write_stamp(sheets, start_time)
                _write_sql_sheet(workbook)
                sheets[0].activate()

            set_status_report(file_name, STATUS_DONE)
            stop_time = datetime.datetime.now()
            log.info(f'REPORT: {code}. Формирование {file_name} завершено '
                     f'({start_time:%H:%M:%S} - {stop_time:%H:%M:%S}), '
                     f'записей: {len(records)}')
            return file_name

        except Exception:
            log.exception(f'REPORT: {code}. Ошибка формирования {file_name}')
            try:
                set_status_report(file_name, STATUS_ERROR)
            except Exception:
                log.exception('Не удалось выставить статус ошибки')
            if os.path.isfile(file_name):
                try:
                    os.remove(file_name)   # чтобы битый файл не считался готовым
                except OSError:
                    pass
            raise

    def thread_report(file_name: str, **params):
        log.info(f'THREAD REPORT. {code} -> {file_name}, params: {params}')
        threading.Thread(target=do_report, args=(file_name,), kwargs=params,
                         daemon=True).start()
        return {"status": 1, "file_path": file_name}

    return do_report, thread_report
