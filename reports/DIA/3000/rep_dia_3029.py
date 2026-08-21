from configparser import ConfigParser
import xlsxwriter
import datetime
from   util.logger import log
import oracledb
import os.path
from   model.manage_reports import set_status_report

report_name = 'СО по категориям МЗП и регионам (3029)'
report_code = '3029'

stmt_report = """
with period as(
   select to_date(:dt_from,'YYYY-MM-DD') dt_from, 
          to_date(:dt_to,'YYYY-MM-DD') + 1 as dt_to 
--   select to_date('2026-07-01','YYYY-MM-DD') dt_from, 
--          to_date('2026-07-31','YYYY-MM-DD') + 1 as dt_to 
  from dual
)
,mzp as (
  Select /*+ PARALLEL(8)*/
      br, SICID, 
    --sex, 
    LAST_RNN, SUM_PAY, cnt_pay_mnth,
      --type_payer,
      case  when cnt_mzp/cnt_pay_mnth   < 1 then 1
            when cnt_mzp/cnt_pay_mnth = 1 then 2
            when cnt_mzp/cnt_pay_mnth < 2 then 3
            when cnt_mzp/cnt_pay_mnth = 2 then 4
            when cnt_mzp/cnt_pay_mnth < 3 then 5
            when cnt_mzp/cnt_pay_mnth < 4 then 6
            when cnt_mzp/cnt_pay_mnth < 5 then 7
            when cnt_mzp/cnt_pay_mnth < 6 then 8
            when cnt_mzp/cnt_pay_mnth < 7 then 9
            when cnt_mzp/cnt_pay_mnth < 8 then 10
            when cnt_mzp/cnt_pay_mnth < 9 then 11
            when cnt_mzp/cnt_pay_mnth < 10 then 12
            when cnt_mzp/cnt_pay_mnth = 10 then 13
            when cnt_mzp/cnt_pay_mnth > 10 then 14
      end kat_mzp
  from                
  (
      SELECT /*+ PARALLEL(8)*/
             br, S.SICID, s.sex, S.LAST_RNN, SUM(S.SUM_PAY) SUM_PAY,
             count(DISTINCT s.pay_month) cnt_pay_mnth,
             sum(nvl(cnt_mzp,0)) cnt_mzp
       FROM ( SELECT /*+ PARALLEL(8)*/
                     FIRST_VALUE(substr(coalesce(cb.RFBN_ID,'ZZ'),1,2))
                     over(partition by sm.sicid order by sm.pay_date_gfss desc) BR,
                     SM.SICID,
                     p.sex,
                     SM.SUM_PAY,
                     sm.pay_month,
                     round(sm.cnt_mzp,3) cnt_mzp,
                     FIRST_VALUE(sm.P_RNN) OVER(PARTITION BY sm.sicid ORDER BY sm.pay_date_gfss DESC) LAST_RNN,
                     FIRST_VALUE(sm.pay_date_gfss) OVER(PARTITION BY sm.sicid ORDER BY sm.pay_date_gfss DESC) LAST_date_gfss
              FROM SI_MEMBER_2 SM, PERSON P, rfon_organization rf, cato_branch cb, period p
              WHERE SM.KNP = '012'
        AND SM.PAY_DATE_GFSS >= p.dt_from
        and SM.PAY_DATE_GFSS < p.dt_to
        AND   SM.PAY_DATE >= add_months(p.dt_from,-1) 
        AND SM.PAY_DATE < p.dt_to
              AND SM.TYPE_PAYER!='E'
              and sm.SICID = P.SICID
              AND sm.p_rnn=rf.bin(+)
              and rf.cato=cb.code(+)
      ) S
      GROUP BY br, s.sicid, s.sex, s.last_rnn
  )
),
type_co as 
(
  select /*+ parallel(4)*/
         Unique(s.sicid),
         sum(case when per.iin=s.p_rnn then 1 else 0 end) ip_sam,
         sum(case when per.iin!=s.p_rnn and substr(s.p_rnn,5,1) not in (0,1,2,3)  then 1 else 0 end) ur,
         sum(case when per.iin!=s.p_rnn and S.TYPE_PAYER='I' then 1 else 0 end) fiz,
         sum(case when S.TYPE_PAYER='SZ' then 1 else 0 end) sz,
         sum(case when S.TYPE_PAYMENT='P' then 1 else 0 end) pz,
         sum(case when S.TYPE_PAYMENT='O' then 1 else 0 end) o_pl
  from si_member_2 S, person per, period p
  where s.sicid=per.sicid 
  AND   S.KNP = '012'
  AND S.PAY_DATE_GFSS >= p.dt_from
  and S.PAY_DATE_GFSS < p.dt_to
  AND   S.PAY_DATE >= add_months(p.dt_from,-1) 
  AND S.PAY_DATE < p.dt_to
  AND S.TYPE_PAYER!='E'
  GROUP BY s.sicid
)
select kat_mzp, rfbn_id, type, count(sicid) as cnt_sicid, sum(sum_pay) as sum_pay
from (
  SELECT /*+ parallel(4)*/
      m.kat_mzp,
      -- m.sex,
      m.br rfbn_id,--"Код",
      nvl(br.NAME, 'Не найден') name, --"Наименование",
      case when a.ip_sam>0 and a.fiz=0 and a.ur=0  and a.sz=0 and a.pz=0 and a.o_pl=0 then 'ИП'
          when a.fiz>0 and a.ip_sam=0 and a.ur=0 and a.sz=0 and a.pz=0 and a.o_pl=0 then 'Наемный физ'
          when a.ur>0 and a.ip_sam=0 and a.fiz=0 and a.sz=0 and a.pz=0 and a.o_pl=0 then 'Наемный юр'
          when a.sz>0 and a.ip_sam=0 and a.fiz=0 and a.ur=0 and a.pz=0 and a.o_pl=0 then 'Самозанятые'
          when a.pz>0 and a.ip_sam=0 and a.fiz=0 and a.ur=0 and a.sz=0 and a.o_pl=0 then 'Платформенная занятость'
          when a.o_pl>0 and a.ip_sam=0 and a.fiz=0 and a.ur=0 and a.sz=0 and a.pz=0 then 'Объединенный платёж'
          when a.fiz>0 and a.ur>0 and a.ip_sam=0 and a.sz=0 and a.pz=0 then 'Смешанный физ+юр'
          else 'Смешанный' 
      end type, 
      a.sicid,
      m.sum_pay
  FROM  type_co a, mzp m, rfbn_branch br 
  WHERE a.sicid = m.sicid
  AND   m.br||'00'= br.RFBN_ID(+)
)
GROUP BY kat_mzp, rfbn_id, type
ORDER BY 1,2,4
"""


def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 14)
	#worksheet.set_row(3, 48)

	worksheet.set_column(0, 0, 6)
	worksheet.set_column(1, 1, 6)
	worksheet.set_column(2, 2, 12)
	worksheet.set_column(3, 3, 40)
	worksheet.set_column(4, 4, 16)
	worksheet.set_column(5, 5, 18)
	worksheet.set_column(6, 6, 18)

	worksheet.write(2,0, '1', common_format)
	worksheet.write(2,1, '2', common_format)
	worksheet.write(2,2, '3', common_format)
	worksheet.write(2,3, '4', common_format)
	worksheet.write(2,4, '5', common_format)
	worksheet.write(2,5, '6', common_format)
	worksheet.write(2,6, '7', common_format)
	worksheet.write(3,0, '№', common_format)
	worksheet.write(3,1, 'Группа МЗП', common_format)
	worksheet.write(3,2, 'Код района', common_format)
	worksheet.write(3,3, 'Наименование', common_format)
	worksheet.write(3,4, 'Тип предприятия', common_format)
	worksheet.write(3,5, 'Общее количество сотрудников за которых поступили СО', common_format)
	worksheet.write(3,6, 'Общая сумма СО', common_format)


def do_report(file_name: str, date_first: str, date_second: str):
	if os.path.isfile(file_name):
		log.info(f'Отчет уже существует {file_name}')
		return file_name
	
	s_date = datetime.datetime.now().strftime("%H:%M:%S")

	log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, FILE_PATH: {file_name}')

	config = ConfigParser()
	config.read('db_config.ini')
	
	ora_config = config['rep_db_loader']
	db_user=ora_config['db_user']
	db_password=ora_config['db_password']
	db_dsn=ora_config['db_dsn']
	log.info(f'{report_code}. db_user: {db_user}, db_dsn: {db_dsn}')

	with oracledb.connect(user=db_user, password=db_password, dsn=db_dsn) as connection:
		with connection.cursor() as cursor:
			workbook = xlsxwriter.Workbook(file_name)

			title_format = workbook.add_format({'bg_color': '#D1FFFF', 'align': 'center', 'font_color': 'black'})
			#title_format = workbook.add_format({'bg_color': '#C5FFFF', 'align': 'center', 'font_color': 'black'})
			title_format.set_align('vcenter')
			title_format.set_border(1)
			title_format.set_text_wrap()
			title_format.set_bold()

			title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '14'})
			title_name_report .set_align('vcenter')
			title_name_report .set_bold()

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

			sum_pay_format = workbook.add_format({'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
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
			worksheet.append( workbook.add_worksheet(f'Список {page_num}') )
			sql_sheet = workbook.add_worksheet('SQL')
			merge_format = workbook.add_format({
				'bold':     False,
				'border':   6,
				'align':    'left',
				'valign':   'vcenter',
				'fg_color': '#FAFAD7',
				'text_wrap': True
			})
			sql_sheet.merge_range(f'A1:I{len(stmt_report.splitlines())}', f'{stmt_report}', merge_format)

			worksheet[page_num-1].activate()
			format_worksheet(worksheet=worksheet[page_num-1], common_format=title_format)

			worksheet[page_num-1].write(0, 0, report_name, title_name_report)
			worksheet[page_num-1].write(1, 0, f'За период: {date_first}', title_name_report)

			row_cnt = 1
			all_cnt=1
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
				return
			finally:
				log.info(f'REPORT: {report_code}. Выборка из курсора завершена')
			
			log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')

			records = []
			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 1
				worksheet[page_num-1].write(row_cnt+shift_row, 0, all_cnt, digital_format)
				for list_val in record:
					if col in (3,4):
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, region_name_format)
					if col in (1,2,5):
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, digital_format)
					if col in (6,):
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, money_format)
					col+= 1
				row_cnt+= 1
				cnt_part+= 1
				all_cnt+=1
				if (all_cnt//1000000) +1 > page_num:
					page_num=page_num+1
					row_cnt=1
					# ADD a new worksheet
					worksheet.append( workbook.add_worksheet(f'Список {page_num}') )
					# Formatting column and rows, ADD HEADERS
					format_worksheet(worksheet=worksheet[page_num-1], common_format=title_format)
					worksheet[page_num-1].write(0, 0, report_name, title_name_report)
					worksheet[page_num-1].write(1, 0, f'За период: {date_first} - {date_second}', title_name_report)
					

				if cnt_part > 250000:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			for i in range(page_num):
				# Шифр отчета
				worksheet[i].write(0, 5, report_code, title_report_code)
				worksheet[i].write(1, 5, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)

			workbook.close()
			set_status_report(file_name, 2)

			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {all_cnt} записей')


def thread_report(file_name: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
	threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


# def get_file_full_name(part_name, params):
# 	if 'date_first' in params:
# 		trunc_date = datetime.datetime.strptime(params['date_first'], '%Y-%m-%d').replace(day=1)
# 		str_trunc_date = datetime.datetime.strftime(trunc_date, '%Y-%m-%d')
# 		return f'{part_name}.{str_trunc_date}.xlsx'


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01.xlsx', '01.10.2022','31.10.2022')
