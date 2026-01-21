from configparser import ConfigParser
import xlsxwriter
import datetime
import os.path
import oracledb
from   util.logger import log
from   model.call_report import set_status_report


report_name = 'Получатели СВут (0702) с 1 разделом'
report_code = '1502.03'

stmt_create = """
select 
      rfbn_id, 
	  rfpm_id, 
	  iin, 
	  birthdate,
      sex, 
      age,
      appointdate, date_approve, stopdate, 
      sum(last_pay_sum) as all_sum_pay,  
      ksu, kut, sum_avg, sum_all,
	  mrzp,
	  sum(sum_debt)	 sum_debt
from (
    select 
      b.rfbn_id, b.rfpm_id, 
	  iin, 
	  birthdate,
      sex, 
      age,
      b.appointdate, b.date_approve, b.stopdate, 
      b.last_pay_sum,  
      b.ksu, b.kut, b.sum_avg, b.sum_all,
      b.knp,
      mrzp,
      sum_debt,
      case when b.pay_month>=to_date('2023-01-01','YYYY-MM-DD') then 1 else 0 end p_month,
      case when b.pay_month is null then 0 else 1 end all_month	  
    from (
        select unique 
          a.rfbn_id, a.rfpm_id, p.iin, p.birthdate,
          case when p.sex=0 then 'Ж' else 'M' end as sex, 
          floor( months_between(a.risk_date, p.birthdate) / 12 ) age,
          a.appointdate, a.date_approve, a.stopdate, 
          a.last_pay_sum,  
          a.ksu, a.kut, a.sum_avg, a.sum_all,
          si.pay_month,
          a.knp,
		  a.mrzp,
		  a.sum_debt
        from (              
          SELECT /*+parallel(4)*/
               unique d.pncd_id,
               FIRST_VALUE(pp.rfbn_id) OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) rfbn_id,
               FIRST_VALUE(D.rfpm_id) OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) rfpm_id,
               FIRST_VALUE(pp.appointdate) OVER(PARTITION BY D.PNCD_ID ORDER BY pp.appointdate DESC) appointdate,
               FIRST_VALUE(sipr.risk_date) OVER(PARTITION BY D.PNCD_ID ORDER BY sipr.risk_date DESC) risk_date,
               FIRST_VALUE(sipr.date_approve) OVER(PARTITION BY sipr.iin ORDER BY sipr.date_approve DESC) date_approve,
               FIRST_VALUE(pp.stopdate) OVER(PARTITION BY D.PNCD_ID ORDER BY D.PNCP_DATE DESC) stopdate,
               case when D.pay_sum>0 then D.pay_sum else d.sum_debt end as last_pay_sum,
               sipr.kut, sipr.ksu, sipr.sum_avg, sipr.sum_all, 
               d.knp, 
               FIRST_VALUE(mrzp) OVER(PARTITION BY D.PNCD_ID ORDER BY sipr.risk_date DESC) mrzp,
			   d.sum_debt
          FROM  PNPD_DOCUMENT D, 
                sipr_maket_first_approve_2 sipr,
                PNPT_PAYMENT PP
          WHERE D.SOURCE_ID = PP.PNPT_ID(+)
          and   d.source_id = sipr.pnpt_id(+)
          AND   D.PNCP_DATE >= to_date(:date_first,'YYYY-MM-DD') 
		  AND   D.PNCP_DATE <  to_date(:date_second,'YYYY-MM-DD') + 1
          AND   substr(D.RFPM_ID,1,4) = '0702'
          AND   D.RIDT_ID IN (4, 6, 7, 8)
          AND   D.STATUS IN (0, 1, 2, 3, 5, 7)
          AND   D.PNSP_ID > 0
        ) a, person p, si_member_2 si
        where a.pncd_id = si.sicid(+) 
        and   a.pncd_id = p.sicid
		and	  si.knp(+) = '012'
        and   si.pay_date(+) BETWEEN to_date(:date_first,'YYYY-MM-DD') AND to_date(:date_second,'YYYY-MM-DD')  
    ) b
)
group by 
      rfbn_id, rfpm_id, 
	  iin, 
	  birthdate,
      sex, 
      age,
      appointdate, date_approve, stopdate, 
      ksu, kut, sum_avg, sum_all, mrzp
order by rfbn_id, rfpm_id, iin
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
	worksheet.set_column(3, 3, 14)
	worksheet.set_column(4, 4, 12)
	worksheet.set_column(5, 5, 8)
	worksheet.set_column(6, 6, 12)
	worksheet.set_column(7, 7, 12)
	worksheet.set_column(8, 8, 12)
	worksheet.set_column(9, 9, 12)
	worksheet.set_column(10, 10, 18)
	worksheet.set_column(11, 11, 8)
	worksheet.set_column(12, 12, 8)
	worksheet.set_column(13, 13, 12)
	worksheet.set_column(14, 14, 21)
	worksheet.set_column(15, 15, 16)
	worksheet.set_column(16, 16, 16)

	worksheet.merge_range('A3:A4', '№', common_format)
	worksheet.merge_range('B3:B4', 'Код региона', common_format)
	worksheet.merge_range('C3:C4', 'Код выплаты', common_format)
	worksheet.merge_range('D3:D4', 'ИИН получателя', common_format)
	worksheet.merge_range('E3:E4', 'Дата рождения', common_format)	
	worksheet.merge_range('F3:F4', 'Пол', common_format)
	worksheet.merge_range('G3:G4', 'Возраст на дату риска', common_format)
	worksheet.merge_range('H3:H4', 'Дата риска', common_format)
	worksheet.merge_range('I3:I4', 'Дата назначения', common_format)
	worksheet.merge_range('J3:J4', 'Дата окончания', common_format)
	worksheet.merge_range('K3:K4', 'Размер СВ', common_format)
	worksheet.merge_range('L3:L4', 'КСУ', common_format)
	worksheet.merge_range('M3:M4', 'КУТ', common_format)
	worksheet.merge_range('N3:N4', 'СМД', common_format)
	worksheet.merge_range('O3:O4', 'Сумма первой назначенной выплаты', common_format)
	worksheet.merge_range('P3:P4', 'МРЗП', common_format)
	worksheet.merge_range('Q3:Q4', 'Сумма 1 раздела', common_format)


def do_report(file_name: str, date_first: str, date_second: str):
	if os.path.isfile(file_name):
		log.info(f'Отчет уже существует {file_name}')
		return file_name

	s_date = datetime.datetime.now().strftime("%H:%M:%S")

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

			title_format_it = workbook.add_format({'align': 'right'})
			title_format_it.set_align('vcenter')
			title_format_it.set_italic()

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
			worksheet.write(1, 0, f'За период: {date_first} - {date_second}', title_name_report)

			row_cnt = 1
			shift_row = 3
			cnt_part = 0
			m_val = [0]

			log.info(f'Выполняем Execute для отчета: {report_code}')
			try:
				cursor.execute(active_stmt, date_first=date_first, date_second=date_second)
			except oracledb.DatabaseError as e:
				error, = e.args
				log.error(f"ERROR. REPORT {report_code}. error_code: {error.code}, error: {error.message}\n{active_stmt}")
				set_status_report(file_name, 3)
				return
			finally:
				log.info(f'REPORT: {report_code}. Execute выполнен')
				
			log.info(f'Выполняем FetchAll для отчета: {report_code}')
			records = cursor.fetchall()

			log.info(f'Для отчета {report_code} выбираем записи из курсора за период {date_first} - {date_second}')
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1,2,3,6):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col in(5,):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col in (4,7,8,9):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col in (10,11,12,13,14,15,16,17):
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					# ADD to SUMMARY
					# if col in (9):
					# 	m_val[0] = m_val[0] + list_val
					col += 1
				cnt_part += 1
				if cnt_part > 24999:
					log.info(f'{file_name}. LOADED {row_cnt} records.')
					cnt_part = 0
				row_cnt += 1

			# SUMMARY
			# worksheet.write(row_cnt + shift_row, 10, m_val[0], money_format)
			worksheet.write(0, 12, report_code, title_report_code)

			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 12, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


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
