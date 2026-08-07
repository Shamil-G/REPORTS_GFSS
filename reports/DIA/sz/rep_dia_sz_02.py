from configparser import ConfigParser
import xlsxwriter
import datetime
import os.path
import oracledb
from   util.logger import log
from   model.manage_reports import set_status_report


report_name = 'Поступления от Самозанятых участников'
report_code = 'СЗ.02'

stmt_1 = """
      Select  
			to_char(20 + 5 * (width_bucket(g.let, 20, 65, 9) - 1 ) ) || 
			' - ' || 
			to_char((19 + 5 * (width_bucket(g.let, 20, 65, 9) ) ) )  as age,
            count(unique  case when sex = 0 then sicid else null end ) cnt_1w,
            sum( case when sex = 0 then g.sum_pay else 0 end ) sum1w,
            count(unique  case when sex = 1 then sicid else null end ) cnt_1m,
            sum( case when sex = 1 then g.sum_pay else 0 end ) sum1m
      from (select
                trunc(months_between(to_date(:dt_to, 'yyyy-mm-dd'), p.birthdate)/12) let,
                p.sex, si.sum_pay, p.sicid
            from  si_member_2 si, person p, rfrg_region rg
            where si.sicid = p.sicid
            and si.type_payer = 'SZ'
            and si.knp = '012'
            and si.pay_date_gfss >= to_date(:dt_from, 'yyyy-mm-dd') 
			and si.pay_date_gfss <  to_date(:dt_to, 'yyyy-mm-dd') + 1
            and si.pay_date_gfss  >= to_date('01.02.2023','dd.mm.yyyy')
            and si.pay_date		  >= to_date('01.02.2023','dd.mm.yyyy')
            and si.pay_date >= (to_date(:dt_from, 'yyyy-mm-dd') -  14)
            and si.pay_date <= to_date(:dt_to, 'yyyy-mm-dd')
			and substr(p.branchid,1,2) = rg.rfrg_id(+)
			and substr(p.branchid,1,2) = case when :id_region is null then substr(p.branchid,1,2) else :id_region end
      ) g
      group by 	to_char(20 + 5 * (width_bucket(g.let, 20, 65, 9) - 1 ) ) || 
			' - ' || 
			to_char((19 + 5 * (width_bucket(g.let, 20, 65, 9) ) ) )
      order by 1
"""

active_stmt = stmt_1

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 22)
	worksheet.set_row(3, 22)

	worksheet.set_column(0, 0, 8)
	worksheet.set_column(1, 1, 14)
	worksheet.set_column(2, 2, 10)
	worksheet.set_column(3, 3, 18)
	worksheet.set_column(4, 4, 10)
	worksheet.set_column(5, 5, 18)

	worksheet.merge_range('A3:A4', '№', common_format)
	worksheet.merge_range('B3:B4', 'Возраст', common_format)
	worksheet.merge_range('C3:C4', 'кол-во женщин', common_format)
	worksheet.merge_range('D3:D4', 'Сумма', common_format)
	worksheet.merge_range('E3:E4', 'кол-во мужчин', common_format)
	worksheet.merge_range('F3:F4', 'Сумма', common_format)

def do_report(file_name: str, date_first: str, date_second: str, rfbn_id: str):
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

			title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '13'})
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
			worksheet.write(1, 0, f'Период расчёта: с {date_first} по {date_second}', title_name_report)

			row_cnt = 1
			shift_row = 3
			cnt_part = 0
			m_val = [0]

			log.info(f'{file_name}. Загружаем данные с {date_first} по {date_second}')
			cursor.execute(active_stmt, dt_from=date_first,dt_to=date_second, id_region=rfbn_id)

			records = cursor.fetchall()
			
			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1,2,4):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col in (3,5):
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					col += 1
				cnt_part += 1
				if cnt_part > 9999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0
				row_cnt += 1

			#worksheet.write(row_cnt+shift_row, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)
			#worksheet.write(row_cnt + shift_row, 8, m_val[0], money_format)
			# Шифр отчета
			worksheet.write(0, 5, report_code, title_report_code)

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 5, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


def thread_report(file_name: str, date_first: str, date_second: str, rfbn_id: str):
	import threading
	log.info(f'THREAD REPORT. DATE BETWEEN REPORT: {date_first} - {date_second}, FILE_NAME: {file_name}, srfbn_id: {rfbn_id}')
	threading.Thread(target=do_report, args=(file_name, date_first, date_second, rfbn_id), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    #make_report('0701', '01.10.2022','31.10.2022')
    do_report('01.01.2023', '15.01.2023')
