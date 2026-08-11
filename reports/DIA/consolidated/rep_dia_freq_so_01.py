from configparser import ConfigParser
import xlsxwriter
import datetime
from   util.logger import log
import oracledb
import os.path
from   model.manage_reports import set_status_report

report_name = 'Частота уплаты социальных отчислений за период (FSO)'
report_code = 'FSO'

#document.status:  0 - Документ сформирован на выплату, 1 - Сформирован платеж, 2 - Платеж на выплате

stmt_report = """
with src as (
  select /*+parallel(4)*/
       si.sicid, 
       si.p_rnn, 
       p.iin,
       trunc(si.pay_date,'MM') pay_month, 
       si.sum_pay, si.type_payer, si.type_payment  
  from si_member_2 si, person p
  where si.pay_date_gfss>=to_date(:d1,'yyyy-mm-dd')
  and   si.pay_date_gfss<to_date(:d2,'yyyy-mm-dd')+1
  and   si.pay_date>=to_date(:d1,'yyyy-mm-dd')-30
  and   si.pay_date<to_date(:d2,'yyyy-mm-dd')+1
  and   si.knp='012'
  and   si.sicid=p.sicid
  and	1!=2
)
, hired_ul as(
  select /*+parallel(4)*/ 
         unique sicid 
  from src s 
  where type_payer in ('U','N')
  and nvl(type_payment,'X') not in ('O','P')
  minus
  select /*+parallel(4)*/ 
         unique sicid 
  from src s 
  where type_payer not in ('U','N')
  or nvl(type_payment,'X') in ('O','P')
)
, comb_payment as(
  select /*+parallel(4)*/ 
         unique sicid
  from src s 
  where type_payment='O'
  minus
  select /*+parallel(4)*/ sicid 
  from src s 
  where nvl(type_payment,'X')!='O'
)
, ppz_payment as(
  select /*+parallel(4)*/ 
         unique sicid
  from src s 
  where type_payment='P'
  minus
  select /*+parallel(4)*/ 
         unique sicid
  from src s 
  where nvl(type_payment,'X')!='P'
) 
, sz_list as (
  select /*+parallel(4)*/ unique sicid
  from src s 
  where type_payer='SZ'
  minus
  select /*+parallel(4)*/ unique sicid 
  from src s 
  where type_payer!='SZ'
)
, boss_ip as (
  select /*+parallel(4)*/ unique sicid
  from src s 
  where s.p_rnn=s.iin
  and   type_payer='I'
  minus
  select /*+parallel(4)*/ unique sicid 
  from src s 
  where type_payer!='I'
  or    s.p_rnn!=s.iin
)
, hired_ip as (
  select /*+parallel(4)*/ 
         unique sicid 
  from src s 
  where type_payer='I'
  or    s.p_rnn!=s.iin
  minus
  select /*+parallel(4)*/ unique sicid 
  from src s 
  where type_payer not in ('I')
  or    s.p_rnn=s.iin  
)
, mesh_emp as 
(  --4 min
  select unique sicid
  from (
    select sicid -- 
    from (
      select sicid, count(unique decode(si.type_payer,'N','U',si.type_payer)), count(unique nvl(si.type_payment,'X'))
      from src si
      group by si.sicid
      having count(unique decode(si.type_payer,'N','U',si.type_payer))>1 or count(unique nvl(si.type_payment,'X'))>1
    )
    union
    select sicid -- Для индивидуальных предпринимателей
    from (
      select sicid
      from src si
      where type_payer = 'I'
      minus
      select sicid
      from boss_ip
      minus 
      select sicid
      from hired_ip
    )
  )
)
, esp_emp as(
  select /*+parallel(4)*/ 
         sicid 
  from src s 
  where type_payer='E'
  minus 
  select /*+parallel(4)*/ 
         sicid 
  from src s 
  where type_payer!='E'
),
people_cat as (
  select /*+parallel(4)*/ a.cat, a.sicid, count(unique src.pay_month) cnt_month, sum(sum_pay ) as all_sum_pay
  from 
  (
    select /*+parallel(4)*/ '1. Наемные ЮЛ' as cat, sicid  --5035815, 5034462, 5 035 386
    from hired_ul
    union
    select /*+parallel(4)*/ '2. Объединенные платежи', sicid -- 30 320
    from comb_payment
    union
    select /*+parallel(4)*/ '3. Платформенная занятость', sicid
    from ppz_payment
    union
    select /*+parallel(4)*/ '4. ИП руководители', sicid
    from boss_ip
    union
    select /*+parallel(4)*/ '5. ИП наемные', sicid -- !!!
    from hired_ip
    union
    select /*+parallel(4)*/ '6. Смешанные', sicid --
    from mesh_emp
    union
    select /*+parallel(4)*/ '7. ЕСП', sicid -- !!!
    from esp_emp
	union
    select /*+parallel(4)*/ '8. Самозанятые', sicid -- !!!
    from sz_list
  ) a, src
  where src.sicid=a.sicid
  group by a.cat, a.sicid
)
select /*+parallel(4)*/
  sl.cat,
    COUNT(sicid) p_all,
    sum(CASE WHEN cnt_month = 1 THEN sl.all_sum_pay ELSE 0 END) s_1,
    sum(CASE WHEN cnt_month = 2 THEN sl.all_sum_pay ELSE 0 END) s_2,
    sum(CASE WHEN cnt_month = 3 THEN sl.all_sum_pay ELSE 0 END) s_3,
    sum(CASE WHEN cnt_month = 4 THEN sl.all_sum_pay ELSE 0 END) s_4,
    sum(CASE WHEN cnt_month = 5 THEN sl.all_sum_pay ELSE 0 END) s_5,
    sum(CASE WHEN cnt_month = 6 THEN sl.all_sum_pay ELSE 0 END) s_6,
    sum(CASE WHEN cnt_month = 7 THEN sl.all_sum_pay ELSE 0 END) s_7,
    sum(CASE WHEN cnt_month = 8 THEN sl.all_sum_pay ELSE 0 END) s_8,
    sum(CASE WHEN cnt_month = 9 THEN sl.all_sum_pay ELSE 0 END) s_9,
    sum(CASE WHEN cnt_month = 10 THEN sl.all_sum_pay ELSE 0 END) s_10,
    sum(CASE WHEN cnt_month = 11 THEN sl.all_sum_pay ELSE 0 END) s_11,
    sum(CASE WHEN cnt_month = 12 THEN sl.all_sum_pay ELSE 0 END) s_12,
    sum(CASE WHEN cnt_month > 12 THEN sl.all_sum_pay ELSE 0 END) s_more_12,

    sum(CASE WHEN cnt_month = 1 THEN 1 ELSE 0 END) m_1,
    sum(CASE WHEN cnt_month = 2 THEN 1 ELSE 0 END) m_2,
    sum(CASE WHEN cnt_month = 3 THEN 1 ELSE 0 END) m_3,
    sum(CASE WHEN cnt_month = 4 THEN 1 ELSE 0 END) m_4,
    sum(CASE WHEN cnt_month = 5 THEN 1 ELSE 0 END) m_5,
    sum(CASE WHEN cnt_month = 6 THEN 1 ELSE 0 END) m_6,
    sum(CASE WHEN cnt_month = 7 THEN 1 ELSE 0 END) m_7,
    sum(CASE WHEN cnt_month = 8 THEN 1 ELSE 0 END) m_8,
    sum(CASE WHEN cnt_month = 9 THEN 1 ELSE 0 END) m_9,
    sum(CASE WHEN cnt_month = 10 THEN 1 ELSE 0 END) m_10,
    sum(CASE WHEN cnt_month = 11 THEN 1 ELSE 0 END) m_11,
    sum(CASE WHEN cnt_month = 12 THEN 1 ELSE 0 END) m_12,
    sum(CASE WHEN cnt_month > 12 THEN 1 ELSE 0 END) m_more_12
from people_cat sl
group by sl.cat
order by 1
"""

def format_worksheet(worksheet, common_format):
	worksheet.set_row(0, 24)
	worksheet.set_row(1, 24)
	worksheet.set_row(2, 20)
	worksheet.set_row(4, 14)

	worksheet.set_column(0, 0, 28)
	worksheet.set_column(1, 1, 12)

	for num in range(2,15):	# Money
		worksheet.set_column(num, num, 18)

	for num in range(15,27):   # count 
		worksheet.set_column(num, num, 14)
		
	for num in range(26,28):   # count 
		worksheet.set_column(num, num, 16)

	for num in range(28):
		worksheet.write(4,num, num+1, common_format)


	worksheet.merge_range('A3:A4', 'Категория работника', common_format)
	worksheet.merge_range('B3:B4', 'Всего сотрудников', common_format)
	worksheet.merge_range('C3:O3', 'Сумма уплаты с частотой уплаты', common_format)
	worksheet.merge_range('P3:AB3', 'Количество участников с частотой уплаты', common_format)

	worksheet.write(3,2, '1 месяц', common_format)
	worksheet.write(3,3, '2 месяца', common_format)
	worksheet.write(3,4, '3 месяца', common_format)
	worksheet.write(3,5, '4 месяца', common_format)
	worksheet.write(3,6, '5 месяцев', common_format)
	worksheet.write(3,7, '6 месяцев', common_format)
	worksheet.write(3,8, '7 месяцев', common_format)
	worksheet.write(3,9, '8 месяцев', common_format)
	worksheet.write(3,10, '9 месяцев', common_format)
	worksheet.write(3,11, '10 месяцев', common_format)
	worksheet.write(3,12, '11 месяцев', common_format)
	worksheet.write(3,13, '12 месяцев', common_format)
	worksheet.write(3,14, 'более 12 месяцев', common_format)
	worksheet.write(3,15, '1 месяц', common_format)
	worksheet.write(3,16, '2 месяца', common_format)
	worksheet.write(3,17, '3 месяца', common_format)
	worksheet.write(3,18, '4 месяца', common_format)
	worksheet.write(3,19, '5 месяцев', common_format)
	worksheet.write(3,20, '6 месяцев', common_format)
	worksheet.write(3,21, '7 месяцев', common_format)
	worksheet.write(3,22, '8 месяцев', common_format)
	worksheet.write(3,23, '9 месяцев', common_format)
	worksheet.write(3,24, '10 месяцев', common_format)
	worksheet.write(3,25, '11 месяцев', common_format)
	worksheet.write(3,26, '12 месяцев', common_format)
	worksheet.write(3,27, 'более 12 месяцев', common_format)
	

def do_report(file_name: str, date_first: str, date_second: str):
	if os.path.isfile(file_name):
		log.info(f'Отчет уже существует {file_name}: {date_first}')
		return file_name

	s_date = datetime.datetime.now().strftime("%H:%M:%S")

	log.info(f'DO REPORT. START {report_code}. DATE_FROM: {date_first}, FILE_PATH: {file_name}')

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

			title_format = workbook.add_format({'bg_color': '#D1FFFF', 'align': 'center', 'font_color': 'black'})
			#title_format = workbook.add_format({'bg_color': '#C5FFFF', 'align': 'center', 'font_color': 'black'})
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

			category_name_format = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format.set_align('vcenter')
			category_name_format.set_border(1)

			category_name_format_1 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_1.set_border(1)
			category_name_format_1.set_bg_color('#FFF8DC')	  # Желтенький
			category_name_format_2 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_2.set_bg_color('#DAFBC5')	  # Зелененький
			category_name_format_3 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_3.set_bg_color('#FDFEE5')	  # Желтенький
			category_name_format_4 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_4.set_bg_color('#EBE6FF')	  #  Светло-голубой
			category_name_format_5 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_5.set_bg_color('#FFFFE0')	  # Слегка желтенький
			category_name_format_6 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_6.set_bg_color('#FFE1E1')	  # Розовый
			category_name_format_7 = workbook.add_format({'align': 'left', 'font_color': 'black'})
			category_name_format_7.set_bg_color('#E0F7FF')    # Голубой
			category_name_format_1.set_border(1)
			category_name_format_2.set_border(1)
			category_name_format_3.set_border(1)
			category_name_format_4.set_border(1)
			category_name_format_5.set_border(1)
			category_name_format_6.set_border(1)
			category_name_format_7.set_border(1)

			sum_pay_format = workbook.add_format({'num_format': '#,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
			sum_pay_format.set_border(1)

			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

			number_format = workbook.add_format({'num_format': '# ### ### ##0', 'align': 'center'})
			number_format.set_border(1)
			number_format.set_align('vcenter')

			digital_format = workbook.add_format({'num_format': '# ### ### ##0', 'align': 'right'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '### ### ### ### ##0.00', 'align': 'right'})
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
			sql_sheet.merge_range('A1:I145', f'{stmt_report}', merge_format)

			worksheet.activate()
			format_worksheet(worksheet=worksheet, common_format=title_format)

			worksheet.write(0, 0, report_name, title_name_report)
			worksheet.write(1, 0, f'За период: {date_first} - {date_second}', title_name_report)

			cursor = connection.cursor()
			log.info(f'{file_name}. Загружаем данные за период {date_first} : {date_second}')

			try:
				cursor.execute(stmt_report, d1=date_first, d2=date_second)
			except oracledb.DatabaseError as e:
				error, = e.args
				log.error(f"ERROR. REPORT {report_code}. error_code: {error.code}, error: {error.message}\n{stmt_report}")
				set_status_report(file_name, 3)
				return
			finally:
				log.info(f'REPORT: {report_code}. Выборка из курсора завершена')

			log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')

			records = []
			records = cursor.fetchall()
			row_cnt = 1
			shift_row = 4
			num_rec = 0
			#for record in records:
			for record in records:
				col = 0
				for list_val in record:
					if col == 0:
						match(num_rec):
							case 0: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_1)
							case 1: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_2)
							case 2: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_3)
							case 3: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_4)
							case 4: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_5)
							case 5: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_6)
							case 6: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format_7)
							case _: worksheet.write(row_cnt+shift_row, col, list_val, category_name_format)
						num_rec = num_rec+1
					if col in (2,3,4,5,6,7,8,9,10,11,12,13,14):
						worksheet.write(row_cnt+shift_row, col, list_val, money_format)
					if col in (1,15,16,17,18,19,20,21,22,23,24,25,26,27):
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					col += 1
				row_cnt += 1

			# Шифр отчета
			worksheet.write(0, 10, report_code, title_report_code)
			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 10, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Строк в отчете: {row_cnt-1}')


def thread_report(file_name: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS NONE')
	threading.Thread(target=do_report, args=(file_name, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('minSO_02.xlsx', '01.10.2022','31.10.2022')
