# Получатели выплат, имеющие одновременно СО
import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Получатели социальных выплат'
report_code = 'DIA_06_03'

stmt_1 = """
select unique first_value(pd.rfbn_id) over(partition by pt.pnpt_id order by pd.pncp_date desc) rfbn_id,
    first_value(pd.rfpm_id) over(partition by pt.pnpt_id order by pd.pncp_date desc) rfpm_id,
    p1.iin R_IIN,
    p2.iin DEP_IIN,
    pt.appointdate,
    pt.approvedate,
    pt.sum_pay,
    first_value(pd.pncp_date) over(partition by pt.pnpt_id order by pd.pncp_date desc) last_pay_date,
    first_value(pd.pnpd_id) over(partition by pd.source_id, pd.pncd_id order by pd.pncp_date desc) last_pnpd_id,
    pd.pncd_id r_sicid,
    dt.risk_date,
    first_value(dt.kut) over(partition by pd.source_id, pd.pncd_id order by pd.pncp_date desc) kut,
    first_value(dt.kzd) over(partition by pd.source_id, pd.pncd_id order by pd.pncp_date desc) kzd,
    first_value(dt.ksu) over(partition by pd.source_id, pd.pncd_id order by pd.pncp_date desc) ksu,
    first_value(dt.sum_avg) over(partition by pd.source_id, pd.pncd_id order by pd.pncp_date desc) smd
from pnpt_payment pt,
    pnpd_document pd,
    ss_m_pay pay,
    ss_data dt,
    person p1,
    person p2
where pt.pnpt_id=pd.source_id
and pd.pncd_id=p1.sicid
and pay.soliray_id=pt.pnpt_id
and dt.sipr_id = pay.sid
and pd.pncd_id=p2.sicid(+)
and substr(pt.rfpm_id,1,4) = :p1
and pd.pncp_date >= :date_from AND pd.pncp_date <= :date_to
order by rfbn_id, rfpm_id, pd.pncd_id
"""

active_stmt = stmt_1

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)

	worksheet.set_column(0, 0, 7)
	worksheet.set_column(1, 1, 9)
	worksheet.set_column(2, 2, 10)
	worksheet.set_column(3, 3, 13)
	worksheet.set_column(4, 4, 13)
	worksheet.set_column(5, 5, 12)
	worksheet.set_column(6, 6, 12)
	worksheet.set_column(7, 7, 12)
	worksheet.set_column(8, 8, 12)
	worksheet.set_column(9, 9, 12)
	worksheet.set_column(10, 10, 12)
	worksheet.set_column(11, 11, 12)
	worksheet.set_column(12, 12, 10)
	worksheet.set_column(13, 13, 10)
	worksheet.set_column(14, 14, 10)
	worksheet.set_column(15, 15, 12)

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'Код региона', common_format)
	worksheet.write(2, 2, 'Код выплаты', common_format)
	worksheet.write(2, 3, 'ИИН получателя', common_format)
	worksheet.write(2, 4, 'ИИН иждивенца', common_format)
	worksheet.write(2, 5, 'Дата риска', common_format)
	worksheet.write(2, 6, 'Дата назначения', common_format)
	worksheet.write(2, 7, 'Размер СВ', common_format)

	worksheet.write(2, 8, 'Последний месяц выплаты', common_format)
	worksheet.write(2, 9, 'Последний Ид выплаты', common_format)
	worksheet.write(2, 10, 'ID получателя (sicid)', common_format)
	worksheet.write(2, 11, 'Дата риска', common_format)
	worksheet.write(2, 12, 'КУТ', common_format)
	worksheet.write(2, 13, 'КЗД', common_format)
	worksheet.write(2, 14, 'КСУ', common_format)
	worksheet.write(2, 15, 'СМД', common_format)


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

			float_digital_format = workbook.add_format({'num_format': '##0.00', 'font_color': 'black', 'align': 'center'})
			float_digital_format.set_border(1)

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
					if col in (1,2,3,4):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col in (5, 6, 8, 11):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col in (12, 13, 14):
						worksheet.write(row_cnt+shift_row, col, list_val, float_digital_format)
					if col in (7, 15):
						worksheet.write(row_cnt+shift_row, col, list_val, sum_pay_format)
					if col in (9, 10):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					col += 1
				row_cnt += 1
				cnt_part += 1
				if cnt_part > 999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0

			#worksheet.write(row_cnt+1, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)

			workbook.close()
			now = datetime.datetime.now()
			log.info(f'Формирование отчета {file_name} завершено: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			return file_name


if __name__ == "__main__":
    log.info(f'Отчет {report_name} запускается.')
    make_report('0701', '01.01.2022','31.12.2022')

