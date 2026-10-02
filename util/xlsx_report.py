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

def _parse_date(value):
    """Дата из поля формы: 2026-01-31 (input type=date) или 31.01.2026."""
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    text = str(value).strip()[:10]
    fmt = '%Y-%m-%d' if text[4:5] == '-' else '%d.%m.%Y'
    return datetime.datetime.strptime(text, fmt).date()


def _eom(d):
    """Последний день месяца (last_day)."""
    nxt = (d.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return nxt - datetime.timedelta(days=1)


parse_date = _parse_date      # для проверок check_params в модулях отчётов

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
    # Выравнивание значений: left | center | right. None - по kind (текст влево,
    # числа вправо). Меняет только вид: число остаётся числом и суммируется.
    align: str = None
    # Только для kind='avg'. Без него итог по колонке - обычная сумма, как её
    # считал Rep.SetColSumTotal в PL/SQL: официальная отчётность сверяется с
    # эталоном, поэтому по умолчанию воспроизводим оригинал.
    # С avg_of=(колонка суммы, колонка количества) итог считается верно -
    # sum(числитель)/sum(знаменатель); включать только после согласования с ДАУС.
    avg_of: tuple = None
    # Вид значения по строкам: имя колонки SQL, где у каждой строки лежит свой
    # kind ('int' / 'money'). Нужен отчётам-карточкам, где в одной колонке
    # идут и человеки, и тенге (форма 18 REP_MINTRUD). Пусто в строке - kind.
    kind_of: str = None
    # Печатать ли итог по колонке. В PL/SQL итог включался отдельно для каждой
    # колонки (`SetColSumTotal(N)`): часть отчётов суммирует не все числа.
    total: bool = True


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


_FORMATS = {
    'title': {
        'align': 'center', 'valign': 'vcenter',
        'font_size': 14, 'bold': True, 'text_wrap': True},
    'code': {
        'align': 'left', 'valign': 'vcenter', 'font_size': 12, 'bold': True},
    'period': {
        'align': 'right', 'valign': 'vcenter', 'font_size': 11, 'italic': True},
    'subtitle': {
        'align': 'left', 'valign': 'vcenter', 'font_size': 11, 'italic': True},
    'header': {
        'bold': True, 'align': 'center', 'valign': 'vcenter', 'font_size': 11,
        'border': 1, 'bg_color': '#E0F7FF', 'text_wrap': True},
    'colnum': {
        'align': 'center', 'valign': 'vcenter', 'font_size': 9,
        'border': 1, 'bg_color': '#E0F7FF'},
    'text': {
        'align': 'left', 'valign': 'vcenter', 'border': 1, 'bg_color': '#f2f2f2'},
    'center': {
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#f2f2f2', 'num_format': '@'},
    'int': {
        'align': 'right', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#f2f2f2', 'num_format': '### ### ##0'},
    'money': {
        'align': 'right', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#f2f2f2', 'num_format': '### ### ### ##0.00'},
    'date': {
        'align': 'center', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#f2f2f2', 'num_format': 'dd.mm.yyyy'},
    'total_text': {
        'bold': True, 'align': 'right', 'valign': 'vcenter',
        'border': 1, 'bg_color': '#E0F7FF'},
    'total_int': {
        'bold': True, 'align': 'right', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#E0F7FF', 'num_format': '### ### ##0'},
    'total_money': {
        'bold': True, 'align': 'right', 'valign': 'vcenter', 'border': 1,
        'bg_color': '#E0F7FF', 'num_format': '### ### ### ##0.00'},
    'footnote': {
        'align': 'left', 'valign': 'top', 'font_size': 9,
        'italic': True, 'text_wrap': True},
    'sql': {
        'border': 1, 'align': 'left', 'valign': 'top',
        'fg_color': '#FAFAD7', 'text_wrap': True},
}

# 'avg' печатается как деньги; отдельный формат не нужен
_CELL_FORMAT = {'text': 'text', 'center': 'center', 'int': 'int',
                'money': 'money', 'avg': 'money', 'date': 'date'}
_TOTAL_FORMAT = {'int': 'total_int', 'money': 'total_money',
                 'avg': 'total_money'}
_NUMERIC = ('int', 'money', 'avg')


def _build_formats(workbook, leaves):
    """Общие форматы плюс свои у колонок с явным align.

    Формат колонки - копия формата её kind с другим выравниванием, ключ -
    ('cell', номер колонки) и ('total', номер колонки) для строки итогов.
    """
    fmt = {k: workbook.add_format(v) for k, v in _FORMATS.items()}
    for i, c in enumerate(leaves, start=1):
        if not c.align:
            continue
        fmt['cell', i] = workbook.add_format(
            {**_FORMATS[_CELL_FORMAT[c.kind]], 'align': c.align})
        if c.kind in _TOTAL_FORMAT:
            fmt['total', i] = workbook.add_format(
                {**_FORMATS[_TOTAL_FORMAT[c.kind]], 'align': c.align})
    return fmt


# Высота строк названия и шапки. Excel не подбирает высоту под объединённые
# ячейки, а xlsxwriter не умеет мерить текст, поэтому число строк переноса
# оцениваем сами по ширине колонок. Константы подобраны по Calibri bold 11pt
# (шрифт xlsxwriter по умолчанию) с небольшим запасом: лучше лишний отступ,
# чем обрезанное слово.
_PX_PER_WIDTH = 7       # пикселей на единицу ширины колонки (set_column)
_PX_PER_CHAR = 7.0      # средняя ширина символа bold 11pt
_CELL_PAD_PX = 6        # поля ячейки слева и справа
_LINE_PT = 15           # высота строки текста 11pt, в пунктах
_ROW_PAD_PT = 4         # поля ячейки сверху и снизу


def _col_px(width):
    return int(width * _PX_PER_WIDTH + 5)


def _wrapped_lines(text, width_px, font_size):
    """Сколько строк займёт текст при переносе по словам, как в Excel.

    Явный '\\n' в тексте - принудительный перенос: им можно разбить заголовок
    так, как нужно, а не как решит Excel.
    """
    per_line = max(1, int((width_px - _CELL_PAD_PX)
                          / (_PX_PER_CHAR * font_size / 11)))
    total = 0
    for para in str(text).split('\n'):
        lines, cur = 1, 0
        for word in para.split():
            if cur and cur + 1 + len(word) <= per_line:
                cur += 1 + len(word)
                continue
            if cur:
                lines += 1
            lines += (len(word) - 1) // per_line   # слово длиннее строки режется
            cur = len(word) % per_line or per_line
        total += lines
    return total


def _text_height(text, width_px, font_size=11):
    return (_wrapped_lines(text, width_px, font_size)
            * _LINE_PT * font_size / 11 + _ROW_PAD_PT)


def _header_heights(columns, depth, widths, word):
    """Высоты строк шапки. widths - ширины листовых колонок по порядку.

    Заголовок группы занимает одну строку - она должна вместить его целиком.
    Лист тянется до низа шапки: если суммы строк под ним не хватает, недостача
    раскладывается поровну на эти строки.
    """
    need = [_LINE_PT + _ROW_PAD_PT] * depth
    tall = []           # (первая строка, нужная высота) у листьев выше низа

    def walk(cols, row, col):
        for c in cols:
            title = c.title.replace(PERIOD_WORD_SLOT, word)
            if isinstance(c, Group):
                span = len(_leaves(c.cols))
                px = sum(_col_px(w) for w in widths[col:col + span])
                need[row] = max(need[row], _text_height(title, px))
                walk(c.cols, row + 1, col)
                col += span
            else:
                h = _text_height(title, _col_px(widths[col]))
                if row == depth - 1:
                    need[row] = max(need[row], h)
                else:
                    tall.append((row, h))
                col += 1

    walk(columns, 0, 0)
    for row, h in tall:
        short = h - sum(need[row:])
        if short > 0:
            for r in range(row, depth):
                need[r] += short / (depth - row)
    return need


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
                 date_range=False,    # период "с date_first по date_second" вместо года + периода
                 max_days=None,       # date_range: наибольшая разница дат, иначе отказ
                 check_params=None,   # функция(params): проверка ввода, при ошибке ValueError
                 title_params=(),     # параметры формы, значение которых печатается в названии
                 title_sql=None,      # запрос реквизитов для названия: колонки -> {колонка}
                 title_not_found='Данные не найдены',   # текст ошибки, если title_sql пуст
                 totals=False,
                 footnote=None,
                 blank_zero=False,
                 period_label=None,   # см. make_period_label() в util/period.py
                 text_params=None,    # {ключ_параметра: {значение: фраза}}
                 title_height=None,
                 header_heights=None,
                 sheet_name='Отчёт',
                 max_rows=500_000):
    """Собирает отчёт из описания. Возвращает (do_report, thread_report).

    Высота строки названия и строк шапки по умолчанию оценивается по длине
    текста и ширине колонок. Если оценка промахнулась, её можно задать руками:
    title_height - в пунктах, header_heights - список по строкам шапки сверху
    вниз, None в списке оставляет строку на автоподборе. Например, для
    двухуровневой шапки header_heights=[None, 60].

    date_range - отчёты, у которых в AIS период задавался двумя датами. В запрос
    уходят :d_from, :d_to (исключительная, на сутки позже date_second) и :y_from
    (первое января года начала периода), так что
    условие то же, что у периодических отчётов: `>= :d_from and < :d_to`.
    В name место для периода - '{period}', выводится "01.01.2026 по 31.01.2026";
    если формулировка оригинала печатает даты порознь ("Период с: ... по: ..."),
    в name ставятся '{date_from}' и '{date_to}' ('{date_from_dash}' и
    '{date_to_dash}' - то же в формате dd-mm-yyyy; '{date_to_eom}' - последний
    день месяца даты «по», для отчётов с `p_EndDate := last_day(p_EndDate)`).
    max_days - ограничение оригинала на длину периода (разница дат, как в PL/SQL
    `(pDateTo - pDateFrom) > 366`): больше - отчёт не строится.

    check_params - проверки введённых значений, которые в PL/SQL делал сам отчёт
    (`raise_application_error(-20000, 'Введен неправильный БИН!')`). Вызывается
    до запроса; текст ValueError попадает в журнал.

    stmt - текст запроса либо функция(params) -> текст запроса.

    title_sql - запрос (те же :бинды формы), одна строка которого даёт реквизиты
    для названия: каждая колонка подставляется в name как '{колонка}' (ФИО и СИК
    получателя в справке). Нет строки - ValueError с текстом title_not_found.

    В name можно поставить '{today}' - дата формирования отчёта (dd.mm.yyyy).

    title_params - имена параметров формы, чьё введённое значение печатается в
    названии как есть (БИН, ИИН, код региона): в name место помечено '{имя}'.

    text_params - подстановка в name текста, зависящего не от периода, а от
    обычного параметра формы (например, выбранный вид выплаты меняет
    официальную формулировку названия, как в app_50/51/55). Ключ - имя
    параметра (как передаётся в do_report/thread_report), значение - словарь
    "значение параметра -> фраза". В name соответствующее место помечается
    '{имя_параметра}', как {period} для периода.
    """
    # формулировка подписи периода у каждого отчёта своя, по умолчанию - общая
    label_of = period_label or _default_period_label
    leaves = _leaves(columns)
    header_depth = _depth(columns)
    data_row0 = HEADER_ROW + header_depth
    total_cols = len(leaves) + 1          # +1 на колонку "№"

    if header_heights is not None and len(header_heights) != header_depth:
        raise ValueError(f'{code}: header_heights - {len(header_heights)} '
                         f'знач., а строк в шапке {header_depth}')
    widths = [c.width for c in leaves]
    table_px = _col_px(6) + sum(_col_px(w) for w in widths)

    def _make_header(ws, title, subtitle, word):
        ws.set_row(TITLE_ROW, title_height or _text_height(title, table_px, 14))
        ws.set_row(CODE_ROW, 18)
        ws.set_row(COLNUM_ROW, 14)
        auto = _header_heights(columns, header_depth, widths, word)
        manual = header_heights or [None] * header_depth
        for i, (a, m) in enumerate(zip(auto, manual)):
            ws.set_row(HEADER_ROW + i, m or a)

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
        f = fmt.get(('cell', col)) or fmt[_CELL_FORMAT[kind]]
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
                ws.write_number(row, i, value,
                                fmt.get(('total', i)) or fmt['total_money'])
            elif c.kind in ('int', 'money', 'avg') and c.total:
                # 'avg' без avg_of складывается как есть - так делал
                # Rep.SetColSumTotal; см. комментарий к Col.avg_of
                value = sum(float(r.get(c.key) or 0) for r in records)
                ws.write_number(row, i, value,
                                fmt.get(('total', i))
                                or fmt[_TOTAL_FORMAT[c.kind]])
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

    def _write_sql_sheet(workbook, sql):
        sheet = workbook.add_worksheet('SQL')
        sheet.set_column(0, 8, 14)
        lines = sql.splitlines()
        sheet.merge_range(0, 0, max(len(lines) - 1, 1), 8, sql, fmt['sql'])

    def _bind_values(params, sql):
        """Кандидаты в бинды: параметры формы плюс границы периода."""
        if check_params:
            check_params(params)
        candidates = {k: (v if v != '' else None)
                      for k, v in params.items() if k != 'file_name'}
        title, subtitle, word = name, '', ''
        for key, mapping in (text_params or {}).items():
            title = title.replace('{' + key + '}', mapping.get(params.get(key), ''))
        if date_range:
            first = _parse_date(params['date_first'])
            second = _parse_date(params['date_second'])
            if second < first:
                raise ValueError('Начальная дата больше конечной')
            if max_days is not None and (second - first).days > max_days:
                raise ValueError('Выбран слишком большой период!')
            candidates.update(d_from=first,
                              d_to=second + datetime.timedelta(days=1),
                              y_from=datetime.date(first.year, 1, 1))
            phrase = f'{first:%d.%m.%Y} по {second:%d.%m.%Y}'
            title = (title.replace('{date_from}', f'{first:%d.%m.%Y}')
                          .replace('{date_to}', f'{second:%d.%m.%Y}')
                          .replace('{date_to_eom}', f'{_eom(second):%d.%m.%Y}')
                          .replace('{date_from_dash}', f'{first:%d-%m-%Y}')
                          .replace('{date_to_dash}', f'{second:%d-%m-%Y}'))
            if PERIOD_SLOT in name:
                title = title.replace(PERIOD_SLOT, phrase)
            elif '{date_from' in name:
                pass            # даты уже стоят в названии, отдельная подпись не нужна
            else:
                subtitle = f'За период: с {phrase}'
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
                title = title.replace(PERIOD_SLOT, phrase)
            else:
                subtitle = f'За период: {phrase}'
        # "на 02.10.2026 г." - дата формирования, как sysdate в названии оригинала
        title = title.replace('{today}', f'{datetime.date.today():%d.%m.%Y}')
        for key in title_params:
            title = title.replace('{' + key + '}', str(params.get(key) or ''))
        if title_sql:
            # реквизиты в названии, которые берутся из БД (ФИО, СИК, наименование)
            rows = select_2(title_sql, _used_binds(title_sql, candidates),
                            profile=profile, raise_on_error=True)
            if not rows:
                raise ValueError(title_not_found)
            for key, value in rows[0].items():
                title = title.replace('{' + key + '}', str(value or ''))
        return _used_binds(sql, candidates), title, subtitle, word

    fmt = None          # заполняется внутри do_report, живёт в замыкании

    def do_report(file_name: str, **params):
        nonlocal fmt

        if os.path.isfile(file_name):
            log.info(f'Отчёт уже существует {file_name}')
            return file_name

        start_time = datetime.datetime.now()
        log.info(f'DO REPORT. START {code}. PARAMS: {params}, FILE: {file_name}')

        try:
            # stmt - текст запроса или функция(params) -> текст: у отчётов, где
            # разрез зависит от формы (область / республика), запросы разные
            sql = stmt(params) if callable(stmt) else stmt
            binds, title, subtitle, word = _bind_values(params, sql)
            log.info(f'REPORT: {code}. BINDS: {binds}')

            # raise_on_error=True: пустой результат не должен маскировать ошибку
            # запроса, иначе отчёт тихо запишется пустым и получит статус "готов"
            records = select_2(sql, binds, profile=profile, raise_on_error=True)

            with xlsxwriter.Workbook(file_name) as workbook:
                fmt = _build_formats(workbook, leaves)

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
                        kind = (c.kind_of and record.get(c.kind_of)) or c.kind
                        _write_cell(sheet, row, i, record.get(c.key), kind)
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
                _write_sql_sheet(workbook, sql)
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
