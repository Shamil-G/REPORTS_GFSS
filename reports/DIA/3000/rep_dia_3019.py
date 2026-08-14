from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3019 - статус 103 (3103)'
report_code = '3019'

stmt_report = """
select
    nvl(br.NAME,'Не определен') name_reg,
    reg,
    SUM(CASE WHEN d.knp = '012' THEN d.cnt ELSE 0 END) c012,
    SUM(CASE WHEN d.knp = '012' THEN d.sm ELSE 0 END) s012,
    SUM(CASE WHEN d.knp = '017' THEN d.cnt ELSE 0 END) c017,
    SUM(CASE WHEN d.knp = '017' THEN d.sm ELSE 0 END) s017
from(
  Select
       Nvl(nullif(case when r.rfbn_id IN ('1403', '1416', '1417', '1418') then '17'
       when r.rfbn_id IN ('0503', '0504', '0505', '0506', '0507', '0508', '0510', '0518') then '18'
       when r.rfbn_id IN ('0303', '0304', '0305', '0306', '0311', '0313', '0314', '0315', '0317', '0318') then '19'
       when r.rfbn_id IN ('0802', '0804', '0812', '0816', '0818') then '20'
       else r.Rfrg_Id end, '00'), 'ZZ') reg,
       s.knp,
       Count(Unique s.sicid) cnt,
       Sum(s.sum_pay) sm
    From( Select --/*+ ORDERED index (vd) use_nl (pdo vd dl pdi)*/
              dl.sicid, pdi.cipher_id_knp knp, dl.pay_sum sum_pay,
              first_value(pdi.p_rnn) Over(Partition By dl.sicid Order By decode(pdi.cipher_id_knp, '012', 0, 1), pdi.pay_date Desc rows Between unbounded preceding And unbounded following) last_rnn,
              first_value(pdi.pay_date) Over(Partition By dl.sicid Order By decode(pdi.cipher_id_knp, '012', 0, 1), pdi.pay_date Desc rows Between unbounded preceding And unbounded following) last_date
          From pmpd_pay_doc pdo,
--                    mhmh_msg_head mh,
              virtual_doc_list vd,
              pmdl_doc_list dl,
              pmpd_pay_doc pdi
          Where pdo.pay_date Between TO_DATE(:dt_from,'YYYY-MM-DD') And TO_DATE(:dt_to,'YYYY-MM-DD')
            -- Added Gusseinov 7 october 2019
          and dl.pay_date Between add_months(TO_DATE(:dt_from,'YYYY-MM-DD'),-1) And TO_DATE(:dt_to,'YYYY-MM-DD')
          and pdi.pay_date Between add_months(TO_DATE(:dt_from,'YYYY-MM-DD'),-1) And TO_DATE(:dt_to,'YYYY-MM-DD')
          -- End Added
          And pdo.cipher_id_knp In ('012', '017')
--                And pdo.mhmh_id = mh.mhmh_id
          And pdo.tmst_id = 103
          And pdo.mhmh_id = vd.mhmh_id_out
          And vd.mhmh_id_in = dl.mhmh_id
          And vd.pmdl_n_in = dl.pmdl_n
          And dl.mhmh_id = pdi.mhmh_id
         ) s, rfrr_id_region r
 Where (Case
         When s.last_date < to_date('01.01.2013', 'dd.mm.yyyy') Then
          'R'
         Else
          'I'
       End) = r.typ(+)
   And s.last_rnn = r.id(+)
 Group By Nvl(nullif(case when r.rfbn_id IN ('1403', '1416', '1417', '1418') then '17'
 when r.rfbn_id IN ('0503', '0504', '0505', '0506', '0507', '0508', '0510', '0518') then '18'
 when r.rfbn_id IN ('0303', '0304', '0305', '0306', '0311', '0313', '0314', '0315', '0317', '0318') then '19'
 when r.rfbn_id IN ('0802', '0804', '0812', '0816', '0818') then '20'
 else r.Rfrg_Id end, '00'), 'ZZ'), s.knp
 ) d, rfbn_branch br
 where br.RFBN_ID(+)=reg||'00'
 group by reg,nvl(br.NAME,'Не определен')
 order by reg
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 40)
    worksheet.set_row(3, 30)

    worksheet.set_column(0, 0, 30)
    worksheet.set_column(1, 1, 8)
    worksheet.set_column(1, 31, 15)

    worksheet.merge_range(2, 0, 3, 0, 'Наименование региона', common_format)
    worksheet.merge_range(2, 1, 3, 1, 'Код региона', common_format)

    worksheet.merge_range(2, 2, 2, 3, 'Социальные отчисления', common_format)
    worksheet.merge_range(2, 4, 2, 5, 'Пеня за несвоевременное перечисление социальных отчислений', common_format)

    for start_col in [2, 4]:
        worksheet.write(3, start_col,     'Количество,\nчеловек*', common_format)
        worksheet.write(3, start_col + 1, 'Сумма,\nтенге', common_format)


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

            first_row = 5
            row_num = first_row - 1

            for record in rows:
                worksheet[0].write(row_num, 0, record[0], region_name_format)
                worksheet[0].write(row_num, 1, record[1], digital_format)

                worksheet[0].write(row_num, 2, record[2], digital_format)
                worksheet[0].write(row_num, 3, record[3], money_format)

                worksheet[0].write(row_num, 4, record[4], digital_format)
                worksheet[0].write(row_num, 5, record[5], money_format)

                row_num += 1

            # строка итогов
            worksheet[0].merge_range(row_num, 0, row_num, 1, 'ИТОГО', title_format)

            for col in range(1, 6):
                col_letter = xl_col_to_name(col)

                fmt = total_money_format if col in (3, 5) else total_digital_format

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


def thread_report(file_name: str, date_first: str, date_second: str):
    import threading
    log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
    log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
    threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
    return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01.xlsx', '01.10.2022', '31.10.2022')
