from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3151 - Количество получателей и сумма выплаты по регионам'
report_code = '3151'

stmt_report = """
SELECT
  rfbn,
  br.name,
  COUNT(DISTINCT CASE WHEN rfpm = '07010101' THEN PNCD_ID END) CNT01,
  SUM(CASE WHEN rfpm = '07010101' THEN sm END) SUM01,
  ROUND(SUM(CASE WHEN rfpm = '07010101' THEN sm END)/COUNT(DISTINCT CASE WHEN rfpm = '07010101' THEN PNCD_ID END)/Months_Between(trunc(TO_DATE(:dt_to,'YYYY-MM-DD'), 'MM'), trunc(TO_DATE(:dt_from,'YYYY-MM-DD'), 'MM')) + 1) avg01,
  COUNT(DISTINCT CASE WHEN rfpm = '07010102' THEN PNCD_ID END) CNT02,
  SUM(CASE WHEN rfpm = '07010102' THEN sm END) SUM02,
  ROUND(SUM(CASE WHEN rfpm = '07010102' THEN sm END)/COUNT(DISTINCT CASE WHEN rfpm = '07010102' THEN PNCD_ID END)/Months_Between(trunc(TO_DATE(:dt_to,'YYYY-MM-DD'), 'MM'), trunc(TO_DATE(:dt_from,'YYYY-MM-DD'), 'MM')) + 1) avg02,
  COUNT(DISTINCT CASE WHEN rfpm = '07010103' THEN PNCD_ID END) CNT03,
  SUM(CASE WHEN rfpm = '07010103' THEN sm END) SUM03,
  ROUND(SUM(CASE WHEN rfpm = '07010103' THEN sm END)/COUNT(DISTINCT CASE WHEN rfpm = '07010103' THEN PNCD_ID END)/Months_Between(trunc(TO_DATE(:dt_to,'YYYY-MM-DD'), 'MM'), trunc(TO_DATE(:dt_from,'YYYY-MM-DD'), 'MM')) + 1) avg03,
  COUNT(DISTINCT CASE WHEN rfpm = '07010104' THEN PNCD_ID END) CNT04,
  SUM(CASE WHEN rfpm = '07010104' THEN sm END) SUM04,
  ROUND(SUM(CASE WHEN rfpm = '07010104' THEN sm END)/COUNT(DISTINCT CASE WHEN rfpm = '07010104' THEN PNCD_ID END)/Months_Between(trunc(TO_DATE(:dt_to,'YYYY-MM-DD'), 'MM'), trunc(TO_DATE(:dt_from,'YYYY-MM-DD'), 'MM')) + 1) avg04,
  COUNT(DISTINCT PNCD_ID ) CNTA,
  SUM(sm) SUMA,
  ROUND(SUM(sm)/COUNT(DISTINCT PNCD_ID)/Months_Between(trunc(TO_DATE(:dt_to,'YYYY-MM-DD'), 'MM'), trunc(TO_DATE(:dt_from,'YYYY-MM-DD'), 'MM')) + 1) avga
FROM(
SELECT
  d.pncd_id,
  d.source_id,
  FIRST_VALUE(SUBSTR(D.RFBN_ID, 1, 2) || '00') OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) rfbn,
  FIRST_VALUE(D.RFPM_ID) OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) rfpm,
  d.pay_sum + d.sum_debt sm
  FROM PNPD_DOCUMENT D
 WHERE D.PNCP_DATE BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
   AND D.RFPM_ID LIKE '0701%'
   AND D.RIDT_ID IN (4, 6, 7, 8)
   AND D.STATUS IN (0, 1, 2, 3, 5, 7)
   AND D.PNSP_ID > 0) t, rfbn_branch br
WHERE t.rfbn = br.RFBN_ID
GROUP BY rfbn, br.name
ORDER BY rfbn
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 30)
    worksheet.set_row(3, 24)
    worksheet.set_row(4, 42)

    worksheet.set_column(0, 0, 22)
    worksheet.set_column(1, 15, 14)

    worksheet.merge_range(2, 0, 4, 0, 'Наименование\nрегиона', common_format)

    worksheet.merge_range(2, 1, 2, 12, 'Количество иждивенцев', common_format)

    worksheet.merge_range(2, 13, 3, 15, 'Всего', common_format)

    worksheet.merge_range(3, 1, 3, 3, '1 иждивенец', common_format)
    worksheet.merge_range(3, 4, 3, 6, '2 иждивенца', common_format)
    worksheet.merge_range(3, 7, 3, 9, '3 иждивенца', common_format)
    worksheet.merge_range(3, 10, 3, 12, '4 и более иждивенца', common_format)

    for start_col in [1, 4, 7, 10, 13]:
        worksheet.write(4, start_col,     'Количество,\nчеловек', common_format)
        worksheet.write(4, start_col + 1, 'Сумма,\nтенге',        common_format)
        worksheet.write(4, start_col + 2, 'Средний размер,\nтенге', common_format)


def do_report(file_name: str, date_first: str, date_second: str):
    if os.path.isfile(file_name):
        log.info(f'Отчет уже существует {file_name}')
        return file_name

    s_date = datetime.datetime.now().strftime("%H:%M:%S")

    log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, FILE_PATH: {file_name}')

    config = ConfigParser()
    config.read('db_config.ini')

    ora_config = config['rep_db_loader']
    db_user = ora_config['db_user']
    db_password = ora_config['db_password']
    db_dsn = ora_config['db_dsn']
    log.info(f'{report_code}. db_user: {db_user}, db_dsn: {db_dsn}')

    with oracledb.connect(user=db_user, password=db_password, dsn=db_dsn) as connection:
        with connection.cursor() as cursor:
            workbook = xlsxwriter.Workbook(file_name)

            title_format = workbook.add_format({'bg_color': '#D1FFFF', 'align': 'center', 'font_color': 'black'})
            # title_format = workbook.add_format({'bg_color': '#C5FFFF', 'align': 'center', 'font_color': 'black'})
            title_format.set_align('vcenter')
            title_format.set_border(1)
            title_format.set_text_wrap()
            title_format.set_bold()

            title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '14'})
            title_name_report.set_align('vcenter')
            title_name_report.set_bold()

            title_format_it = workbook.add_format({'align': 'right'})
            title_format_it.set_align('vcenter')
            title_format_it.set_italic()

            title_report_code = workbook.add_format({'align': 'right', 'font_size': '14'})
            title_report_code.set_align('vcenter')
            title_report_code.set_bold()

            common_format = workbook.add_format({'align': 'center', 'font_color': 'black'})
            common_format.set_align('vcenter')
            common_format.set_border(1)

            region_name_format = workbook.add_format({'align': 'left', 'font_color': 'black'})
            region_name_format.set_align('vcenter')
            region_name_format.set_border(1)

            sum_pay_format = workbook.add_format(
                {'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
            sum_pay_format.set_border(1)

            date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
            date_format.set_border(1)
            date_format.set_align('vcenter')

            digital_format = workbook.add_format({'num_format': '#0', 'align': 'center'})
            digital_format.set_border(1)
            digital_format.set_align('vcenter')

            total_digital_format = workbook.add_format({'num_format': '#0', 'align': 'center'})
            total_digital_format.set_border(1)
            total_digital_format.set_align('vcenter')
            total_digital_format.set_bold()

            money_format = workbook.add_format({'num_format': '# ### ### ##0.00', 'align': 'right'})
            money_format.set_border(1)
            money_format.set_align('vcenter')

            total_money_format = workbook.add_format({'num_format': '# ### ### ##0.00', 'align': 'right'})
            total_money_format.set_border(1)
            total_money_format.set_align('vcenter')
            total_money_format.set_bold()

            now = datetime.datetime.now()
            log.info(f'Начало формирования {file_name}: {now.strftime("%d-%m-%Y %H:%M:%S")}')
            page_num = 1
            worksheet = []
            worksheet.append(workbook.add_worksheet(f'Список {page_num}'))
            sql_sheet = workbook.add_worksheet('SQL')
            merge_format = workbook.add_format({
                'bold': False,
                'border': 6,
                'align': 'left',
                'valign': 'vcenter',
                'fg_color': '#FAFAD7',
                'text_wrap': True
            })
            sql_sheet.merge_range(f'A1:I{len(stmt_report.splitlines())}', f'{stmt_report}', merge_format)

            worksheet[page_num - 1].activate()
            format_worksheet(worksheet=worksheet[page_num - 1], common_format=title_format)

            worksheet[page_num - 1].write(0, 0, report_name, title_name_report)
            worksheet[page_num - 1].write(1, 0, f'За период: {date_first} - {date_second}', title_name_report)

            log.info(f'REPORT {report_code}. CREATING REPORT')

            try:
                cursor.execute(stmt_report, dt_from=date_first, dt_to=date_second)
            except oracledb.DatabaseError as e:
                error, = e.args
                log.error(f"ERROR. REPORT {report_code}. error_code: {error.code}, error: {error.message}")
                log.info(f'\n---------\n{stmt_report}\n---------')
                set_status_report(file_name, 3)
                return None
            finally:
                log.info(f'REPORT: {report_code}. Выборка из курсора завершена')

            log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')

            rows = cursor.fetchall()

            if not rows:
                log.warning(f'REPORT {report_code}. Данные отсутствуют')
                workbook.close()
                set_status_report(file_name, 2)
                return None

            all_cnt = len(rows)

            first_row = 6
            row_num = first_row - 1

            for record in rows:
                worksheet[0].write(row_num, 0, record[1], region_name_format)
                worksheet[0].write(row_num, 1, record[2], digital_format)
                worksheet[0].write(row_num, 2, record[3], money_format)
                worksheet[0].write(row_num, 3, record[4], money_format)
                worksheet[0].write(row_num, 4, record[5], digital_format)
                worksheet[0].write(row_num, 5, record[6], money_format)
                worksheet[0].write(row_num, 6, record[7], money_format)
                worksheet[0].write(row_num, 7, record[8], digital_format)
                worksheet[0].write(row_num, 8, record[9], money_format)
                worksheet[0].write(row_num, 9, record[10], money_format)
                worksheet[0].write(row_num, 10, record[11], digital_format)
                worksheet[0].write(row_num, 11, record[12], money_format)
                worksheet[0].write(row_num, 12, record[13], money_format)
                worksheet[0].write(row_num, 13, record[14], digital_format)
                worksheet[0].write(row_num, 14, record[15], money_format)
                worksheet[0].write(row_num, 15, record[16], money_format)

                row_num += 1

            # строка итогов
            worksheet[0].write(row_num, 0, 'ИТОГО', title_format)

            for col in range(1, 16):
                col_letter = xl_col_to_name(col)

                fmt = total_money_format if col in (2, 3, 5, 6, 8, 9, 11, 12, 14, 15) else total_digital_format

                if col in (3, 6, 9, 12, 15):
                    worksheet[0].write(row_num, col, '', total_money_format)
                    continue

                worksheet[0].write_formula(
                    row_num,
                    col,
                    f'=SUM({col_letter}{first_row}:{col_letter}{row_num})',
                    fmt
                )

            worksheet[0].freeze_panes(3, 0)
            worksheet[0].freeze_panes(4, 0)
            worksheet[0].freeze_panes(5, 0)

            now = datetime.datetime.now()
            stop_time = now.strftime("%H:%M:%S")

            for i in range(page_num):
                # Шифр отчета
                worksheet[i].write(0, 5, report_code, title_report_code)
                worksheet[i].write(1, 5, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})',
                                   title_format_it)

            workbook.close()
            set_status_report(file_name, 2)

            log.info(
                f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {all_cnt} записей')


def thread_report(file_name: str, date_first: str, date_second: str):
    import threading
    log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
    log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
    threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
    return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01.xlsx', '01.10.2022', '31.10.2022')
