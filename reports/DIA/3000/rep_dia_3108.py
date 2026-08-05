from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3108 - Отчет по платежам в разрезе КНП'
report_code = '3108'

stmt_report = """
  SELECT
    t.nm,
    t.in_out,
    t.cipher_id_knp,
    t.descr,
    CASE WHEN t.nm NOT IN (2, 4, 6) THEN COUNT(t.mhmh_id) ELSE 0 END p_cnt,
    SUM(t.cnt) cnt,
    SUM(t.pay_sum) p_sum
  FROM
    (SELECT
      CASE WHEN pd.tmst_id IN (3, 6) THEN 'Входящие' ELSE 'Исходящие' END in_out,
      CASE WHEN pd.tmst_id IN (3, 6) THEN 'Ошибочные' WHEN pd.tmst_id = 103 THEN 'Доставленные' ELSE 'Обработанные' END descr,
      CASE WHEN pd.tmst_id IN (3, 6) AND pd.cipher_id_knp = '012' THEN 1
           WHEN pd.tmst_id IN (3, 6) AND pd.cipher_id_knp = '017' THEN 3
           WHEN pd.tmst_id IN (3, 6) AND pd.cipher_id_knp = '026' THEN 5
           WHEN pd.tmst_id IN (3, 6) THEN 7
           ELSE 99 END nm,
      pd.cipher_id_knp,
      pd.mhmh_id,
      (SELECT COUNT(1) FROM pmdl_doc_list WHERE mhmh_id = pd.mhmh_id) cnt,
      pd.pay_sum
    FROM pmpd_pay_doc pd
    WHERE  (
            (pd.tmst_id IN (3, 6) AND pd.r_account = 'KZ67009SS00368609110')
            OR (pd.tmst_id = 103 AND pd.p_account = 'KZ67009SS00368609110')
           )
    AND pd.pay_date BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
    UNION

    SELECT
      'Входящие' in_out,
      'Обработанные' descr,
      14 nm,
      pd.cipher_id_knp,
      pd.mhmh_id,
      (SELECT COUNT(1) FROM pmdl_doc_list WHERE mhmh_id = pd.mhmh_id) cnt,
      pd.pay_sum
    FROM pmpd_pay_doc pd
    WHERE pd.tmst_id = 5
    AND pd.cipher_id_knp NOT IN ('012', '017', '160', '026', '183') --Добавили 05.02.2018 начали вылазить в отчет
    AND pd.pay_date BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
    UNION

    SELECT
      'Входящие',
      'Ошибочные разрезанные',
      CASE WHEN pd.cipher_id_knp = '012' THEN 2
           WHEN pd.cipher_id_knp = '017' THEN 4
           WHEN pd.cipher_id_knp = '026' THEN 6
           ELSE 99
      END nm,
      pd.cipher_id_knp,
      pd.mhmh_id,
      COUNT(dl.mhmh_id),
      sum(dl.pay_sum)
    FROM pmpd_pay_doc pd, pmdl_doc_list dl
    WHERE pd.mhmh_id = dl.mhmh_id
    AND pd.tmst_id = 5
    AND pd.cipher_id_knp IN ('012', '017', '026', '094')
    AND EXISTS (SELECT 1 FROM pmdl_doc_list dl WHERE dl.mhmh_id = pd.mhmh_id AND dl.rfem_id IS NOT NULL)
    AND dl.rfem_id IS NOT NULL
    AND pd.pay_date BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
    GROUP BY pd.tmst_id, pd.mhmh_id, pd.cipher_id_knp
    UNION

    SELECT
      'Входящие',
      'Обработанные разрезанные',
      CASE WHEN pd.cipher_id_knp = '012' THEN 9
        WHEN pd.cipher_id_knp = '017' THEN 11
        WHEN pd.cipher_id_knp = '026' THEN 13
        ELSE 99
      END nm,
      pd.cipher_id_knp,
      pd.mhmh_id,
      COUNT(pd.mhmh_id),
      sum(dl.pay_sum)
    FROM pmpd_pay_doc pd, pmdl_doc_list dl
    WHERE pd.mhmh_id = dl.mhmh_id
    AND pd.tmst_id = 5
    AND pd.cipher_id_knp IN ('012', '017', '026', '094')
    AND EXISTS (SELECT 1 FROM pmdl_doc_list dl WHERE dl.mhmh_id = pd.mhmh_id AND dl.rfem_id IS NOT NULL)
    AND dl.rfem_id IS NULL
    AND pd.pay_date BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
    GROUP BY pd.tmst_id, pd.mhmh_id, pd.cipher_id_knp
    UNION

    SELECT
      'Входящие',
      'Обработанные целые',
      CASE WHEN pd.cipher_id_knp = '012' THEN 8
           WHEN pd.cipher_id_knp = '017' THEN 10
           WHEN pd.cipher_id_knp = '026' THEN 12
           ELSE 99 END nm,
      pd.cipher_id_knp,
      pd.mhmh_id,
      COUNT(pd.mhmh_id),
      sum(dl.pay_sum)
    FROM pmpd_pay_doc pd, pmdl_doc_list dl
    WHERE pd.mhmh_id = dl.mhmh_id
    AND pd.tmst_id = 5
    AND pd.cipher_id_knp IN ('012', '017', '026', '094')
    AND pd.pay_date BETWEEN TO_DATE(:dt_from,'YYYY-MM-DD') AND TO_DATE(:dt_to,'YYYY-MM-DD')
    AND NOT EXISTS (SELECT 1 FROM pmdl_doc_list dl WHERE dl.mhmh_id = pd.mhmh_id AND dl.rfem_id IS NOT NULL)
    GROUP BY pd.tmst_id, pd.mhmh_id, pd.cipher_id_knp
    ) t
  GROUP BY t.nm, t.in_out, t.descr, t.cipher_id_knp
  ORDER BY t.nm, t.cipher_id_knp
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 40)
    worksheet.set_row(3, 30)

    worksheet.set_column(0, 6, 15)

    worksheet.write(2, 0,'Документы', common_format)
    worksheet.write(2, 1,'КНП', common_format)
    worksheet.write(2, 2,'Статус', common_format)
    worksheet.write(2, 3,'Количество платежей', common_format)
    worksheet.write(2, 4,'Количество записей', common_format)
    worksheet.write(2, 5,'Сумма, тенге', common_format)


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

            err_row = proc_row = deliv_row = None
            err_cnt = err_rec = err_sum = 0
            proc_cnt = proc_rec = proc_sum = 0
            deliv_cnt = deliv_rec = deliv_sum = 0

            for record in rows:
                worksheet[0].write(row_num, 0, record[0], region_name_format)
                worksheet[0].write(row_num, 1, record[2], digital_format)
                worksheet[0].write(row_num, 2, record[3], region_name_format)
                worksheet[0].write(row_num, 3, record[4], digital_format)
                worksheet[0].write(row_num, 4, record[5], digital_format)
                worksheet[0].write(row_num, 5, record[6], money_format)

                status = record[3]

                if 'Ошибочные' in status:
                    if err_row is None:
                        err_row = row_num
                    err_cnt += record[4]
                    err_rec += record[5]
                    err_sum += record[6]

                elif 'Обработанные' in status:
                    if proc_row is None:
                        proc_row = row_num
                    proc_cnt += record[4]
                    proc_rec += record[5]
                    proc_sum += record[6]

                elif 'Доставленные' in status:
                    if deliv_row is None:
                        deliv_row = row_num
                    deliv_cnt += record[4]
                    deliv_rec += record[5]
                    deliv_sum += record[6]

                row_num += 1

            # строка итогов
            def write_total(row, title, cnt, rec, sm):
                worksheet[0].merge_range(row, 0, row, 2, title, title_format)
                worksheet[0].write(row, 3, cnt, total_digital_format)
                worksheet[0].write(row, 4, rec, total_digital_format)
                worksheet[0].write(row, 5, sm, total_money_format)
                return row + 1

            row_num = write_total(row_num, 'ИТОГО Ошибочные', err_cnt, err_rec, err_sum)
            row_num = write_total(row_num, 'ИТОГО Обработанные', proc_cnt, proc_rec, proc_sum)
            row_num = write_total(row_num, 'ИТОГО Доставленные', deliv_cnt, deliv_rec, deliv_sum)

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
