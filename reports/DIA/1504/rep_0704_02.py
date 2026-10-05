from configparser import ConfigParser
# from   db_config import report_db_user, report_db_password, report_db_dsn
import xlsxwriter
import datetime
import os.path
import oracledb
from   util.logger import log
from   model.call_report import set_status_report

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Получатели СВбр'
report_code = '1504.02'

stmt_create = """
select  unique rfbn_id, iin, 
  age,
  risk_date, date_approve, stopdate, 
  ksu, sum_avg, sum_all
from (              
  SELECT 
        p.iin as "IIN",
		floor( months_between(sipr.risk_date, p.birthdate) / 12 ) age,
		FIRST_VALUE(pp.rfbn_id) OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) rfbn_id,
		sipr.risk_date,
		sipr.date_approve, 
		sipr.date_stop AS STOPDATE, 
		sipr.ksu, 
		sipr.sum_avg, 
		sipr.sum_all
  FROM  PNPD_DOCUMENT D, 
		sipr_maket_first_approve_2 sipr,
		PNPT_PAYMENT PP, person p
  WHERE D.SOURCE_ID = PP.PNPT_ID(+)
  and   d.source_id = sipr.pnpt_id(+)
  and   d.pncd_id = p.sicid
  AND   coalesce(D.KNP,'000')!='010'
  AND   D.PNCP_DATE >= to_date(:date_first,'YYYY-MM-DD') AND D.PNCP_DATE <= to_date(:date_second,'YYYY-MM-DD')
  AND   substr(D.RFPM_ID,1,4) = '0704'
  AND   D.RIDT_ID IN (4, 6, 7, 8)
  AND   D.STATUS IN (0, 1, 2, 3, 5, 7)
  AND   D.PNSP_ID > 0
)  
order by rfbn_id, iin
"""

active_stmt = stmt_create

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 28)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 24)
	worksheet.set_row(3, 24)

	worksheet.set_column(0, 0, 9)
	worksheet.set_column(1, 1, 14)
	worksheet.set_column(2, 2, 14)
	worksheet.set_column(3, 3, 8)
	worksheet.set_column(4, 4, 12)
	worksheet.set_column(5, 5, 12)
	worksheet.set_column(6, 6, 12)
	worksheet.set_column(7, 7, 8)
	worksheet.set_column(8, 8, 16)
	worksheet.set_column(9, 9, 16)

	worksheet.merge_range('A3:A4', '№', common_format)
	worksheet.merge_range('B3:B4', 'Код региона', common_format)
	worksheet.merge_range('C3:C4', 'ИИН получателя', common_format)
	worksheet.merge_range('D3:D4', 'Возраст', common_format)
	worksheet.merge_range('E3:E4', 'Дата риска', common_format)
	worksheet.merge_range('F3:F4', 'Дата назначения', common_format)
	worksheet.merge_range('G3:G4', 'Дата окончания', common_format)
	worksheet.merge_range('H3:H4', 'КСУ', common_format)
	worksheet.merge_range('I3:I4', 'СМД', common_format)
	worksheet.merge_range('J3:J4', 'Сумма первой назначенной выплаты', common_format)
	

def do_report(file_name: str, date_first: str, date_second: str):
	if os.path.isfile(file_name):
		log.info(f'Отчет уже существует {file_name}')
		return file_name

	s_date = datetime.datetime.now().strftime("%H:%M:%S")

	log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, DATE_TO: {date_second}, FILE_PATH: {file_name}')
	
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

			title_format = workbook.add_format({'align': 'center', 'valign': 'vcenter', 'font_color': 'black'})
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

			sum_pay_format = workbook.add_format({'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
			sum_pay_format.set_border(1)

			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

			digital_format = workbook.add_format({'num_format': '# ### ##0', 'align': 'center'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			money_format_center = workbook.add_format({'num_format': '# ### ##0.00', 'align': 'center'})
			money_format_center.set_border(1)
			money_format_center.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '# ### ### ### ##0.00', 'align': 'right'})
			money_format.set_border(1)
			money_format.set_align('vcenter')

			now = datetime.datetime.now()
			log.info(f'Начало формирования {file_name}: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			worksheet = workbook.add_worksheet('Список')
			sql_sheet = workbook.add_worksheet('SQL')
			merge_format = workbook.add_format({
				'bold':     False,
				'border':   6,
				'align':    'left',
				'valign':   'vcenter',
				'fg_color': '#FAFAD7',
				'text_wrap': True
			})
			sql_sheet.merge_range('A1:I35', active_stmt, merge_format)

			worksheet.activate()
			format_worksheet(worksheet=worksheet, common_format=title_format)

			worksheet.write(0, 0, f'{report_name} : 0704', title_name_report)
			worksheet.write(1, 0, f'За период: {date_first} - {date_second}', title_name_report)

			row_cnt = 1
			shift_row = 3
			cnt_part = 0
			m_val = [0]

			log.info(f'{file_name}. Загружаем данные за период {date_first} - {date_second}')
			cursor.execute(active_stmt, date_first=date_first, date_second=date_second)

			records = cursor.fetchall()

# unique rfbn_id, iin, 
#   age,
#   risk_date, date_approve, stopdate, 
#   ksu, real_ksu, sum_avg, sum_all


			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1,2,3,7):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col in (4,5,6):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col in (8,9):
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					col += 1
				cnt_part += 1
				if cnt_part > 49999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0
				row_cnt += 1

			#
			worksheet.write(0, 9, report_code, title_report_code)

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 9, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


# def get_file_path(file_name: str, date_first: str, date_second: str):
# 	full_file_name = f'{file_name}.{report_code}.{date_first}-{date_second}.xlsx'
# 	return full_file_name


def thread_report(file_name: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: rfpm_id: 0702, date_first: {date_first}, date_second: {date_second}')
	threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    #make_report('0701', '01.10.2022','31.10.2022')
    do_report('01.01.2023')
