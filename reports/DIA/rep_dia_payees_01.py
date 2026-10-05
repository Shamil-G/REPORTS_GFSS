import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

# Принят 14 января 2022, помесячно отчет соответствует, за год расхождение
report_name = 'Списочная часть получателей по видам выплат с количеством СО'
stmt_1 = """
with su_count as(
select /*+ full(si) */ 
       count(unique si.period) cnt, 
       pd.source_id
from si_member_2 si, 
     pnpd_document pd
where si.sicid=pd.pncd_id
and   substr(pd.rfpm_id,1,4) = :p1
and   pd.pncp_date >= :d1 AND pd.pncp_date <= :d2
and   si.pay_date <= :d1
and   pd.status = 2 
and   pd.knp=case when :p1 = '0704' then '096'
				  when :p1 = '0705' then '091'	
                  else '000' end
group by pd.source_id
)
select sfa.rfbn_id,
       sfa.rfpm_id,
       p1.iin R_IIN,
       sfa.risk_date,
       sfa.date_approve,
       sfa.sum_all,
	   sfa.sum_avg,
       su.cnt,
       ksu 
from sipr_maket_first_approve_2 sfa,
     person p1, su_count su
where sfa.sicid=p1.sicid
and   su.source_id=sfa.pnpt_id(+)
and   substr(sfa.rfpm_id,1,4) = :p1
order by rfbn_id, rfpm_id, p1.rn
"""


stmt_2 = """
with su_count as(
select /*+ full(si) */ 
       count(unique trunc(si.pay_date,'MM')) cnt, 
       pd.source_id
from si_member_2 si, 
     pnpd_document pd
where si.sicid=pd.pncd_id
and   substr(pd.rfpm_id,1,4) = :p1
and   pd.pncp_date >= :d1 AND pd.pncp_date <= :d2
and   si.pay_date <= :d1
and   pd.status = 2 
and   pd.knp=case when :p1 = '0704' then '096'
				  when :p1 = '0705' then '091'	
                  else '000' end
group by pd.source_id
)
select sfa.rfbn_id,
       sfa.rfpm_id,
       p1.iin R_IIN,
       sfa.risk_date,
       sfa.date_approve,
       sfa.sum_all,
	   sfa.sum_avg,
       su.cnt,
       ksu 
from sipr_maket_first_approve_2 sfa,
     person p1, su_count su
where sfa.sicid=p1.sicid
and   su.source_id=sfa.pnpt_id(+)
and   substr(sfa.rfpm_id,1,4) = :p1
order by rfbn_id, rfpm_id, p1.rn
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
	worksheet.set_column(7, 7, 14)
	worksheet.set_column(8, 8, 14)
	worksheet.set_column(9, 9, 14)
	worksheet.set_column(10, 10, 16)	

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'Код региона', common_format)
	worksheet.write(2, 2, 'Код выплаты', common_format)
	worksheet.write(2, 3, 'ИИН получателя', common_format)
	worksheet.write(2, 4, 'Дата риска', common_format)
	worksheet.write(2, 5, 'Дата назначения', common_format)
	worksheet.write(2, 6, 'Размер СВ', common_format)
	worksheet.write(2, 7, 'СМД', common_format)
	worksheet.write(2, 8, 'СУ (кол-во месяцев)', common_format)
	worksheet.write(2, 9, 'Кол-во дней нетрудоспособности', common_format)


def make_report(rfpm_id: str, date_from: str, date_to: str):
	report_code = f'DIA_ALL_MEMBER_{rfpm_id}_01'

	file_name = f'{report_code}_{rfpm_id}_{date_from}_{date_to}.xlsx'
	file_path = f'{file_name}'

	print(f'MAKE REPORT started...')
	if os.path.isfile(file_path):
		print(f'Отчет уже существует {file_name}')
		log.info(f'Отчет уже существует {file_name}')
		return file_name

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

	cx_Oracle.init_oracle_client(lib_dir='c:/instantclient_21_3')
	#cx_Oracle.init_oracle_client(lib_dir='/home/aktuar/instantclient_21_8')
	with cx_Oracle.connect(user='sswh', password='sswh', dsn="172.16.17.12/gfss", encoding="UTF-8") as connection:
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
				if col in (1,2,3):
					worksheet.write(row_cnt+shift_row, col, list_val, common_format)
				if col in (4,5):
					worksheet.write(row_cnt+shift_row, col, list_val, date_format)
				if col in (6,7):
					worksheet.write(row_cnt+shift_row, col, list_val, money_format)
				if col in (8,9):
					worksheet.write(row_cnt+shift_row, col, list_val, num_format)
				col += 1
			row_cnt += 1
			cnt_part += 1
			if cnt_part > 9999:
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
    #make_report('0704', '01.01.2022','31.12.2022')
    #make_report('0704', '01.01.2022','31.01.2022')
    #make_report('0704', '01.06.2022','30.06.2022')
    make_report('0704', '01.12.2022','31.12.2022')
