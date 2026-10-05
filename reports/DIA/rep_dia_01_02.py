import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Получатели 0701, имеющие назначение по уходу за ребенком до 3-х лет, в статусе иждивенца'
report_code = 'DIA_01_02'

stmt_1 = """
	with sub_select_1 as (
	  select sfa2.sicid 
	  from (
		  select sicid 
		  from sipr_maket_first_approve_2 sfa
		  where substr(sfa.rfpm_id,1,4)='0701'
		  and sfa.date_approve >= :d1 AND sfa.date_approve <= :d2
		  intersect
		  select sicid 
		  from sipr_maket_first_approve_2 sfa2
		  where substr(sfa2.rfpm_id,1,4)='0705'
		  and sfa2.date_approve >= :d1 AND sfa2.date_approve <= :d2
	  ) sub_1, 
		sipr_maket_first_approve_2 sfa2,
		 pnpd_payment_dependant dep,
		 person ch
	  WHERE sfa2.sicid=sub_1.sicid
	  and   sfa2.pnpt_id=dep.pnpt_id
	  and   dep.sicid=ch.sicid
	  and substr(sfa2.rfpm_id,1,4)='0701'
	  and sfa2.date_approve >= :d1 AND sfa2.date_approve <= :d2
	  and months_between(to_date(:d2,'dd.mm.yyyy'),ch.birthdate) < 36
	)
	select * from
	(
    select sfa.rfbn_id, 
           sfa.rfpm_id, 
           (select p.iin from person p where p.sicid=s.sicid) R_IIN,
           ch.iin  CHILD_IIN,
           ch.sex CHILD_SEX,
           sfa.risk_date,
           sfa.date_approve,
           sfa.date_stop,
           sfa.sum_all,
		   sfa.pnpt_id
    from sipr_maket_first_approve_2 sfa, 
         sub_select_1 s,
         pnpd_payment_dependant dep,
         person ch
    where sfa.sicid=s.sicid
    and   sfa.pnpt_id=dep.pnpt_id
    and   dep.sicid=ch.sicid
    and substr(sfa.rfpm_id,1,4) = '0701'
    and sfa.date_approve >= :d1 AND sfa.date_approve <= :d2
    and months_between(:d2,ch.birthdate) < 36
	union
    select sfa.rfbn_id, 
           sfa.rfpm_id, 
           (select p.rn from person p where p.sicid=s.sicid) R_IIN,
           ch.rn  CHILD_IIN,
           ch.sex CHILD_SEX,
           sfa.risk_date,
           sfa.date_approve,
           sfa.date_stop,
           sfa.sum_all,
		   sfa.pnpt_id
    from sipr_maket_first_approve_2 sfa, 
         sub_select_1 s,
         ss_m_family mch,
         person ch
    where sfa.sicid=s.sicid
    and   sfa.sipr_id=mch.id_obj
    and   ch.sicid=mch.id_per
    and substr(sfa.rfpm_id,1,4) = '0705'
    and sfa.date_approve >= :d1 AND sfa.date_approve <= :d2
) order by R_IIN, rfpm_id
"""

active_stmt = stmt_1

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
			sql_sheet.merge_range('A1:I67', active_stmt, merge_format)

			worksheet.activate()
			format_worksheet(worksheet=worksheet, common_format=title_format)

			worksheet.write(0, 0, report_name, title_name_report)
			worksheet.write(1, 0, f'За период: {date_from} - {date_to}', title_name_report)

			cursor = connection.cursor()
			log.info(f'{file_name}. Загружаем данные за период {date_from} : {date_to}')

			cursor.execute(active_stmt, [date_from, date_to])

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
    make_report('0701', '01.01.2022','31.10.2022')
