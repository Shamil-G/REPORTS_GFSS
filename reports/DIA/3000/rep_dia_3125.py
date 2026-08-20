from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3125 - Сведения о числе получателей по полу по районам'
report_code = '3125'

stmt_report = """
Select
 reg_id,
 rfbn.NAME,
 
 SUM(CASE WHEN rfpm = '0701' THEN cnt_sv ELSE 0 END) c01,
 SUM(CASE WHEN rfpm = '0701' AND sex = 1 THEN cnt_sv ELSE 0 END) c01m,
 SUM(CASE WHEN rfpm = '0701' AND sex = 0 THEN cnt_sv ELSE 0 END) c01w,
 SUM(CASE WHEN rfpm = '0701' THEN summ ELSE 0 END) s01,
 SUM(CASE WHEN rfpm = '0701' AND sex = 1 THEN summ ELSE 0 END) s01m,
 SUM(CASE WHEN rfpm = '0701' AND sex = 0 THEN summ ELSE 0 END) s01w,

 SUM(CASE WHEN rfpm = '0702' THEN cnt_sv ELSE 0 END) c02,
 SUM(CASE WHEN rfpm = '0702' AND sex = 1 THEN cnt_sv ELSE 0 END) c02m,
 SUM(CASE WHEN rfpm = '0702' AND sex = 0 THEN cnt_sv ELSE 0 END) c02w,
 SUM(CASE WHEN rfpm = '0702' THEN summ ELSE 0 END) s02,
 SUM(CASE WHEN rfpm = '0702' AND sex = 1 THEN summ ELSE 0 END) s02m,
 SUM(CASE WHEN rfpm = '0702' AND sex = 0 THEN summ ELSE 0 END) s02w,

 SUM(CASE WHEN rfpm = '0703' THEN cnt_sv ELSE 0 END) c03,
 SUM(CASE WHEN rfpm = '0703' AND sex = 1 THEN cnt_sv ELSE 0 END) c03m,
 SUM(CASE WHEN rfpm = '0703' AND sex = 0 THEN cnt_sv ELSE 0 END) c03w,
 SUM(CASE WHEN rfpm = '0703' THEN summ ELSE 0 END) s03,
 SUM(CASE WHEN rfpm = '0703' AND sex = 1 THEN summ ELSE 0 END) s03m,
 SUM(CASE WHEN rfpm = '0703' AND sex = 0 THEN summ ELSE 0 END) s03w,

 SUM(CASE WHEN rfpm = '0704' THEN cnt_sv ELSE 0 END) c04,
 SUM(CASE WHEN rfpm = '0704' AND sex = 1 THEN cnt_sv ELSE 0 END) c04m,
 SUM(CASE WHEN rfpm = '0704' AND sex = 0 THEN cnt_sv ELSE 0 END) c04w,
 SUM(CASE WHEN rfpm = '0704' THEN summ ELSE 0 END) s04,
 SUM(CASE WHEN rfpm = '0704' AND sex = 1 THEN summ ELSE 0 END) s04m,
 SUM(CASE WHEN rfpm = '0704' AND sex = 0 THEN summ ELSE 0 END) s04w,

 SUM(CASE WHEN rfpm = '0705' THEN cnt_sv ELSE 0 END) c05,
 SUM(CASE WHEN rfpm = '0705' AND sex = 1 THEN cnt_sv ELSE 0 END) c05m,
 SUM(CASE WHEN rfpm = '0705' AND sex = 0 THEN cnt_sv ELSE 0 END) c05w,
 SUM(CASE WHEN rfpm = '0705' THEN summ ELSE 0 END) s05,
 SUM(CASE WHEN rfpm = '0705' AND sex = 1 THEN summ ELSE 0 END) s05m,
 SUM(CASE WHEN rfpm = '0705' AND sex = 0 THEN summ ELSE 0 END) s05w,

 SUM(cnt_sv) ca,
 SUM(CASE WHEN sex = 1 THEN cnt_sv ELSE 0 END) cam,
 SUM(CASE WHEN sex = 0 THEN cnt_sv ELSE 0 END) caw,
 SUM(summ) sa,
 SUM(CASE WHEN sex = 1 THEN summ ELSE 0 END) sam,
 SUM(CASE WHEN sex = 0 THEN summ ELSE 0 END) saw
From (Select
      reg_id,
      rfpm,
      sex,
      Sum(sum_all) summ,
      Count(1) cnt_sv
        From (Select pr.sex,
                     a.*
                From (Select sipr_id,
                             sicp_id,
                             rfbn_id reg_id,
                             Substr(rfpm_id, 1, 4) rfpm,
                             sum_all
                        From (Select s.sipr_id,
                                     s.sicp_id,
                                     s.rfbn_id,
                                     s.rfpm_id,
                                     s.sum_all,
                                     trunc(s.date_approve) date_calc
                                From SIPR_MAKET_FIRST_APPROVE_2 s
                                WHERE substr(s.rfbn_id,1,2) = :rfbn_id)
                       Where date_calc Between TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')) a,
                     person pr
               Where a.sicp_id = pr.sicid) b
               Group By reg_id, rfpm, sex ) t, rfbn_branch rfbn
    WHERE t.reg_id = rfbn.RFBN_ID
    GROUP BY reg_id, rfbn.NAME
    ORDER BY reg_id
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 40)
    worksheet.set_row(3, 40)

    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 1, 30)
    worksheet.set_column(1, 40, 15)

    worksheet.merge_range(2, 0, 3, 0, 'Код региона', common_format)
    worksheet.merge_range(2, 1, 3, 1, 'Наименование региона', common_format)

    worksheet.merge_range(2, 2, 2, 7, 'по случаю потери кормильца', common_format)
    worksheet.merge_range(2, 8, 2, 13, 'по случаю утраты трудоспособности', common_format)
    worksheet.merge_range(2, 14, 2, 19, 'по случаю потери работы', common_format)
    worksheet.merge_range(2, 20, 2, 25, 'на случай потери дохода в связи с беременностью и родами, с усыновлением (удочерением) новорожденного ребенка (детей)', common_format)
    worksheet.merge_range(2, 26, 2, 31, 'на случай потери дохода в связи с уходом за ребенком по достижении им возраста 1 года', common_format)
    worksheet.merge_range(2, 32, 2, 34, 'Количество', common_format)
    worksheet.merge_range(2, 35, 2, 37, 'Сумма выплат (тенге)', common_format)


    for start_col in [2, 8, 14, 20, 26, 32]:
        worksheet.write(3, start_col,     'всего', common_format)
        worksheet.write(3, start_col + 1, 'мужчин', common_format)
        worksheet.write(3, start_col + 2, 'женщин', common_format)
        worksheet.write(3, start_col + 3, 'всего сумма выплат\n(тенге)', common_format)
        worksheet.write(3, start_col + 4, 'мужчин', common_format)
        worksheet.write(3, start_col + 5, 'женщин', common_format)


def do_report(file_name: str, date_first: str, date_second: str, rfbn_id: str):
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
                cursor.execute(stmt_report, dt_from=date_first, dt_to=date_second, rfbn_id=rfbn_id)
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

            first_row = 5
            row_num = first_row - 1

            for record in rows:
                worksheet[0].write(row_num, 0, record[0], digital_format)
                worksheet[0].write(row_num, 1, record[1], region_name_format)

                worksheet[0].write(row_num, 2, record[2], digital_format)
                worksheet[0].write(row_num, 3, record[3], digital_format)
                worksheet[0].write(row_num, 4, record[4], digital_format)
                worksheet[0].write(row_num, 5, record[5], money_format)
                worksheet[0].write(row_num, 6, record[6], money_format)
                worksheet[0].write(row_num, 7, record[7], money_format)

                worksheet[0].write(row_num, 8, record[8], digital_format)
                worksheet[0].write(row_num, 9, record[9], digital_format)
                worksheet[0].write(row_num, 10, record[10], digital_format)
                worksheet[0].write(row_num, 11, record[11], money_format)
                worksheet[0].write(row_num, 12, record[12], money_format)
                worksheet[0].write(row_num, 13, record[13], money_format)

                worksheet[0].write(row_num, 14, record[14], digital_format)
                worksheet[0].write(row_num, 15, record[15], digital_format)
                worksheet[0].write(row_num, 16, record[16], digital_format)
                worksheet[0].write(row_num, 17, record[17], money_format)
                worksheet[0].write(row_num, 18, record[18], money_format)
                worksheet[0].write(row_num, 19, record[19], money_format)

                worksheet[0].write(row_num, 20, record[20], digital_format)
                worksheet[0].write(row_num, 21, record[21], digital_format)
                worksheet[0].write(row_num, 22, record[22], digital_format)
                worksheet[0].write(row_num, 23, record[23], money_format)
                worksheet[0].write(row_num, 24, record[24], money_format)
                worksheet[0].write(row_num, 25, record[25], money_format)

                worksheet[0].write(row_num, 26, record[26], digital_format)
                worksheet[0].write(row_num, 27, record[27], digital_format)
                worksheet[0].write(row_num, 28, record[28], digital_format)
                worksheet[0].write(row_num, 29, record[29], money_format)
                worksheet[0].write(row_num, 30, record[30], money_format)
                worksheet[0].write(row_num, 31, record[31], money_format)

                worksheet[0].write(row_num, 32, record[32], digital_format)
                worksheet[0].write(row_num, 33, record[33], digital_format)
                worksheet[0].write(row_num, 34, record[34], digital_format)

                worksheet[0].write(row_num, 35, record[35], money_format)
                worksheet[0].write(row_num, 36, record[36], money_format)
                worksheet[0].write(row_num, 37, record[37], money_format)


                row_num += 1

            # строка итогов
            worksheet[0].merge_range(row_num, 0, row_num, 1, 'ИТОГО', title_format)

            for col in range(1, 38):
                col_letter = xl_col_to_name(col)

                fmt = total_money_format if col in (5, 6, 7, 11, 12, 13, 17, 18, 19,
                                                    23, 24, 25, 29, 30, 31, 35, 36, 37) else total_digital_format

                worksheet[0].write_formula(
                    row_num,
                    col,
                    f'=SUM({col_letter}{first_row}:{col_letter}{row_num})',
                    fmt
                )

            worksheet[0].freeze_panes(3, 0)
            worksheet[0].freeze_panes(4, 0)

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


def thread_report(file_name: str, date_first: str, date_second: str, rfbn_id :str):
    import threading
    log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
    log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
    threading.Thread(target=do_report, args=(file_name, date_first, date_second, rfbn_id), daemon=True).start()
    return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01.xlsx', '01.10.2022', '31.10.2022')
