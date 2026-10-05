# Количество месяцев стажа участия для утвержденных выплат за период
import xlsxwriter
import datetime
import os.path
from logger import log
import cx_Oracle

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Количество месяцев стажа участия для утвержденных выплат за период'
report_code = 'DIA_06_01'

stmt_1 = """
select code_region, rfpm_id, rnn, fio, risk_date, sum_avg, ksu, kzd, kut, mrzp, count_donation, sum_all, count(unique si.pay_month)
from (       
      SELECT 
        sfa.rfbn_id code_region,
        sfa.rfpm_id,
        p.iin rnn,
        sfa.sicid,
        p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
        case when p.sex=0 then 'ж' else 'м' end sx,
        sfa.risk_date,
        sfa.DATE_ADDRESS,
        sfa.sum_avg,
        sfa.ksu,
        sfa.kzd,
        sfa.kut, 
        sfa.mrzp,
        sfa.count_donation,
        sfa.sum_all
      FROM sipr_maket_first_approve_2 sfa, person p
      WHERE sfa.sicid = p.sicid
      AND substr(sfa.rfpm_id,1,4) = :p1
      AND sfa.date_approve >= :d1 AND sfa.date_approve <= :d2
) a, si_member_2 si 
where a.sicid = si.sicid(+)
and   si.pay_month <= a.DATE_ADDRESS    
group by code_region, rfpm_id, rnn, fio, risk_date, sum_avg, ksu, kzd, kut, mrzp, count_donation, sum_all
order by code_region, fio
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
	worksheet.write(2, 1, 'Код области', common_format)
	worksheet.write(2, 2, 'Вид выплаты', common_format)
	worksheet.write(2, 3, 'ИИН', common_format)
	worksheet.write(2, 4, 'ФИО', common_format)
	worksheet.write(2, 5, 'Дата риска', common_format)
	worksheet.write(2, 6, 'Назначенная сумма', common_format)
	worksheet.write(2, 7, 'КСУ', common_format)
	worksheet.write(2, 8, 'КЗД', common_format)
	worksheet.write(2, 9, 'КУТ', common_format)
	worksheet.write(2, 10, 'МРЗП', common_format)
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

			#worksheet.write(row_cnt+1, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)

			workbook.close()
			now = datetime.datetime.now()
			log.info(f'Формирование отчета {file_name} завершено: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			return file_name


if __name__ == "__main__":
    log.info(f'Отчет {report_name} запускается.')
    make_report('0705', '01.10.2022','31.10.2022')
