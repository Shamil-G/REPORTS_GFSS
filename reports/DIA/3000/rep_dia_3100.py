from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3100 - Ведомость перечисленных социальных выплат в разрезе БВУ'
report_code = '3100'

stmt_report = """
  Select nvl(r.knp, 'ВСЕГО:') knp,
         bt.Name,
         r.rfpw_id r,
     sum(r.cnt) cnt,
     sum(r.col_p) col,
     sum(r.summa) SM,
     nvl(CASE WHEN r.rfpm_group = '0701' THEN '2'
        WHEN r.rfpm_group = '0702' THEN '1'
        ELSE substr(r.rfpm_group, 4, 1)-- извращение для сортировки
          END, 'Z') ord
    From ss_decoding r, rfrc_recipient_last rc, rfbl_bank_list bt, rfpm_payments rfpm
   Where r.PAY_DATE Between TO_DATE(:dt_from,'YYYY-MM-DD') And TO_DATE(:dt_to,'YYYY-MM-DD')
     And r.TMST_ID = 103
     And r.rfrc_id = rc.RFRC_ID
     And rc.BANK_TYPE = bt.rfbl_Id
     AND r.rfpm_group = rfpm.rfpm_id
  Group By Grouping Sets (1,(bt.rfbl_id, bt.Name, r.rfpw_id, r.knp, r.rfpm_group, rfpm.name ))
  Order By ord, rfpm_group, knp, rfbl_id
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 30)

    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 5, 15)

    worksheet.write(2, 0,'КНП', common_format)
    worksheet.write(2, 1,'Наименование банка', common_format)
    worksheet.write(2, 2,'Способ выплаты', common_format)
    worksheet.write(2, 3,'Кол-во платежей', common_format)
    worksheet.write(2, 4,'Кол-во получателей', common_format)
    worksheet.write(2, 5,'Сумма', common_format)


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

            first_row = 4
            row_num = first_row - 1

            # Метки подытогов по кодам КНП
            knp_subtotal_labels = {
                '027': 'Итого по утрате трудоспособности',
                '046': 'Итого по потере кормильца',
                '048': 'Итого по потере работы',
                '096': 'Итого по беременности и родам',
                '091': 'Итого по уходу за ребенком до года/до полутора лет',
            }

            def write_subtotal(target_row: int, start_row: int, end_row: int, label: str):
                worksheet[0].merge_range(target_row, 0, target_row, 1, label, title_format)
                for col in range(2, 6):
                    col_letter = xl_col_to_name(col)
                    fmt = total_money_format if col == 5 else total_digital_format
                    worksheet[0].write_formula(
                        target_row,
                        col,
                        f'=SUM({col_letter}{start_row+1}:{col_letter}{end_row+1})',
                        fmt
                    )

            group_start_row = row_num
            current_knp_code = None

            for record in rows:
                knp_code = str(record[0]).strip() if record[0] is not None else None

                # КНП сменился
                if current_knp_code is not None and knp_code != current_knp_code:
                    if current_knp_code in knp_subtotal_labels:
                        write_subtotal(row_num, group_start_row, row_num - 1, knp_subtotal_labels[current_knp_code])
                        row_num += 1
                    # группа сменилась в любом случае — сбрасываем начало новой группы
                    group_start_row = row_num

                worksheet[0].write(row_num, 0, record[0], digital_format)
                worksheet[0].write(row_num, 1, record[1], region_name_format)

                worksheet[0].write(row_num, 2, record[2], digital_format)
                worksheet[0].write(row_num, 3, record[3], digital_format)

                worksheet[0].write(row_num, 4, record[4], digital_format)
                worksheet[0].write(row_num, 5, record[5], money_format)

                current_knp_code = knp_code
                row_num += 1

            # Последняя группа перед 'ВСЕГО:'
            if current_knp_code in knp_subtotal_labels:
                write_subtotal(row_num, group_start_row, row_num - 1, knp_subtotal_labels[current_knp_code])
                row_num += 1

            worksheet[0].freeze_panes(3, 0)

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
