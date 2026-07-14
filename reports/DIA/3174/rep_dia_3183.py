from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3183 - Получатели, у которых удержаны ОПВ'
report_code = '3183'

stmt_report = """
SELECT
  rfbn,
  br.name,
  COUNT(DISTINCT CASE WHEN rfpm in ('07050001', '07050101') THEN PNCD_ID END) CNT01,
  SUM(CASE WHEN rfpm in ('07050001', '07050101') THEN sm END) SUM01,
  COUNT(DISTINCT CASE WHEN rfpm in ('07050002', '07050102') THEN PNCD_ID END) CNT02,
  SUM(CASE WHEN rfpm in ('07050002', '07050102') THEN sm END) SUM02,
  COUNT(DISTINCT CASE WHEN rfpm in ('07050003', '07050103') THEN PNCD_ID END) CNT03,
  SUM(CASE WHEN rfpm in ('07050003', '07050103') THEN sm END) SUM03,
  COUNT(DISTINCT CASE WHEN rfpm in ('07050004', '07050104') THEN PNCD_ID END) CNT04,
  SUM(CASE WHEN rfpm in ('07050004', '07050104') THEN sm END) SUM04,
  COUNT(DISTINCT PNCD_ID) CNTA,
  SUM(sm) SUMA
FROM(
SELECT
  d.pncd_id,
  d.source_id,
  last_VALUE(substr(D.RFBN_ID, 1, 2) || '00') OVER(PARTITION BY D.SOURCE_ID ORDER BY D.PNCP_DATE) rfbn,
  last_VALUE(D.RFPM_ID) OVER(PARTITION BY D.SOURCE_ID ORDER BY D.PNCP_DATE) rfpm,
  d.pay_sum + d.sum_debt sm
  FROM PNPD_DOCUMENT D
 WHERE D.PNCP_DATE BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
   AND D.RFPM_ID LIKE '0705%'
   AND D.RIDT_ID IN (4, 6, 7, 8)
   AND D.STATUS IN (0, 1, 2, 3, 5, 7)
   AND D.PNSP_ID > 0
   AND d.knp = '010') t, rfbn_branch br
WHERE t.rfbn = br.RFBN_ID
GROUP BY rfbn, br.name
ORDER BY rfbn
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 30)
    worksheet.set_row(3, 24)
    worksheet.set_row(4, 42)

    worksheet.set_column(0, 0, 30)
    worksheet.set_column(1, 18, 15)

    worksheet.merge_range(2, 0, 4, 0, 'Наименование\nрегиона', common_format)
    worksheet.merge_range(2, 1, 2, 8, 'По уходу за', common_format)

    worksheet.merge_range(3, 1, 3, 2, 'Первым ребенком', common_format)
    worksheet.merge_range(3, 3, 3, 4, 'Вторым ребенком', common_format)
    worksheet.merge_range(3, 5, 3, 6, 'Третьим ребенком', common_format)
    worksheet.merge_range(3, 7, 3, 8, 'Четвертым и более ребенком', common_format)
    worksheet.merge_range(2, 9, 3, 10, 'Всего', common_format)


    for start_col in [1, 3, 5, 7, 9]:
        worksheet.write(4, start_col,     'Количество,\nчеловек', common_format)
        worksheet.write(4, start_col + 1, 'Сумма ОПВ,\nтенге',        common_format)


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
                worksheet[0].write(row_num, 0, record[1], common_format)

                worksheet[0].write(row_num, 1, record[2], digital_format)
                worksheet[0].write(row_num, 2, record[3], money_format)

                worksheet[0].write(row_num, 3, record[4], digital_format)
                worksheet[0].write(row_num, 4, record[5], money_format)

                worksheet[0].write(row_num, 5, record[6], digital_format)
                worksheet[0].write(row_num, 6, record[7], money_format)

                worksheet[0].write(row_num, 7, record[8], digital_format)
                worksheet[0].write(row_num, 8, record[9], money_format)

                worksheet[0].write(row_num, 9, record[10], digital_format)
                worksheet[0].write(row_num, 10, record[11], money_format)

                row_num += 1

            # строка итогов
            worksheet[0].write(row_num, 0, 'ИТОГО', title_format)

            for col in range(1, 11):
                col_letter = xl_col_to_name(col)

                fmt = total_money_format if col in (2, 4, 6, 8, 10) else total_digital_format

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
