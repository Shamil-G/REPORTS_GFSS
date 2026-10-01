from configparser import ConfigParser
import xlsxwriter
import datetime
from   util.logger import log
import oracledb
import os.path
from   model.manage_reports import set_status_report
from util.trunc_date import get_month_name

report_name = 'Динамика численности получателей и сумм социальных выплат из АО "Государственный фонд социального страхования" по видам социальных рисков за '
report_code = 'DYN.9'

stmt_report = """
with dt as (select trunc(to_date(:dt_from,'YYYY-MM-DD'),'MM') dt_from from dual)
, r as (
select substr(d.rfpm_id, 1, 4) rfpm, 
       ap.riac_id,
       r.name,
       count(unique d.pncd_id) cnt
From pnpd_document d, pnap_act_prt_2 ap, riac_action r, dt
Where d.pncp_date = add_months(dt.dt_from, -1)
And   ap.act_month >= dt.dt_from 
And   ap.act_month < add_months(dt.dt_from, 1)
and   d.pncd_id=ap.pncd_id
And substr(d.rfpm_id,1,4) in ('0701','0702','0703','0705')
And d.ridt_id In (4,6, 7, 8)
And d.status In (0, 1, 2, 3, 5, 7) 
And d.pnsp_id > 0
and r.riac_id=ap.riac_id
Group By substr(d.rfpm_id, 1, 4), ap.riac_id, r.name
)
select * 
from 
(
select ' 1. численность получателей на начало месяца, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) cnt_0702,
       sum( case when rfpm='0701' then cnt else 0 end) cnt_0701,
       sum( case when rfpm='0703' then cnt else 0 end) cnt_0703,
       sum( case when rfpm='0705' then cnt else 0 end) cnt_0705
from (       
  select substr(d.rfpm_id, 1, 4) rfpm, count(unique d.pncd_id) cnt
  From pnpd_document d, dt
  Where d.pncp_date = add_months(dt.dt_from, -1) 
  And substr(d.rfpm_id,1,4) in ('0701','0702','0703','0705')
  And d.ridt_id In (4,6, 7, 8)
  And d.status In (0, 1, 2, 3, 5, 7) 
  And d.pnsp_id > 0
  Group By substr(d.rfpm_id, 1, 4)
)

union

select ' 2. Сумма выплат, тенге' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from (       
  select substr(d.rfpm_id, 1, 4) rfpm, sum(d.pay_sum + d.sum_debt) cnt
  From pnpd_document d, dt
  Where d.pncp_date = dt.dt_from
  And substr(d.rfpm_id,1,4) in ('0701','0702','0703','0705')
  And d.ridt_id In (4,6, 7, 8)
  And d.status In (0, 1, 2, 3, 5, 7) 
  And d.pnsp_id > 0
  Group By substr(d.rfpm_id, 1, 4)
)

union

select ' 3. назначение, человек*' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from ( 
  SELECT substr(sfa.rfpm_id,1,4) rfpm, 
      count(unique sfa.iin) cnt
  FROM sswh.sipr_maket_first_approve_2 sfa, dt
  WHERE substr(sfa.rfpm_id,1,4) in ('0701','0702','0703','0705')
  and sfa.date_approve >= dt.dt_from
  and sfa.date_approve < add_months(dt.dt_from, 1)
  group by substr(sfa.rfpm_id,1,4)
)

union

select ' 4. сумма социальных выплат для назначенных, тенге' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from ( 
  SELECT 
      substr(sfa.rfpm_id,1,4) rfpm, --"Код выплаты",
      sum(sfa.sum_all) cnt --"Назначенный размер, тенге"
  FROM sswh.sipr_maket_first_approve_2 sfa, dt
  WHERE substr(sfa.rfpm_id,1,4) in ('0701','0702','0703','0705')
  and sfa.date_approve >= dt.dt_from
  and sfa.date_approve < add_months(dt.dt_from, 1)
  group by substr(sfa.rfpm_id,1,4)
) 

union

select ' 5. смертность, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from r
where r.riac_id in (122)

union

select ' 6. прибывшие из-за пределов Республики Казахстан, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from r
where r.riac_id in (110)

union 

select ' 7. Убывшие за пределы Республики Казахстан, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from r
where r.riac_id in (150)

union 

select ' 8. восстановленные, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from r
where r.riac_id in (120, 121)

union 

select ' 9. снятые, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) sum_0702,
       sum( case when rfpm='0701' then cnt else 0 end) sum_0701,
       sum( case when rfpm='0703' then cnt else 0 end) sum_0703,
       sum( case when rfpm='0705' then cnt else 0 end) sum_0705
from r
where r.riac_id in (151, 152)

union 

select '10. численность выплат на конец месяца, человек' line, 
       sum( case when rfpm='0702' then cnt else 0 end) cnt_0702,
       sum( case when rfpm='0701' then cnt else 0 end) cnt_0701,
       sum( case when rfpm='0703' then cnt else 0 end) cnt_0703,
       sum( case when rfpm='0705' then cnt else 0 end) cnt_0705
from (       
  select substr(d.rfpm_id, 1, 4) rfpm, count(unique d.pncd_id) cnt
  From pnpd_document d, dt
  Where d.pncp_date = dt.dt_from
  And substr(d.rfpm_id,1,4) in ('0701','0702','0703','0705')
  And d.ridt_id In (4,6, 7, 8)
  And d.status In (0, 1, 2, 3, 5, 7) 
  And d.pnsp_id > 0
  Group By substr(d.rfpm_id, 1, 4)
)

) order by line

"""


def format_worksheet(worksheet, common_format, title_format, title_format_it, date_first):
	worksheet.set_row(0, 48)
	# worksheet.set_row(1, 24)
	worksheet.set_row(2, 48)
	#worksheet.set_row(3, 48)
	worksheet.set_row(5, 88)

	worksheet.set_column(0, 0, 64)
	worksheet.set_column(1, 1, 18)
	worksheet.set_column(2, 2, 18)
	worksheet.set_column(3, 3, 18)
	worksheet.set_column(4, 4, 18)

	worksheet.merge_range('D1:E1', 'Приложение №9 к Приказу Министра труда и социальной защиты населения Республики Казахстан от "18" мая 2023 года №158', title_format_it)
	worksheet.merge_range('A3:E3', f'Динамика числености поучателей и сумм социальных выплат из АО "Государственный фонд социального страхования" по видам социальных рисков за {get_month_name(date_first)} {date_first[0:4]}г.', common_format)

	worksheet.merge_range('A5:A6', 'Наименование', title_format)
	worksheet.merge_range('B5:E5', 'По видам социальных рисков', title_format)
	worksheet.write(5,1, '0702 - по случаю утраты трудоспособности', title_format)
	worksheet.write(5,2, '0701 - по случаю потери кормильца', title_format)
	worksheet.write(5,3, '0703 - по случаю потери работы', title_format)
	worksheet.write(5,4, '0705 - по случаю потери дохода в связи с уходом за ребенком по достижении им возраста 1,5 лет', title_format)

	worksheet.write(6,0, '1', title_format)
	worksheet.write(6,1, '2', title_format)
	worksheet.write(6,2, '3', title_format)
	worksheet.write(6,3, '4', title_format)
	worksheet.write(6,4, '5', title_format)


def do_report(file_name: str, date_first: str):
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

			title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '18'})
			title_name_report .set_align('vcenter')
			title_name_report .set_bold()

			title_format_it = workbook.add_format({'align': 'justify', 'font_size': '10', 'text_wrap': True })
			title_format_it.set_align('vcenter')
			title_format_it.set_italic()

			date_create_format = workbook.add_format({'align': 'right', 'font_size': '10'})
			date_create_format.set_align('vcenter')
			date_create_format.set_italic()

			common_format = workbook.add_format({'align': 'center', 'font_color': 'black', 'text_wrap': True, 'font_size': '18' })
			common_format.set_align('vcenter')
			# common_format.set_border(1)

			name_format = workbook.add_format({'align': 'left', 'font_color': 'black'})
			name_format.set_align('vcenter')
			name_format.set_border(1)

			sum_pay_format = workbook.add_format({'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
			sum_pay_format.set_border(1)

			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

			digital_format = workbook.add_format({'num_format': '### ### ##0', 'align': 'right'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			digital_format_center = workbook.add_format({'num_format': '### ### ##0', 'align': 'center'})
			digital_format_center.set_border(1)
			digital_format_center.set_align('vcenter')

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

			format_worksheet(worksheet=worksheet[page_num-1], common_format=common_format, title_format=title_format, title_format_it=title_format_it, date_first=date_first)

			# worksheet[page_num-1].write(0, 0, report_name, title_name_report)
			# worksheet[page_num-1].write(1, 0, f'За период: {date_first}', title_name_report)

			log.info(f'REPORT {report_code}. CREATING REPORT')

			try:
				cursor.execute(stmt_report, dt_from=date_first)
			except oracledb.DatabaseError as e:
				error, = e.args
				log.error(f"ERROR. REPORT {report_code}. error_code: {error.code}, error: {error.message}")
				log.info(f'\n---------\n{stmt_report}\n---------')
				set_status_report(file_name, 3)
				return
			finally:
				log.info(f'REPORT: {report_code}. Выборка из курсора завершена')
			
			log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')

			row_cnt = 1
			all_cnt = 0
			shift_row = 6
			cnt_part = 0

			records = []
			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 0
				start_char='1'
				for list_val in record:
					if isinstance(list_val, str): 
						start_char = list_val[0]
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, name_format)
					elif start_char in ('2','4'):
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, money_format)
					else:
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, digital_format)
					col+= 1
				row_cnt+= 1
				cnt_part+= 1


			stop_time = now.strftime("%H:%M:%S")
			worksheet[page_num-1].write(row_cnt+shift_row+1, 0, '* потребность на месяц', title_format_it)
			info = f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})'
			worksheet[page_num-1].write(row_cnt+shift_row+1, 4, info, date_create_format)

			workbook.close()

			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}), Загружено {all_cnt} записей')
			set_status_report(file_name, 2)


def thread_report(file_name: str, date_first: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
	threading.Thread(target=do_report, args=(file_name, date_first), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('test_dyn9.xlsx', '01.10.2022','31.10.2022')
