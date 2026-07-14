from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3185 - Сведения по доплате'
report_code = '3185'

stmt_report = """
SELECT
  t.rfpm_id,
  rfpm.shortname,
  COUNT(CASE WHEN sum_dop is null AND sex = 1 THEN sicp_id END) cntm,
  SUM(CASE WHEN sum_dop is null AND sex = 1 THEN sum_all END) summ,
  round(AVG(CASE WHEN sum_dop is null AND sex = 1 THEN sum_all END), 2) avgm,
  COUNT(CASE WHEN sum_dop is null AND sex = 0 THEN sicp_id END) cntw,
  SUM(CASE WHEN sum_dop is null AND sex = 0 THEN sum_all END) sumw,
  round(AVG(CASE WHEN sum_dop is null AND sex = 0 THEN sum_all END), 2) avgw,
  COUNT(CASE WHEN sum_dop is not null AND sex = 1 THEN sicp_id END) cntmd,
  SUM(CASE WHEN sum_dop is not null AND sex = 1 THEN sum_calc END)summc,
  SUM(CASE WHEN sum_dop is not null AND sex = 1 THEN sum_dop END) summdop,
  SUM(CASE WHEN sum_dop is not null AND sex = 1 THEN sum_all END) summd,
  round(AVG(CASE WHEN sum_dop is not null AND sex = 1 THEN sum_all END), 2)awgmd,
  COUNT(CASE WHEN sum_dop is not null AND sex = 0 THEN sicp_id END) cntwd,
  SUM(CASE WHEN sum_dop is not null AND sex = 0 THEN sum_calc END)sumwc,
  SUM(CASE WHEN sum_dop is not null AND sex = 0 THEN sum_dop END)sumwdop,
  SUM(CASE WHEN sum_dop is not null AND sex = 0 THEN sum_all END)sumwd,
  round(AVG(CASE WHEN sum_dop is not null AND sex = 0 THEN sum_all END), 2) awgwd
FROM (
  SELECT
     rfpm_id,
     sum_all,
     sum_dop,
     sicp_id,
     sum_calc,
     sfa.sex
  FROM SIPR_MAKET_FIRST_APPROVE_2 sfa
  WHERE RFPM_ID LIKE '0705%'
  AND trunc(DATE_APPROVE,'DD') BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
 ) t, rfpm_payments rfpm
 WHERE t.rfpm_id = rfpm.rfpm_id
 GROUP BY t.rfpm_id, rfpm.shortname
 ORDER BY t.rfpm_id
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 30)
    worksheet.set_row(3, 24)
    worksheet.set_row(4, 80)

    worksheet.set_column(0, 0, 40)
    worksheet.set_column(1, 20, 15)

    worksheet.merge_range(2, 0, 4, 0, 'Наименование\nвыплаты', common_format)
    worksheet.merge_range(2, 1, 2, 6, 'СВур расчитана по социальным отчислениям', common_format)
    worksheet.merge_range(2, 7, 2, 16, 'СВур, доведенная до размера ГСП', common_format)

    worksheet.merge_range(3, 1, 3, 3, 'Мужчины', common_format)
    worksheet.merge_range(3, 4, 3, 6, 'Женщины', common_format)

    worksheet.merge_range(3, 7, 3, 11, 'Мужчины', common_format)
    worksheet.merge_range(3, 12, 3, 16, 'Женщины', common_format)

    for start_col in [1, 4]:
        worksheet.write(4, start_col,     'Количество,\nчеловек', common_format)
        worksheet.write(4, start_col + 1, 'Назначенная сумма,\nтенге', common_format)
        worksheet.write(4, start_col + 2, 'Средний размер,\nтенге', common_format)

    for start_col in [7, 12]:
        worksheet.write(4, start_col,     'Количество,\nчеловек', common_format)
        worksheet.write(4, start_col + 1, 'Сумма СВур, рассчитанная\nна основании поступивших\nсоциальных отчислений', common_format)
        worksheet.write(4, start_col + 2, 'Сумма\nдоплаты', common_format)
        worksheet.write(4, start_col + 3, 'Сумма СВур,\nдоведенная до уровня ГСП', common_format)
        worksheet.write(4, start_col + 4, 'Средний размер,\nтенге', common_format)


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
                worksheet[0].write(row_num, 3, record[4], money_format)

                worksheet[0].write(row_num, 4, record[5], digital_format)
                worksheet[0].write(row_num, 5, record[6], money_format)
                worksheet[0].write(row_num, 6, record[7], money_format)

                worksheet[0].write(row_num, 7, record[8], digital_format)
                worksheet[0].write(row_num, 8, record[9], money_format)
                worksheet[0].write(row_num, 9, record[10], money_format)
                worksheet[0].write(row_num, 10, record[11], money_format)
                worksheet[0].write(row_num, 11, record[12], money_format)

                worksheet[0].write(row_num, 12, record[13], digital_format)
                worksheet[0].write(row_num, 13, record[14], money_format)
                worksheet[0].write(row_num, 14, record[15], money_format)
                worksheet[0].write(row_num, 15, record[16], money_format)
                worksheet[0].write(row_num, 16, record[17], money_format)

                row_num += 1

            # строка итогов
            worksheet[0].write(row_num, 0, 'ИТОГО', title_format)

            for col in range(1, 17):
                col_letter = xl_col_to_name(col)

                fmt = total_digital_format if col in (1, 4, 7, 12) else total_money_format

                if col in (3, 6, 11, 16):
                    worksheet[0].write(row_num, col, '', fmt)
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
