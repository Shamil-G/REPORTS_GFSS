from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '3030 - Отчет 9V (для Министерства)'
report_code = '3030'

stmt_report = """
with main_src as (
select rownum num,
substr(pd.doc_assign, 2, 2) rfbn_id,
pd.doc_date,
pd.doc_nmb,
pd.cipher_id_knp knp,
pd.refer,
dl.pay_sum,
nvl(dl.period,pd.period) as period,
dl.fm|| ' ' ||dl.nm|| ' ' ||dl.ft as fio ,
pd.doc_assign,
pd.rfbk_mfo_pbank,
dl.rnn,
dl.sicid
from pmpd_pay_doc pd,
pmdl_doc_list dl
where pd.pay_date=dl.pay_date
and pd.mhmh_id=dl.mhmh_id
and (
pd.cipher_id_knp in ('028', '047', '092', '097')
or
( pd.cipher_id_knp = '049'
and pd.doc_assign like '%Возврат сумм%'
)
)
and pd.pay_date >= TO_DATE(:dt_from,'YYYY-MM-DD')
and trunc(pd.pay_date) < TO_DATE(:dt_to,'YYYY-MM-DD') 
and dl.pay_date >= TO_DATE(:dt_from,'YYYY-MM-DD')
and trunc(dl.pay_date) < TO_DATE(:dt_to,'YYYY-MM-DD') 
and pd.r_account= 'KZ70125KZT1001300134'
)
select rownum num, coalesce(reg_name,'Итого:') reg_name, cnt_all, sum_all, cnt_028, sum_028,
cnt_047, sum_047, cnt_049, sum_049, cnt_097, sum_097, cnt_092, sum_092
from (
select a.rfbn_id ||'. '|| b.NAME as reg_name,
sum(cnt_028+cnt_047+cnt_049+cnt_097+cnt_092) cnt_all,
sum(sum_028+sum_047+sum_049+sum_097+sum_092) sum_all,
sum(cnt_028) cnt_028, sum(sum_028) sum_028,
sum(cnt_047) cnt_047, sum(sum_047) sum_047,
sum(cnt_049) cnt_049, sum(sum_049) sum_049,
sum(cnt_097) cnt_097, sum(sum_097) sum_097,
sum(cnt_092) cnt_092, sum(sum_092) sum_092
from (
select case when knp='028' then cnt else 0 end cnt_028,
case when knp='028' then sum_pay else 0 end sum_028,
case when knp='047' then cnt else 0 end cnt_047,
case when knp='047' then sum_pay else 0 end sum_047,
case when knp='049' then cnt else 0 end cnt_049,
case when knp='049' then sum_pay else 0 end sum_049,
case when knp='097' then cnt else 0 end cnt_097,
case when knp='097' then sum_pay else 0 end sum_097,
case when knp='092' then cnt else 0 end cnt_092,
case when knp='092' then sum_pay else 0 end sum_092,
substr(rfbn_id,1,2) rfbn_id
from (
select count(knp) cnt,
sum(pay_sum) sum_pay,
rfbn_id,
knp
from main_src
group by rfbn_id, knp
order by rfbn_id, knp
)
) a, rfbn_branch b
where a.rfbn_id||'00'=b.RFBN_ID
group by cube(a.rfbn_id ||'. '|| b.NAME)
order by 1
)
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 40)
    worksheet.set_row(3, 50)

    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 1, 30)
    worksheet.set_column(2, 14, 15)

    worksheet.merge_range(2, 0, 3, 0, '№', common_format)
    worksheet.merge_range(2, 1, 3, 1, 'Код региона', common_format)
    worksheet.merge_range(2, 2, 2, 3, 'Всего', common_format)
    worksheet.merge_range(2, 4, 2, 5,'На случай утраты трудоспособности КНП=028', common_format)
    worksheet.merge_range(2, 6, 2, 7,'На случай потери кормильца КНП=047', common_format)
    worksheet.merge_range(2, 8, 2, 9,'На случай потери работы КНП=049', common_format)
    worksheet.merge_range(2, 10, 2, 11,'на случай потери дохода в связи с беременностью и родами, усыновлением (удочерением) новорожденного ребенка (детей) КНП=097', common_format)
    worksheet.merge_range(2, 12, 2, 13,'на случай потери дохода в связи с уходом за ребенком по достижении им возраста 1,5 лет КНП=092', common_format)

    for start_col in [2, 4, 6, 8, 10, 12]:
        worksheet.write(3, start_col,     'Кол-во получателей\n(человек)', common_format)
        worksheet.write(3, start_col + 1, 'Сумма возвратов\n(тыс. тенге)', common_format)


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
                worksheet[0].write(row_num, 0, record[0], digital_format)
                worksheet[0].write(row_num, 1, record[1], region_name_format)

                worksheet[0].write(row_num, 2, record[2], digital_format)
                worksheet[0].write(row_num, 3, record[3], money_format)

                worksheet[0].write(row_num, 4, record[4], digital_format)
                worksheet[0].write(row_num, 5, record[5], money_format)

                worksheet[0].write(row_num, 6, record[6], digital_format)
                worksheet[0].write(row_num, 7, record[7], money_format)

                worksheet[0].write(row_num, 8, record[8], digital_format)
                worksheet[0].write(row_num, 9, record[9], money_format)

                worksheet[0].write(row_num, 10, record[10], digital_format)
                worksheet[0].write(row_num, 11, record[11], money_format)

                worksheet[0].write(row_num, 12, record[12], digital_format)
                worksheet[0].write(row_num, 13, record[13], money_format)

                row_num += 1


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

