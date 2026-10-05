import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Получатели выплат 0701 старше 18 лет'
report_code = 'DIA_01_03'

stmt1 = """
	select unique first_value(doc.rfbn_id) over(partition by pt.pnpt_id order by doc.pncp_date desc) rfbn_id,
			first_value(doc.rfpm_id) over(partition by pt.pnpt_id order by doc.pncp_date desc) rfpm_id,
			p1.iin R_IIN,
			p2.iin DEP_IIN,
			sfa.appointdate,
			sfa.approvedate,
			pt.sum_pay,
			first_value(doc.pncp_date) over(partition by pt.pnpt_id order by doc.pncp_date desc) last_pay_date,
			first_value(doc.pnpd_id) over(partition by doc.source_id, pd.sicid order by doc.pncp_date desc) last_pnpd_id,
			doc.pncd_id r_sicid,
			pd.sicid dep_sicid
	from sipr_maket_first_approve sfa,
			pnpd_document doc,
			pnpd_payment_dependant pd,
			person p1,
			person p2
	where sfa.sicid=doc.sicid
	and doc.pncd_id=p1.sicid
	and pt.pnpt_id=pd.pnpt_id(+)
	and pd.sicid=p2.sicid(+)
	and substr(sfa.rfpm_id,1,4) = :p1
	and doc.pncp_date >= :d1 AND doc.pncp_date <= :d2
	order by rfbn_id, rfpm_id, doc.pncd_id
"""


stmt_2 = """
select sfa.rfbn_id,
      sfa.rfpm_id,
      p1.iin R_IIN,
      p2.iin DEP_IIN,
      case when p1.sex=0 then 'Ж' else 'М' end sex,
      sfa.risk_date,
      sfa.date_approve,
      sfa.date_stop,
      sfa.sum_all,
      sfa.sicid r_sicid,
      pd.sicid dep_sicid
  from sipr_maket_first_approve_2 sfa,
      pnpd_payment_dependant pd,
      person p1,
      person p2
  where sfa.pnpt_id=pd.pnpt_id 
  and sfa.sicid=p1.sicid(+)
  and pd.sicid=p2.sicid(+)
  and substr(sfa.rfpm_id,1,4) = :p1
  and sfa.date_approve >= :d1 AND sfa.date_approve <= :d2
  and sfa.date_stop > :d1  
  and MONTHS_BETWEEN(:d1, coalesce(p2.birthdate,sysdate))/12 >= 18
  and MONTHS_BETWEEN(:d2, coalesce(p2.birthdate,sysdate))/12 < 23
  order by rfbn_id, rfpm_id, sfa.sicid
"""

active_stmt = stmt_2

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)

	worksheet.set_column(0, 0, 7)
	worksheet.set_column(1, 1, 10)
	worksheet.set_column(2, 2, 12)
	worksheet.set_column(3, 3, 14)
	worksheet.set_column(4, 4, 14)
	worksheet.set_column(5, 5, 12)
	worksheet.set_column(6, 6, 12)
	worksheet.set_column(7, 7, 12)
	worksheet.set_column(8, 8, 14)
	worksheet.set_column(9, 9, 12)
	worksheet.set_column(10, 10, 12)	
	worksheet.set_column(11, 11, 12)

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'Код региона', common_format)
	worksheet.write(2, 2, 'Код выплаты', common_format)
	worksheet.write(2, 3, 'ИИН получателя', common_format)
	worksheet.write(2, 4, 'ИИН иждивенца', common_format)
	worksheet.write(2, 5, 'Пол', common_format)
	worksheet.write(2, 6, 'Дата риска', common_format)
	worksheet.write(2, 7, 'Дата назначения', common_format)
	worksheet.write(2, 8, 'Дата окончания', common_format)
	worksheet.write(2, 9, 'Размер СВ', common_format)


def make_report(rfpm_id: str, date_from: str, date_to: str):
	file_name = f'{report_code}_{rfpm_id}_{date_from}_{date_to}.xlsx'
	file_path = f'{file_name}'

	print(f'MAKE REPORT started...')
	if os.path.isfile(file_path):
		print(f'Отчет уже существует {file_name}')
		log.info(f'Отчет уже существует {file_name}')
		return file_name
	else:
		cx_Oracle.init_oracle_client(lib_dir='c:/instantclient_21_3')
		#cx_Oracle.init_oracle_client(lib_dir='/home/aktuar/instantclient_21_8')
		with cx_Oracle.connect(user='sswh', password='sswh', dsn="172.16.17.12/gfss") as connection:
			workbook = xlsxwriter.Workbook(file_path)

			title_format = workbook.add_format({'align': 'center', 'font_color': 'black'})
			title_format.set_align('vcenter')
			title_format.set_border(1)
			title_format.set_text_wrap()
			title_format.set_bold()

			title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '14'})
			title_name_report.set_align('vcenter')
			title_name_report.set_bold()

			title_sql = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '12'})
			title_sql.set_align('vcenter')
			title_sql.set_text_wrap()
			
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

			num_format = workbook.add_format({'num_format': '#0', 'align': 'right'})
			num_format.set_border(1)
			num_format.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '# ### ##0', 'align': 'right'})
			money_format.set_border(1)
			money_format.set_align('vcenter')

			now = datetime.datetime.now()
			log.info(f'Начало формирования {report_name}: {now.strftime("%d-%m-%Y %H:%M:%S")}')

			worksheet = workbook.add_worksheet('Отчёт')
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
			worksheet.write(1, 0, f'За период: {date_from} - {date_to}', title_name_report)

			cursor = connection.cursor()
			log.info(f'{file_name}. Загружаем данные за период {date_from} : {date_to}')
			cursor.execute(active_stmt, [rfpm_id, date_from, date_to])

			row_cnt = 1
			shift_row = 2
			cnt_part = 0

			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1,2,3,4):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col in (5,):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col in (6,7,8):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col == 9:
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					if col in (10,11):
						worksheet.write(row_cnt+shift_row, col, list_val, num_format)
					col += 1
				row_cnt += 1
				cnt_part += 1
				if cnt_part > 999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0

			#worksheet.write(row_cnt+1, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)
			workbook.close()
			now = datetime.datetime.now()
			log.info(f'Формирование отчета {report_name} завершено: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			return file_name


if __name__ == "__main__":
    log.info(f'Отчет {report_name} запускается.')
    #make_report('0701', '01.10.2022','31.10.2022')
    make_report('0701', '01.10.2022','31.10.2022')
