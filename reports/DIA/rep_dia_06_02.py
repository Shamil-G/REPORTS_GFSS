# Получатели выплат, имеющие одновременно СО
import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Получатели выплат, имеющие одновременно СО'
report_code = 'DIA_06_02'

stmt_1 = """
select b.sicid,
       p.iin,
--       last_appoint_date,
       sum(case when num_month = 0 then 1 else 0 end) month_pd0,
       sum(case when num_month = 1 then 1 else 0 end) month_pd1,
       sum(case when num_month = 2 then 1 else 0 end) month_pd2,
       sum(case when num_month = 3 then 1 else 0 end) month_pd3,
       sum(case when num_month = 4 then 1 else 0 end) month_pd4,
       sum(case when num_month = 5 then 1 else 0 end) month_pd5,
       sum(case when num_month = 6 then 1 else 0 end) month_pd6,
       sum(case when num_month = 7 then 1 else 0 end) month_pd7,
       sum(case when num_month = 8 then 1 else 0 end) month_pd8,
       sum(case when num_month = 9 then 1 else 0 end) month_pd9,
       sum(case when num_month = 10 then 1 else 0 end) month_pd10,
       sum(case when num_month = 11 then 1 else 0 end) month_pd11,
       sum(case when num_month = 12 then 1 else 0 end) month_pd12
from (
  select unique si.sicid,
         extract(month from si.pay_date) num_month
  from si_member_2 si,
  (
    select unique pd.pncd_id as sicid,
           first_value(pd.pncp_date) over(partition by pd.pncd_id order by pd.pncp_date desc) last_pncp_date,
           first_value(pt.appointdate) over(partition by pt.pncd_id order by pt.appointdate desc) last_appoint_date
    from pnpd_document pd, pnpt_payment pt
    where substr(pd.rfpm_id,1,4)=:p1
	and  pd.pncp_date >= :d1 AND pd.pncp_date <= :d2
    and  pt.pncd_id=pd.pncd_id
  ) a
  where a.sicid=si.sicid
  and   si.pay_date >= :d1 AND si.pay_date <= :d2
  and   si.pay_date >= last_appoint_date
  and   si.pay_date <= last_pncp_date
) b, person p
where b.sicid=p.sicid
group by b.sicid, p.iin
"""

active_stmt = stmt_1

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)

	worksheet.set_column(0, 0, 7)
	worksheet.set_column(1, 1, 12)
	worksheet.set_column(2, 2, 14)
	worksheet.set_column(3, 3, 10)
	worksheet.set_column(4, 4, 10)
	worksheet.set_column(5, 5, 10)
	worksheet.set_column(6, 6, 10)
	worksheet.set_column(7, 7, 10)
	worksheet.set_column(8, 8, 10)
	worksheet.set_column(9, 9, 10)
	worksheet.set_column(10, 10, 10)
	worksheet.set_column(11, 11, 10)
	worksheet.set_column(12, 12, 10)
	worksheet.set_column(13, 13, 10)
	worksheet.set_column(14, 14, 10)
	worksheet.set_column(15, 15, 10)

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'SICID', common_format)
	worksheet.write(2, 2, 'ИИН', common_format)
	worksheet.write(2, 3, 'Месяц 0', common_format)
	worksheet.write(2, 4, 'Месяц 1', common_format)
	worksheet.write(2, 5, 'Месяц 2', common_format)
	worksheet.write(2, 6, 'Месяц 3', common_format)
	worksheet.write(2, 7, 'Месяц 4', common_format)
	worksheet.write(2, 8, 'Месяц 5', common_format)
	worksheet.write(2, 9, 'Месяц 6', common_format)
	worksheet.write(2, 10, 'Месяц 7', common_format)
	worksheet.write(2, 11, 'Месяц 8', common_format)
	worksheet.write(2, 12, 'Месяц 9', common_format)
	worksheet.write(2, 13, 'Месяц 10', common_format)
	worksheet.write(2, 14, 'Месяц 11', common_format)
	worksheet.write(2, 15, 'Месяц 12', common_format)


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
			title_name_report .set_align('vcenter')
			title_name_report .set_bold()

			common_format = workbook.add_format({'align': 'center', 'font_color': 'black'})
			common_format.set_align('vcenter')
			common_format.set_border(1)

			sum_pay_format = workbook.add_format({'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
			sum_pay_format.set_border(1)
			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

			digital_format = workbook.add_format({'num_format': '#0', 'align': 'center'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '# ### ##0', 'align': 'right'})
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
			worksheet.write(1, 0, f'За период: {date_from} - {date_to}', title_name_report)

			row_cnt = 1
			shift_row = 2
			cnt_part = 0

			cursor = connection.cursor()
			log.info(f'{file_name}. Загружаем данные за период {date_from} : {date_to}')
			cursor.execute(active_stmt, [rfpm_id, date_from, date_to])

			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col != 1:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					else:
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					col += 1
				row_cnt += 1
				cnt_part += 1
				if cnt_part > 999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0

			# Шифр отчета
			worksheet.write(0, 5, report_code, title_name_report)

			#worksheet.write(row_cnt+1, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)

			workbook.close()
			now = datetime.datetime.now()
			log.info(f'Формирование отчета {file_name} завершено: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			return file_name


if __name__ == "__main__":
    log.info(f'Отчет {report_name} запускается.')
    make_report('0705', '01.10.2022','31.10.2022')
