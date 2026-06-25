from configparser import ConfigParser
import xlsxwriter
import datetime
from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3129 - Количество и средний размер в разрезе стажа участия'
report_code = '3129'

stmt_report = """
SELECT
   CASE
     WHEN KSU = 0.1  THEN 'Менее 6 месяцев'
     WHEN KSU = 0.7  THEN 'От 6 до 12 месяцев'
     WHEN KSU = 0.75 THEN 'От 12 до 24 месяцев'
     WHEN KSU = 0.85 THEN 'От 24 до 36 месяцев'
     WHEN KSU = 0.9  THEN 'От 36 до 48 месяцев'
     WHEN KSU = 0.95 THEN 'От 48 до 60 месяцев'
     WHEN KSU = 1    THEN 'Более 60 месяцев'
   END STAGE,
   KSU,
   COUNT(DISTINCT CASE WHEN RFPM_ID = '07020101' THEN SICP_ID END) CNT01,
   ROUND(AVG(CASE WHEN RFPM_ID = '07020101' THEN SUM_ALL END),2) AVG01,
   COUNT(DISTINCT CASE WHEN RFPM_ID = '07020102' THEN SICP_ID END) CNT02,
   ROUND(AVG(CASE WHEN RFPM_ID = '07020102' THEN SUM_ALL END),2) AVG02,
   COUNT(DISTINCT CASE WHEN RFPM_ID = '07020103' THEN SICP_ID END) CNT03,
   ROUND(AVG(CASE WHEN RFPM_ID = '07020103' THEN SUM_ALL END),2) AVG03,
   COUNT(DISTINCT SICP_ID) CNT,
   ROUND(AVG(SUM_ALL),2) AVG_ALL
FROM SIPR_MAKET_FIRST_APPROVE_2
WHERE RFPM_ID LIKE '0702%'
  AND TRUNC(DATE_APPROVE)
      BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD')
          AND TO_DATE(:dt_to,'YYYY-MM-DD')
GROUP BY KSU
ORDER BY KSU
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(0, 24)
    worksheet.set_row(1, 24)
    worksheet.set_row(2, 40)
    worksheet.set_row(3, 32)
    worksheet.set_row(4, 48)

    worksheet.set_column(0, 0, 30)   # Стаж участия
    worksheet.set_column(1, 1, 10)   # КСУ

    worksheet.set_column(2, 2, 14)
    worksheet.set_column(3, 3, 18)

    worksheet.set_column(4, 4, 14)
    worksheet.set_column(5, 5, 18)

    worksheet.set_column(6, 6, 14)
    worksheet.set_column(7, 7, 18)

    worksheet.set_column(8, 8, 14)
    worksheet.set_column(9, 9, 18)

    # Стаж участия и КСУ
    worksheet.merge_range('A3:A5', 'Стаж участия', common_format)
    worksheet.merge_range('B3:B5', 'КСУ', common_format)

    # Общий заголовок
    worksheet.merge_range(
        'C3:H3',
        'Степень утраты трудоспособности, %',
        common_format
    )

    # Всего
    worksheet.merge_range(
        'I3:J3',
        'Всего',
        common_format
    )

    # 80-100
    worksheet.merge_range(
        'C4:D4',
        '80-100',
        common_format
    )

    worksheet.write(
        4, 2,
        'Количество,\nчеловек',
        common_format
    )

    worksheet.write(
        4, 3,
        'Средний\nразмер,\nтенге',
        common_format
    )

    # 60-80
    worksheet.merge_range(
        'E4:F4',
        '60-80',
        common_format
    )

    worksheet.write(
        4, 4,
        'Количество,\nчеловек',
        common_format
    )

    worksheet.write(
        4, 5,
        'Средний\nразмер,\nтенге',
        common_format
    )

    # 30-60
    worksheet.merge_range(
        'G4:H4',
        '30-60',
        common_format
    )

    worksheet.write(
        4, 6,
        'Количество,\nчеловек',
        common_format
    )

    worksheet.write(
        4, 7,
        'Средний\nразмер,\nтенге',
        common_format
    )

    # Всего
    worksheet.merge_range(
        'I4:I5',
        'Количество,\nчеловек',
        common_format
    )

    worksheet.merge_range(
        'J4:J5',
        'Средний\nразмер,\nтенге',
        common_format
    )


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

            for idx, record in enumerate(rows, start=1):
                worksheet[0].write(row_num, 0, record[0], region_name_format)
                worksheet[0].write(row_num, 1, record[1], money_format)

                worksheet[0].write(row_num, 2, record[2], digital_format)
                worksheet[0].write(row_num, 3, record[3], money_format)

                worksheet[0].write(row_num, 4, record[4], digital_format)
                worksheet[0].write(row_num, 5, record[5], money_format)

                worksheet[0].write(row_num, 6, record[6], digital_format)
                worksheet[0].write(row_num, 7, record[7], money_format)

                worksheet[0].write(row_num, 8, record[8], digital_format)
                worksheet[0].write(row_num, 9, record[9], money_format)

                row_num += 1

            # строка итогов
            worksheet[0].merge_range(row_num, 0, row_num, 1, 'ИТОГО', title_format)

            for col in range(2, 10):
                col_letter = chr(ord('A') + col)

                if col in (3, 5, 7, 9):
                    worksheet[0].write(row_num, col, '', total_money_format)
                    continue

                worksheet[0].write_formula(
                    row_num,
                    col,
                    f'=SUM({col_letter}{first_row}:{col_letter}{row_num})',
                    total_digital_format
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
