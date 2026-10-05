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

report_name = 'Необратившиеся отказные'
report_code = 'rep_dmn_12'


stmt_2 = """
with otkaz as (
               select   rn, 
                        str.name, 
                        s_brid, 
                        sst.st2, 
                        sst.dat, 
                        p_pc, 
                        sst.ret_txt, 
                        sst.sid,
                        z.sicid,  
                        sum_calc,
                        stopdate,
                        risk_date
                from ss_m_sol_st sst, ss_z_doc z, s_state str, ss_data ss, person p, ss_m_pay m
                where z.id=sst.sid
                and ss.sipr_id(+) = sst.sid
                and p.sicid = z.sicid
                and m.sid = sst.sid
                and substr(p_pc, 1, 4) = case when :rfpm_id = '0000' then substr(p_pc, 1, 4) else :rfpm_id end
                and sst.st2 = 12
                and sst.dat >= to_date(:d1, 'YYYY-MM-DD') AND sst.dat < to_date(:d2, 'YYYY-MM-DD') + 1
                and sst.st2=str.id
                and sum_calc > 0
                ),
naz as  (
            select  z.sicid, 
                    st.dat, 
                    st.st2, 
                    st.p_pc, 
                    st.s_brid,
                    st.ret_txt, 
                    st.sid
            from ss_m_sol_st st, ss_z_doc z, otkaz o
            where z.id = st.sid
            and o.sicid = z.sicid
            and st.dat>o.dat
            and trunc(st.dat, 'DD') between trunc(o.dat, 'DD') and trunc(o.dat, 'DD')+365
            and st.st2 != 12
        )
        ,

res as  (        
            select sicid
            from otkaz
            minus
            select sicid
            from naz        
        )
select  
        s_brid, 
        rn,  
        name, 
        dat, 
        p_pc, 
        ret_txt, 
        sum_calc,
        risk_date,
        stopdate
from otkaz o, res r
where r.sicid = o.sicid
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
	worksheet.set_column(8, 8, 12)
	worksheet.set_column(9, 9, 12)

	worksheet.write(2, 0, '№', common_format)
	worksheet.write(2, 1, 'Код региона', common_format)
	worksheet.write(2, 2, 'ИИН', common_format)
	worksheet.write(2, 3, 'Наименование', common_format)
	worksheet.write(2, 4, 'Дата', common_format)
	worksheet.write(2, 5, 'код выплаты', common_format)
	worksheet.write(2, 6, 'комментарий', common_format)
	worksheet.write(2, 7, 'назначенная сумма', common_format)
	worksheet.write(2, 8, 'дата риска', common_format)
	worksheet.write(2, 9, 'дата окончания', common_format)


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

			digital_format = workbook.add_format({'num_format': '#0', 'align': 'center'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '# ### ##0', 'align': 'right'})
			money_format.set_border(1)
			money_format.set_align('vcenter')
			
			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

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
			worksheet.write(1, 0, f'За период: {date_first} - {date_second}, {srfpm_id}', title_name_report)

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
					if col in (1,2,3,5,6,7):
						worksheet.write(row_cnt+shift_row, col, list_val, common_format)
					if col in (4,8,9):
						worksheet.write(row_cnt+shift_row, col, list_val, date_format)
					if col in ():
						worksheet.write(row_cnt+shift_row, col, list_val, digital_format)
					col += 1
				row_cnt += 1
				cnt_part += 1

			#
			worksheet.write(0, 9, report_code, title_report_code)
			
			now = datetime.datetime.now()
			stop_time = now.strftime("%H:%M:%S")

			worksheet.write(1, 9, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)
			#
			workbook.close()
			set_status_report(file_name, 2)
			
			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено: ({s_date} - {stop_time}). Загружено {row_cnt-1} записей')


def thread_report(file_name: str, srfpm_id: str, date_first: str, date_second: str):
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: rfpm_id: {srfpm_id}, date_first: {date_first}, date_second: {date_second}')
	threading.Thread(target=do_report, args=(file_name, srfpm_id, date_first, date_second), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('0701', '01.01.2022','31.10.2022')