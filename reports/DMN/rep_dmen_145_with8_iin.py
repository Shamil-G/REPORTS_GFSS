from configparser import ConfigParser
# from   db_config import report_db_user, report_db_password, report_db_dsn
import xlsxwriter
import datetime
import os.path
from   util.logger import log
import oracledb
from   model.call_report import set_status_report

# from cx_Oracle import SessionPool
# con = cx_Oracle.connect(cfg.username, cfg.password, cfg.dsn, encoding=cfg.encoding)

report_name = 'Кол-во дел по дням и регионам с доработкой 145 ИИН-ы'
report_code = 'rep_dmen_145_with8_iin'


stmt_2 = """
with st7with_dat as (
                select 
                        st.sid,
                        st.st2,
                        first_value(st.dat) over(partition by sid order by dat) dat,
                        s_brid,
                        p_pc
                from ss_m_sol_st st
                where st2 in (7, 12)
                and st.dat >= to_date(:d1, 'YYYY-MM-DD') AND st.dat < to_date(:d2, 'YYYY-MM-DD') + 1
                and substr(p_pc, 1, 4) = case when :rfpm_id = '0000' then substr(p_pc, 1, 4) else :rfpm_id end
)
,
comm_st as(
                select  st.sid,
                        st.st2,
                        st.dat,
                        st7.s_brid,
                        st7.p_pc,
                        z.sicid,
                        z.num,
                        rn
                from ss_m_sol_st st, ss_z_doc z, st7with_dat st7, person p
                where z.id = st.sid
                and st.sid = st7.sid
                and z.sicid = p.sicid
                and st.st2 in (145, 8, 43, 44, 45)
                and z.id_tip = 'NEW'
                )
                ,
st4_145 as
            (
            select * from
                            (
                            select
                                    st.sid,
                                    st.st2,
                                    first_value(st.dat) over(partition by st.sid, st.num order by st.dat) dat,
                                    row_number() over(partition by st.sid, st.num order by st.dat) row_num,
                                    s_brid,
                                    p_pc,
                                    sicid,
                                    st.num,
                                    rn
                            from comm_st st
                            where st2 in (145)
                            )
            where row_num=1
            )
,
st8_43 as (
            select * from
                        (
                        select  st.sid,
                                st.st2,
                                first_value(st.dat) over(partition by st.sid, st.num order by st.dat) dat,
                                row_number() over(partition by st.sid, st.num order by st.dat) row_num,
                                s_brid,
                                p_pc
                        from comm_st st
                        where st2 in (8, 43, 44, 45)
                        )
            where row_num=1
            )
,
cntdays487 as (
                select  count_work_date(trunc(st4.dat,'DD'), trunc(st7.dat, 'DD'))+1 cnt_days,
                        st4.sid,
                        st4.s_brid,
                        st4.p_pc,
                        st4.sicid,
                        st4.num,
                        rn
                from st8_43 st8, st4_145 st4, st7with_dat st7
                where st8.sid = st4.sid
                and st8.sid = st7.sid
                )

        select  substr(s_brid, 1, 2), 
                case when cnt.cnt_days < 5 then rn else null end before_5,
                case when cnt.cnt_days between 5 and 9 then rn else null end in5_9,
                case when cnt.cnt_days between 10 and 14 then rn else null end in10_14,
                case when cnt.cnt_days between 15 and 19 then rn else null end in15_19,
                case when cnt.cnt_days between 20 and 24 then rn else null end in20_24,
                case when cnt.cnt_days >= 25 then rn else null end more25
        from cntdays487 cnt
		order by substr(s_brid, 1, 2)
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

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'Регион', common_format)
	worksheet.write(2, 2, 'до 5 дней', common_format)
	worksheet.write(2, 3, 'от 5 до 9 дней', common_format)
	worksheet.write(2, 4, 'от 10 до 14 дней', common_format)
	worksheet.write(2, 5, 'от 15 до 19 дней', common_format)
	worksheet.write(2, 6, 'от 20 до 24 дней', common_format)
	worksheet.write(2, 7, 'больше 25', common_format)


def do_report(file_name: str, srfpm_id: str, date_first: str, date_second: str):
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

			title_format = workbook.add_format({'align': 'center', 'font_color': 'black'})
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
			worksheet.write(1, 0, f'За период: {date_first} - {date_first}, {srfpm_id}', title_name_report)

			row_cnt = 1
			shift_row = 2
			cnt_part = 0

			cursor = connection.cursor()
			log.info(f'{file_name}. Загружаем данные за период {date_first} : {date_second}, srfpm: {srfpm_id}')
			cursor.execute(active_stmt, rfpm_id=srfpm_id, d1=date_first, d2=date_second)

			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 1
				worksheet.write(row_cnt+shift_row, 0, row_cnt, digital_format)
				for list_val in record:
					if col in (1, 2):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col == 3:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col == 4:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col == 5:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col == 6:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					if col == 7:
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					col += 1
				row_cnt += 1
				cnt_part += 1

			#worksheet.write(row_cnt+1, 3, "=SUM(D2:D"+str(row_cnt+1)+")", sum_pay_format)
			#
			worksheet.write(0, 7, report_code, title_report_code)
			
			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 7, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


def thread_report(file_name: str, srfpm_id: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: rfpm_id: 0702, date_first: {date_first}, date_second: {date_second}')
	threading.Thread(target=do_report, args=(file_name, srfpm_id, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('0701', '01.01.2022','31.10.2022')
