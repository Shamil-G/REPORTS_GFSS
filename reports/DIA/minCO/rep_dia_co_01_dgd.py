from configparser import ConfigParser
import xlsxwriter
import datetime
from   util.logger import log
import oracledb
from  db.connect import _select
import os.path
from   model.manage_reports import set_status_report

report_name = 'Списочная часть по платежам, рассчитанным от дохода менее 1 МЗП (ДГД)'
report_code = 'minCO.01_dgd'

# 
#document.status:  0 - Документ сформирован на выплату, 1 - Сформирован платеж, 2 - Платеж на выплате
stmt_load = "begin sswh.load_min_so_history.make; end;"

stmt_report = """
	with src as (
	select /*+ parallel(4) */
	  nvl(k.rfbn_id, 'нет') rfbn_area, --Код района
	  k.name_ru name_area,  --Район
	  m.p_rnn,        --БИН/ИИН предприятия
	  nvl(o.nm_ru, 'Неопределено') name_org, --Наименование предприятия
	  m.cnt_worker,     -- Общее количество сотрудников
	  p.iin,
	  p.sicid,
	  m.PAY_MONTH,
	  m.sum_pay,
	  sswh.min_so(m.PAY_MONTH) as base_size,
	  sswh.min_so(m.PAY_MONTH) - m.sum_pay as debt
	from min_so_history m, 
	   person p,
	   rfon_organization o,
	   cato_branch k
	where trunc(m.ctrl_date,'MM')=trunc(to_date(:control_month,'YYYY-MM-DD'),'MM')
	and   trunc(m.pay_month,'MM') >= add_months(trunc(m.ctrl_date,'MM'), -13)
	and   m.p_rnn = o.bin(+)
	and   m.sicid = p.sicid
	and   substr(o.cato,1,4)=substr(k.reg_code,1,4)
	and   k.lev=2
	)
	, uniq_src as(
	select /*+ parallel(4) */
		   unique sicid, 
		   p_rnn, 
		   trunc(src.pay_month,'YYYY') pay_month_year
	from src
	)
	, add_info as (
	select /*+ parallel(4) */
		   count(unique si.pay_month) all_pay_month, 
		   sum(si.sum_pay) sum_pay_year,
		   src.pay_month_year,
		   si.p_rnn, si.sicid
	from uniq_src src, si_member_2 si
	where src.p_rnn=si.p_rnn
	and si.knp='012'
	and src.sicid=si.sicid
	and si.pay_date>=add_months(src.pay_month_year, -13)
	and trunc(si.pay_month,'YYYY')=src.pay_month_year
	group by si.p_rnn, si.sicid, src.pay_month_year
	)
	select rownum as "№", t.*
	from(
		select /*+ parallel(4) */
		  src.rfbn_area as "Код области",
		  src.name_area "Наименование района",
		  src.p_rnn "БИН",
		  src.name_org "Наименование предприятия", 
		  src.cnt_worker "Общее количество сотрудников за которых поступили СО",
		  src.iin "ИИН сотрудника",
		  src.PAY_MONTH "Период платежа",
		  src.sum_pay "Платежи менее 1 МЗП, за период",
		  src.base_size "Мин. ставка СО",
		  src.debt "Недоплачено до мин.ставки СО 11=(10-9)",
		  a.all_pay_month "Количесво периодов", 
		  a.sum_pay_year "Сумма СО (за год)"
		from src, add_info a
		where src.p_rnn=a.p_rnn
		and   src.sicid=a.sicid
		and   trunc(src.pay_month,'YYYY')=a.pay_month_year
		order by src.rfbn_area, src.p_rnn, src.iin
	) t
	"""


HEADER_ROW = 2
DATA_START_ROW = HEADER_ROW + 2
LINE_HEIGHT = 15


def format_worksheet(worksheet, record, title_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 40)
	worksheet.set_row(3, 12)

	list_column_width =[7,9,32,14,120,20,14,12, 14, 12,16, 16, 18]

	for col_num, column_name in enumerate(record):
		worksheet.write(HEADER_ROW, col_num, column_name, title_format)
		worksheet.write(HEADER_ROW+1, col_num, col_num, title_format)
		worksheet.set_column(col_num, col_num, list_column_width[col_num])


def do_report(file_name: str, date_first: str):
	log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, FILE_PATH: {file_name}')
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

			now = datetime.datetime.now()
			log.info(f'Начало формирования {file_name}: {now.strftime("%d-%m-%Y %H:%M:%S")}')

			params = {'control_month': date_first}

			records = _select(stmt_report, cursor, params)
			if len(records) == 0:
				set_status_report(file_name, 3)
				return

			workbook = xlsxwriter.Workbook(file_name)

			title_name_report = workbook.add_format({ "align": "left", "font_color": "black", "font_size": "14", "valign": "vcenter", "bold": True	})
			title_format_it = workbook.add_format({	"align": "right", "valign": "vcenter", "italic": True })
			title_format = workbook.add_format({'bg_color': '#D1FFFF', 'align': 'center', 'font_color': 'black', 'bold': True, 'valign': 'vcenter', 'border': 1, 'text_wrap': True})

			number_format = workbook.add_format({'num_format': '#0', "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2" })
			money_format = workbook.add_format({'num_format': '# ### ### ##0.00', 'align': 'right', 'border': 1, "valign": "vcenter", })

			date_format = workbook.add_format({	"num_format": "dd.mm.yyyy", "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2" })

			text_format = workbook.add_format({ "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2" })
			text_format_center = workbook.add_format({"num_format": '@', "text_wrap": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2"})

			list_format = workbook.add_format({ "text_wrap": True, "align": "left", "valign": "vcenter", "border": 1 })

			title_report_code = workbook.add_format({'align': 'right', 'font_size': '14', "valign": "vcenter", 'bold': True, })

			page_num = 1
			worksheet = []
			# ADD a new worksheet for SQL
			worksheet.append( workbook.add_worksheet(f'Список {page_num}') )
			sql_sheet = workbook.add_worksheet('SQL')
			sql_text_format = workbook.add_format({ 'bold': False, 'border': 6, 'align': 'left', 'valign': 'vcenter', 'fg_color': '#FAFAD7', 'text_wrap': True })
			sql_sheet.merge_range(f'A1:I{len(stmt_report.splitlines())}', f'{stmt_report}', sql_text_format)
			### END ADD a new worksheet for SQL

			worksheet[page_num-1].activate()
			format_worksheet(worksheet=worksheet[page_num-1], record=records[0], title_format=title_format)

			worksheet[page_num-1].write(0, 0, report_name, title_name_report)
			worksheet[page_num-1].write(1, 0, f'За период: {date_first}', title_name_report)

			list_name_number = ["Общее количество сотрудников за которых поступили СО", "Количесво периодов", ]
			list_name_date = ['Период платежа']
			list_name_text = ["Наименование предприятия", "Наименование района","ФИО спикера", "Исполнитель", "Адрес ИРР"]
			list_name_text_list = ["Партнеры"]
			list_name_text_center = ["№", "Код области", "БИН", "ИИН сотрудника", "Мин. ставка СО"]
			list_money = ["Платежи менее 1 МЗП, за период", "Недоплачено до мин.ставки СО 11=(10-9)", "Сумма СО (за год)"]

			row_cnt=0
			all_cnt=1
			cnt_part = 0

			log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')
			### ЗАПИСЬ
			for row_num, record in enumerate(records):
				for col_num, (column_name, value) in enumerate(record.items()):
					if any(column_name.lower() in name.lower() for name in list_name_date):
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, value, date_format )
					if any(column_name.lower() in name.lower() for name in list_name_number):
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, float(value), number_format )
					if any(column_name.lower() in name.lower() for name in list_money):
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, value, money_format )
					if any(column_name.lower() in name.lower() for name in list_name_text):
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, value, text_format )
					if any(column_name.lower() in name.lower() for name in list_name_text_center):
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, value, text_format_center )
					if any(column_name.lower() in name.lower() for name in list_name_text_list):
						text='\n'.join(value)
						worksheet[page_num-1].write( DATA_START_ROW + row_num, col_num, text, list_format )

				row_cnt+=1
				cnt_part+= 1
				all_cnt+=1
				if (all_cnt//1000000) +1 > page_num:
					page_num=page_num+1
					row_cnt=1
					# ADD a new worksheet
					worksheet.append( workbook.add_worksheet(f'Список {page_num}') )
					# Formatting column and rows, ADD HEADERS
					format_worksheet(worksheet=worksheet[page_num-1], record=records[0], title_format=title_format)
					worksheet[page_num-1].write(0, 0, report_name, title_name_report)
					worksheet[page_num-1].write(1, 0, f'За период: {date_first}', title_name_report)

				if cnt_part > 24999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			for i in range(page_num):
				# Шифр отчета
				worksheet[i].write(0, 9, report_code, title_report_code)
				worksheet[i].write(1, 9, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)

			workbook.close()
			set_status_report(file_name, 2)
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {all_cnt} записей')


def thread_report(file_name: str, date_first: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
	threading.Thread(target=do_report, args=(file_name, date_first), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_01_dgd.xlsx', '01.10.2022','31.10.2022')
