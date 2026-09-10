from configparser import ConfigParser
import xlsxwriter
import datetime

from xlsxwriter.utility import xl_col_to_name

from util.logger import log
import oracledb
import os.path
from model.manage_reports import set_status_report

report_name = '501 - Сведения о количестве участников СОСС'
report_code = '501'

stmt_report = """
WITH params AS (
    SELECT
        TO_DATE(:dt_from, 'YYYY-MM-DD') dt_from,
        TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'), 'MONTH') date_from_month,
        ADD_MONTHS(TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'), 'MONTH'), 1) date_to,
        TRUNC(TO_DATE(:dt_from, 'YYYY-MM-DD'), 'YEAR') date_from_year
    FROM dual
),
src_year AS (
    SELECT /*+parallel(4)*/
        si.SICID,
        si.SUM_PAY,
        FIRST_VALUE(P_RNN) OVER(
            PARTITION BY sicid
            ORDER BY pay_date_gfss DESC
        ) LAST_RNN,
        FIRST_VALUE(PAY_DATE_GFSS) OVER(
            PARTITION BY sicid
            ORDER BY pay_date_gfss DESC
        ) LAST_DATE
    FROM si_member_2 si
    CROSS JOIN params p
    WHERE si.Knp = '012'
      AND PAY_DATE_GFSS >= p.date_from_year
      AND PAY_DATE_GFSS <  p.date_to
      AND PAY_DATE >= ADD_MONTHS(p.date_from_year, -1)
      AND PAY_DATE <  p.date_to
),
src_mnth AS (
    SELECT /*+parallel(4)*/
        si.SICID,
        si.SUM_PAY,
        FIRST_VALUE(P_RNN) OVER(
            PARTITION BY sicid
            ORDER BY pay_date_gfss DESC
        ) LAST_RNN,
        FIRST_VALUE(PAY_DATE_GFSS) OVER(
            PARTITION BY sicid
            ORDER BY pay_date_gfss DESC
        ) LAST_DATE
    FROM si_member_2 si
    CROSS JOIN params p
    WHERE si.Knp = '012'
      AND PAY_DATE_GFSS >= p.date_from_month
      AND PAY_DATE_GFSS <  p.date_to
      AND PAY_DATE >= ADD_MONTHS(p.date_from_month, -1)
      AND PAY_DATE <  p.date_to
)
, org_src_year as (
    select /*+parallel(4)*/
           UNIQUE src.SICID,
           coalesce(rc.rfbn_id, 'zzzz') rfbn_id,
           SUM(src.SUM_PAY) SUM_DOH --Суммарный доход
    from src_year src, rfon_organization o, cato_branch rc
    WHERE src.LAST_RNN=o.bin(+)
    and   o.cato=rc.code(+)
    and   coalesce(rc.rfbn_id,'zzzz') like :region || '%'
    GROUP BY src.SICID, rc.rfbn_id
)
, org_src_mnth as (
    select /*+parallel(4)*/
           UNIQUE src.SICID,
           coalesce(rc.rfbn_id, 'zzzz') rfbn_id,
           SUM(src.SUM_PAY) SUM_DOH --Суммарный доход
    from src_mnth src, rfon_organization o, cato_branch rc
    WHERE src.LAST_RNN=o.bin(+)
    and   o.cato=rc.code(+)
    and   coalesce(rc.rfbn_id,'zzzz') like :region || '%'
    GROUP BY src.SICID, rc.rfbn_id
)
, all_year as(
    select rfbn_id,
         count(y.sicid) all_cnt,
         sum(case when p.sex=0 then 1 else 0 end) women_cnt,
         sum(case when p.sex=1 then 1 else 0 end) men_cnt,
         sum(y.sum_doh) all_sum,
         sum(case when p.sex=0 then y.sum_doh else 0 end) women_sum,
         sum(case when p.sex=1 then y.sum_doh else 0 end) men_sum
    from org_src_year y, person p
    where y.sicid=p.sicid
    group by rfbn_id
)
, all_mnth as (
    select rfbn_id,
         count(m.sicid) all_cnt,
         sum(case when p.sex=0 then 1 else 0 end) women_cnt,
         sum(case when p.sex=1 then 1 else 0 end) men_cnt,
         sum(m.sum_doh) all_sum,
         sum(case when p.sex=0 then m.sum_doh else 0 end) women_sum,
         sum(case when p.sex=1 then m.sum_doh else 0 end) men_sum
    from org_src_mnth m, person p
    where m.sicid=p.sicid
    group by rfbn_id
)
select y.rfbn_id,
      case when y.rfbn_id = 'zzzz' then 'Неизвестный район'
           else
      (select coalesce(name_ru,'Неизвестный район')
       from cato_branch cb
       where cb.rfbn_id=y.rfbn_id and lev=2
      )
     end name,

     y.all_cnt ca,
     y.men_cnt mca,
     y.women_cnt wca,
     y.all_sum sa,
     y.men_sum msa,
     y.women_sum wsa,

     m.all_cnt c,
     m.men_cnt mc,
     m.women_cnt wc,
     m.all_sum s,
     m.men_sum ms,
     m.women_sum ws
     
from all_year y, all_mnth m
where y.rfbn_id=m.rfbn_id(+)
order by rfbn_id
"""


def format_worksheet(worksheet, common_format):

    worksheet.set_row(2, 30)
    worksheet.set_row(3, 24)
    worksheet.set_row(4, 42)

    worksheet.set_column(0, 0, 8)
    worksheet.set_column(1, 1, 30)
    worksheet.set_column(2, 13, 15)

    worksheet.merge_range(2, 0, 4, 0, 'Код', common_format)
    worksheet.merge_range(2, 1, 4, 1, 'Наименование района, города', common_format)

    worksheet.merge_range(2, 2, 2, 7, 'С начала года', common_format)
    worksheet.merge_range(2, 8, 2, 13, 'Отчетный месяц', common_format)

    worksheet.merge_range(3, 2, 3, 4, 'Количество участников', common_format)
    worksheet.merge_range(3, 5, 3, 7, 'Сумма, тенге', common_format)

    worksheet.merge_range(3, 8, 3, 10, 'Количество участников', common_format)
    worksheet.merge_range(3, 11, 3, 13, 'Сумма, тенге', common_format)

    for start_col in [2, 5, 8, 11]:
        worksheet.write(4, start_col,     'Всего,\nчеловек', common_format)
        worksheet.write(4, start_col + 1, 'Мужчин',        common_format)
        worksheet.write(4, start_col + 2, 'Женщин', common_format)


def do_report(file_name: str, date_first: str, region: str):
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
            worksheet[page_num - 1].write(1, 0, f'За период: {date_first} в {region} регионе', title_name_report)

            log.info(f'REPORT {report_code}. CREATING REPORT')

            try:
                cursor.execute(stmt_report, dt_from=date_first, region=region)
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

                row_num += 1

            # строка итогов
            worksheet[0].merge_range(row_num, 0, row_num, 1, 'ИТОГО', title_format)

            for col in range(2, 14):
                col_letter = xl_col_to_name(col)

                fmt = total_money_format if col in (5, 6, 7, 11, 12, 13) else total_digital_format

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


def thread_report(file_name: str, date_first: str, region: str):
    import threading
    log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
    log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
    threading.Thread(target=do_report, args=(file_name, date_first, region), daemon=True).start()
    return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01.xlsx', '01.10.2022', '31.10.2022')
