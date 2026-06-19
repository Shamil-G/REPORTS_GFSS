from configparser import ConfigParser
import xlsxwriter
import datetime
from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3128 - Количество получателей и сумма в разрезе степени'
report_code = '3128'

stmt_report = """
SELECT
       TO_DATE(:dt_from,'YYYY-MM-DD') f,
       TO_DATE(:dt_to,'YYYY-MM-DD') t,
       COUNT(DISTINCT CASE WHEN rfpm = '07020101' THEN PNCD_ID END) CNT01,
       SUM(CASE WHEN rfpm = '07020101' THEN SUM_PAY ELSE 0 END) SUM01,
       ROUND(AVG(CASE WHEN rfpm = '07020101' THEN ps END), 2) AVG01,

       COUNT(DISTINCT CASE WHEN rfpm = '07020102' THEN PNCD_ID END) CNT02,
       SUM(CASE WHEN rfpm = '07020102' THEN SUM_PAY ELSE 0 END) SUM02,
       ROUND(AVG(CASE WHEN rfpm = '07020102' THEN ps END), 2) AVG02,

       COUNT(DISTINCT CASE WHEN rfpm = '07020103' THEN PNCD_ID END) CNT03,
       SUM(CASE WHEN rfpm = '07020103' THEN SUM_PAY ELSE 0 END) SUM03,
       ROUND(AVG(CASE WHEN rfpm = '07020103' THEN ps END), 2) AVG03,

       COUNT(DISTINCT PNCD_ID) CNT,
       SUM(SUM_PAY) SUM_PAY,
       ROUND(AVG(ps), 2) AVG_ALL
FROM (
    SELECT
           FIRST_VALUE(D.RFPM_ID)
               OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) RFPM,
           PP.PNPT_ID,
           D.SOURCE_ID,
           D.PNCD_ID,
           D.PAY_SUM + D.SUM_DEBT SUM_PAY,
           PH.SUM_PAY PS
    FROM PNPD_DOCUMENT D
         LEFT JOIN PNPT_PAYMENT PP
             ON D.SOURCE_ID = PP.PNPT_ID
         LEFT JOIN PAYMENT_HISTORY PH
             ON D.PNPD_ID = PH.PNPD_ID
    WHERE D.PNCP_DATE BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD')
                          AND TO_DATE(:dt_to,'YYYY-MM-DD')
      AND D.RFPM_ID LIKE '0702%'
      AND D.RIDT_ID IN (4,6,7,8)
      AND D.STATUS IN (0,1,2,3,5,7)
      AND D.PNSP_ID > 0
)
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(0, 24)
    worksheet.set_row(1, 24)

    worksheet.set_column(0, 0, 6)
    worksheet.set_column(1, 14, 18)

    headers = [
        '№',
        'Дата с',
        'Дата по',
        'Кол-во 07020101',
        'Сумма 07020101',
        'Средняя 07020101',
        'Кол-во 07020102',
        'Сумма 07020102',
        'Средняя 07020102',
        'Кол-во 07020103',
        'Сумма 07020103',
        'Средняя 07020103',
        'Общее кол-во',
        'Общая сумма',
        'Среднее'
    ]

    for col, header in enumerate(headers):
        worksheet.write(2, col, header, common_format)


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

            money_format = workbook.add_format({'num_format': '# ### ### ##0.00', 'align': 'right'})
            money_format.set_border(1)
            money_format.set_align('vcenter')

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

            row_cnt = 1
            all_cnt = 0
            shift_row = 3
            cnt_part = 0

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

            record = cursor.fetchone()
            all_cnt = 1

            if not record:
                log.warning(f'REPORT {report_code}. Данные отсутствуют')
                workbook.close()
                set_status_report(file_name, 2)
                return None

            worksheet[page_num - 1].write(3, 0, 1, digital_format)

            worksheet[page_num - 1].write(3, 1, record[0], date_format)
            worksheet[page_num - 1].write(3, 2, record[1], date_format)

            worksheet[page_num - 1].write(3, 3, record[2], digital_format)
            worksheet[page_num - 1].write(3, 4, record[3], money_format)
            worksheet[page_num - 1].write(3, 5, record[4], money_format)

            worksheet[page_num - 1].write(3, 6, record[5], digital_format)
            worksheet[page_num - 1].write(3, 7, record[6], money_format)
            worksheet[page_num - 1].write(3, 8, record[7], money_format)

            worksheet[page_num - 1].write(3, 9, record[8], digital_format)
            worksheet[page_num - 1].write(3, 10, record[9], money_format)
            worksheet[page_num - 1].write(3, 11, record[10], money_format)

            worksheet[page_num - 1].write(3, 12, record[11], digital_format)
            worksheet[page_num - 1].write(3, 13, record[12], money_format)
            worksheet[page_num - 1].write(3, 14, record[13], money_format)

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
