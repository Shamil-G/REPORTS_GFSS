# -*- coding: utf-8 -*-
"""
Отчет 02. Списки получателей выплат по регионам и кодам выплат.
Исправленная версия.
"""
import datetime
import os.path
import threading

import xlsxwriter

from util.logger import log
from db.connect import select_2, LOADER_PROFILE
from model.manage_reports import set_status_report

report_name = 'Списки получателей выплат по регионам и кодам выплат'
report_code = 'LST.PAY'

# Профиль подключения к Oracle (см. db/connect.py).
# Схеме reports не видны pnpd_document / pnpt_payment / person,
# поэтому этот отчет ходит в БД под учетной записью загрузчика.
DB_PROFILE = LOADER_PROFILE

# Коды статусов отчета (сверь с model/manage_reports.py)
STATUS_DONE = 2
STATUS_ERROR = 3

HEADER_ROW = 3                  # строка с названиями колонок
DATA_START_ROW = HEADER_ROW + 1
MAX_ROWS_PER_SHEET = 500_000    # разбиение на листы "Список N"

# (алиас в SQL, заголовок в Excel, ширина, тип)
COLUMNS = [
    ("Код области",  "Код региона",    10, "center"),
    ("Код выплаты",  "Код выплаты",    12, "center"),
    ("ИИН",          "ИИН получателя", 16, "center"),
    ("Пол",          "Пол",             6, "center"),
    ("Сумма выплаты", "Сумма выплаты", 18, "money"),
]
NUM_COL_WIDTH = 8  # ширина колонки "№"

stmt_report = """
Select /*+parallel(8)*/
       d.rfbn_id "Код области",
       d.rfpm_id "Код выплаты",
       p.iin "ИИН",
       case when p.sex=1 then 'М' else 'Ж' end as "Пол",
       Sum(d.sum_pay) "Сумма выплаты"
from (
    select /*+parallel(2)*/
           d.pncd_id sicid,
           substr(d.rfpm_id, 1, 4) rfpm_id,
           d.pay_sum + d.sum_debt sum_pay,
           first_value(substr(d.rfbn_id, 1, 2)) over (Partition By d.pncd_id order by d.pncp_date desc) rfbn_id
    From pnpd_document d, pnpt_payment pp
    Where d.source_id = pp.pnpt_id(+)
      And d.pncp_date >= to_date(:dt_from,'YYYY-MM-DD')
      And d.pncp_date <  to_date(:dt_to,'YYYY-MM-DD') + 1
      And substr(d.rfpm_id,1,4) in ('0701','0702','0703','0704','0705')
      And d.ridt_id In (4, 6, 7, 8)
      And d.status  In (0, 1, 2, 3, 5, 7)
      And d.pnsp_id > 0
      And (:rfpm is null or substr(d.rfpm_id,1,4) = :rfpm)
      And (:rfbn is null or substr(d.rfbn_id,1,2) = :rfbn)
    ) d, person p
where d.sicid = p.sicid
Group By d.rfbn_id, d.rfpm_id, p.iin, p.sex
order by 1, 2, 3
"""


def build_formats(workbook):
    return {
        "title": workbook.add_format({
            "align": "center", "valign": "vcenter",
            "font_size": 14, "bold": True}),
        "rep_code": workbook.add_format({
            "align": "left", "valign": "vcenter",
            "font_size": 12, "bold": True}),
        "subtitle": workbook.add_format({
            "align": "right", "valign": "vcenter",
            "font_size": 11, "italic": True}),
        "header": workbook.add_format({
            "bold": True, "align": "center", "valign": "vcenter",
            "font_size": 12, "border": 1, "bg_color": "#E0F7FF",
            "text_wrap": True}),
        "colnum": workbook.add_format({
            "align": "center", "valign": "vcenter",
            "font_size": 9, "border": 1, "bg_color": "#E0F7FF"}),
        "center": workbook.add_format({
            "align": "center", "valign": "vcenter", "border": 1,
            "bg_color": "#f2f2f2", "num_format": "@"}),
        "text": workbook.add_format({
            "align": "left", "valign": "vcenter", "border": 1,
            "bg_color": "#f2f2f2"}),
        "money": workbook.add_format({
            "align": "right", "valign": "vcenter", "border": 1,
            "bg_color": "#f2f2f2", "num_format": "### ### ### ##0.00"}),
        "sql": workbook.add_format({
            "border": 1, "align": "left", "valign": "top",
            "fg_color": "#FAFAD7", "text_wrap": True}),
    }


def make_header(ws, fmt, date_first, date_second):
    """Шапка листа: название, период, нумерация колонок, заголовки."""
    total_cols = len(COLUMNS) + 1  # +1 на колонку "№"

    ws.set_row(0, 24)
    ws.set_row(1, 18)
    ws.set_row(2, 14)
    ws.set_row(3, 30)

    ws.merge_range(0, 0, 0, total_cols - 1, report_name, fmt["title"])

	# Дата, время исполнения
    ws.write(1, total_cols - 1, f'За период: {date_first}  -  {date_second}', fmt["subtitle"])

    # Код отчёта — крайняя левая ячейка строки 1
    ws.write(1, 0, report_code, fmt["rep_code"])
    
    ws.set_column(0, 0, NUM_COL_WIDTH)
    for i, (_alias, _title, width, _kind) in enumerate(COLUMNS, start=1):
        ws.set_column(i, i, width)

    for i in range(total_cols):
        ws.write(2, i, str(i + 1), fmt["colnum"])

    ws.write(HEADER_ROW, 0, '№', fmt["header"])
    for i, (_alias, title, _width, _kind) in enumerate(COLUMNS, start=1):
        ws.write(HEADER_ROW, i, title, fmt["header"])

    ws.freeze_panes(DATA_START_ROW, 0)
    ws.repeat_rows(HEADER_ROW)


def write_sql_sheet(workbook, fmt):
    sheet = workbook.add_worksheet('SQL')
    lines = stmt_report.splitlines()
    sheet.set_column(0, 8, 14)
    sheet.merge_range(0, 0, max(len(lines) - 1, 1), 8, stmt_report, fmt["sql"])


def write_rows(workbook, fmt, records, date_first, date_second):
    """Пишет данные, создавая листы 'Список N' по мере необходимости.

    xlsxwriter не умеет переставлять листы после создания: порядок закладок
    задается порядком вызовов add_worksheet(). Поэтому листы с данными
    создаются здесь, а лист SQL — уже после, последней закладкой.
    """
    sheets = []
    sheet = None
    all_cnt = 0

    for record in records:
        row_on_sheet = all_cnt % MAX_ROWS_PER_SHEET
        if row_on_sheet == 0:
            sheet = workbook.add_worksheet(f'Список {len(sheets) + 1}')
            make_header(sheet, fmt, date_first, date_second)
            sheets.append(sheet)

        excel_row = DATA_START_ROW + row_on_sheet
        all_cnt += 1
        sheet.write_number(excel_row, 0, all_cnt, fmt["center"])

        for col, (alias, _title, _width, kind) in enumerate(COLUMNS, start=1):
            value = record.get(alias)
            if value is None:
                sheet.write_blank(excel_row, col, None, fmt[kind if kind != "money" else "money"])
            elif kind == "money":
                sheet.write_number(excel_row, col, float(value), fmt["money"])
            elif kind == "date":
                sheet.write_datetime(excel_row, col, value, fmt["center"])
            else:
                sheet.write_string(excel_row, col, str(value), fmt[kind])

    return sheets, all_cnt


def do_report(file_name: str, date_first: str, date_second: str,
              rfbn_id: str = None, rfpm_id: str = None):
    if os.path.isfile(file_name):
        log.info(f'Отчет уже существует {file_name}')
        return file_name

    start_time = datetime.datetime.now()
    log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, '
             f'DATE_TO: {date_second}, RFBN_ID: {rfbn_id}, RFPM_ID: {rfpm_id}, '
             f'FILE_PATH: {file_name}')

    try:
        # пустая строка из web-формы -> None
        params = {
            'dt_from': date_first,
            'dt_to': date_second,
            'rfbn': (rfbn_id or None),
            'rfpm': (rfpm_id or None),
        }

        # raise_on_error=True: пустой результат не должен маскировать ошибку запроса,
        # иначе отчет тихо запишется пустым и получит статус "готов"
        records = select_2(stmt_report, params, profile=DB_PROFILE, raise_on_error=True)

        with xlsxwriter.Workbook(file_name) as workbook:
            fmt = build_formats(workbook)

            # 1) сначала листы с данными
            sheets, all_cnt = write_rows(workbook, fmt, records, date_first, date_second)

            if not sheets:
                sheet = workbook.add_worksheet('Список 1')
                make_header(sheet, fmt, date_first, date_second)
                sheet.write(DATA_START_ROW, 0, 'Нет данных для отображения')
                sheets.append(sheet)

            # 2) и только потом SQL — последней закладкой
            write_sql_sheet(workbook, fmt)

            sheets[0].activate()

        set_status_report(file_name, STATUS_DONE)
        stop_time = datetime.datetime.now()
        log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено '
                 f'({start_time:%H:%M:%S} - {stop_time:%H:%M:%S}), '
                 f'загружено {all_cnt} записей')
        return file_name

    except Exception:
        log.exception(f'REPORT: {report_code}. Ошибка формирования {file_name}')
        try:
            set_status_report(file_name, STATUS_ERROR)
        except Exception:
            log.exception('Не удалось выставить статус ошибки')
        if os.path.isfile(file_name):
            try:
                os.remove(file_name)  # чтобы битый файл не считался готовым
            except OSError:
                pass
        raise


def thread_report(file_name: str, date_first: str, date_second: str,
                  rfbn_id: str = None, rfpm_id: str = None):
    log.info(f'THREAD REPORT. {datetime.datetime.now():%d-%m-%Y %H:%M:%S} -> {file_name}')
    log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}, date_to: {date_second}')
    threading.Thread(
        target=do_report,
        args=(file_name, date_first, date_second, rfbn_id, rfpm_id),
        daemon=True,
    ).start()
    return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_02.xlsx', '2022-10-01', '2022-10-31')