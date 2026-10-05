from configparser import ConfigParser
# from   db_config import report_db_user, report_db_password, report_db_dsn
import xlsxwriter
import datetime
import os.path
import oracledb
from   util.logger import log
from   model.call_report import set_status_report


report_name = 'Получатели СВбр и СВур, у которых между датами назначения есть СВпр'
report_code = '1504.01'

stmt_1 = """
		select sfa.rfbn_id, sfa.rfpm_id, sfa.iin,
			   t05.risk_date_0704, sfa.risk_date, t05.risk_date_0705,
			   t05.sum_all_0704, sfa.sum_all, t05.sum_all_0705,
			   t05.sum_avg_0705, t05.ksu_0704 
		from sipr_maket_first_approve_2 sfa,
			 (
				select t04.*, sfa.risk_date as risk_date_0705, 
					   sfa.sum_avg as sum_avg_0705, 
					   sfa.sum_all as sum_all_0705
				from sipr_maket_first_approve_2 sfa,
				(
				select rfbn_id, 
					   rfpm_id, 
					   iin, 
					   risk_date risk_date_0704, 
					   sum_avg as sum_avg_0704, 
					   sum_all as sum_all_0704,
					   ksu as ksu_0704
				from sipr_maket_first_approve_2 sfa
				where substr(sfa.rfpm_id,1,4) = '0704'
				and   sfa.risk_date >= trunc(to_date(:date_first,'YYYY-MM-DD'), 'MM') AND sfa.risk_date < trunc(to_date(:date_second,'YYYY-MM-DD'), 'MM') + 1
				--and   trunc(sfa.risk_date) = trunc(to_date('2021-03-01','YYYY-MM-DD'), 'MM')
				) t04
				where sfa.iin=t04.iin
				and   substr(sfa.rfpm_id,1,4) = '0705'
				and   sfa.risk_date > t04.risk_date_0704
				and   sfa.risk_date < add_months(t04.risk_date_0704, 20)
			  ) t05
		where sfa.iin=t05.iin
		and   substr(sfa.rfpm_id,1,4) = '0703'
		and   sfa.risk_date >= t05.risk_date_0704
		and   sfa.risk_date <= add_months(t05.risk_date_0705,6)
"""

active_stmt = stmt_1

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 22)
	worksheet.set_row(3, 22)

	worksheet.set_column(0, 0, 8)
	worksheet.set_column(1, 1, 14)
	worksheet.set_column(2, 2, 14)
	worksheet.set_column(3, 3, 14)
	worksheet.set_column(4, 4, 12)
	worksheet.set_column(5, 5, 12)
	worksheet.set_column(6, 6, 12)
	worksheet.set_column(7, 7, 14)
	worksheet.set_column(8, 8, 14)
	worksheet.set_column(9, 9, 14)
	worksheet.set_column(10, 10, 14)
	worksheet.set_column(11, 11, 8)


	worksheet.merge_range('A3:A4', '№', common_format)
	worksheet.merge_range('B3:B4', 'Код региона', common_format)
	worksheet.merge_range('C3:C4', 'Код выплаты', common_format)
	worksheet.merge_range('D3:D4', 'ИИН получателя', common_format)
	worksheet.merge_range('E3:E4', 'Дата риска СВбр', common_format)
	worksheet.merge_range('F3:F4', 'Дата риска СВпр', common_format)
	worksheet.merge_range('G3:G4', 'Дата риска СВур', common_format)
	worksheet.merge_range('H3:H4', 'Размер СВбр', common_format)
	worksheet.merge_range('I3:I4', 'Размер СВпр', common_format)
	worksheet.merge_range('J3:J4', 'Размер СВур', common_format)
	worksheet.merge_range('K3:K4', 'СМД при СВбр', common_format)
	worksheet.merge_range('L3:L4', 'КСУ', common_format)

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

			worksheet.write(0, 0, report_name, title_name_report)
			worksheet.write(1, 0, f'Период расчёта: {date_first} - {date_second}', title_name_report)

			row_cnt = 1
			shift_row = 3
			cnt_part = 0
			m_val = [0]

			log.info(f'{file_name}. Загружаем данные за период {date_first} - {date_second}')
			cursor.execute(active_stmt, date_first=date_first, date_second=date_second)

			records = cursor.fetchall()
			
			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1,2,3):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col in (4,5,6):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col in (7,8,9,10,11):
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					col += 1
				cnt_part += 1
				if cnt_part > 9999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0
				row_cnt += 1

			#worksheet.write(row_cnt+shift_row, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)
			#worksheet.write(row_cnt + shift_row, 8, m_val[0], money_format)
			worksheet.write(0, 10, report_code, title_report_code)

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 10, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


def thread_report(file_name: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. DATE FOR REPORT: {date_first} - {date_second}, FILE_NAME: {file_name}')
	threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('01.01.2023')
