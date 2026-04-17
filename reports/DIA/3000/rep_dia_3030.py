from main_app import log
from db.connect import select
import datetime
from flask import g, Response
from urllib import parse
import io
import xlsxwriter
import locale 


report_name = 'Возвраты социальных выплат по получателю'
report_code = 'RV_01'

locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

def get_stmt():
	return """
	select  /*+parallel(4)*/
			pd.doc_date "Дата документа",
			p.iin "ИИН",
			p.lastname||' '||p.firstname||' '||p.middlename as "ФИО",
			pd.doc_nmb "Номер документа",
			pd.cipher_id_knp "КНП",
			pd.refer "Референс",
			dl.pay_sum "Сумма возврата",
			coalesce(dl.period, pd.period) "Период возврата",
			pd.doc_assign "Назначение платежа",
			pd.rfbk_mfo_pbank "Получатель"
	from  pmpd_pay_doc pd, pmdl_doc_list dl, person p
	where pd.r_account='KZ70125KZT1001300134'
	and   pd.mhmh_id=dl.mhmh_id
	and   dl.sicid=p.sicid
	and pd.cipher_id_knp in (
			'020', --Удержания Соц.выплат
			'028', --Возврат СВут
			'047', --Возврат СВпк
			'049', --Возврат СВпр
			'092', --Возврат СВур
			'097', --Возврат СВбр
			'039' --Возврат СВчп
			)
	and p.iin=:iin
	order by pd.doc_date
	"""

HEADER_ROW = 2
DATA_START_ROW = HEADER_ROW + 1

# def do_report(file_name: str, iin: str):
def do_report(in_params: dict):
	file_name = in_params.get("file_name","no_file_name")
	iin = in_params.get("iin","no_iin")

	stmt = get_stmt();
	log.debug(f'DO REPORT. {report_code}  file_name: {file_name}, IIN:\n{iin}')


	s_date = datetime.datetime.now().strftime("%H:%M:%S")
	output = io.BytesIO()

	params = {"iin": iin}
	rows = select(stmt, params)      
	
	log.info(f'\tLOGGING RECORDS: {params}')

	with xlsxwriter.Workbook(output, {'in_memory': True}) as workbook:
		worksheet = workbook.add_worksheet("Отчет")
		safe_filename = parse.quote(file_name)

		if not rows:
			worksheet.write(0, 0, "Нет данных для отображения")
			workbook.close() 

			excel_bytes = output.getvalue()

			return Response(
				excel_bytes,
				mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
				headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
			)


		### ЗАГОЛОВКИ
		title_name_report = workbook.add_format({ "align": "left", "font_color": "black", "font_size": "14", "valign": "vcenter", "bold": True	})
		header_format = workbook.add_format({ "bold": True, "align": "center", "font_size": "12", "valign": "vcenter", "border": 1, "bg_color": "#E0F7FF", "text_wrap": True })
		text_format = workbook.add_format({ "align": "left", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2" })
		currency_format = workbook.add_format({ "align": "right", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2", "num_format": "### ### ### ##0.00" })
		text_format_center = workbook.add_format({ "text_wrap": True, "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2", "num_format": '@' })
		date_format = workbook.add_format({	"num_format": "dd/mm/yyyy", "align": "center", "valign": "vcenter", "border": 1, "bg_color": "#f2f2f2" })
		title_format_it = workbook.add_format({	"align": "right", "valign": "vcenter", "italic": True })
		##
		list_name_money = ["Сумма возврата"]
		list_name_date = ["Дата документа"]
		list_name_text = ["ФИО", "Назначение платежа", "Получатель"]
		list_name_text_center = ["Номер документа", "КНП", "Референс", "Период возврата","ИИН"]
		# list_name_text_list = []

		list_column_width =[8,12, 14, 35, 15, 8, 20, 19, 12, 35, 35]

		# Пишем шапку и указываем ширину колонок
		worksheet.set_column(0, 1, list_column_width[0])
		worksheet.write(HEADER_ROW, 0, "№", header_format)
		for col_num, column_name in enumerate(rows[0]):
			worksheet.write(HEADER_ROW, col_num+1, column_name, header_format)
			worksheet.set_column(col_num+1, col_num+2, list_column_width[col_num+1])
			# log.info(f'{col_num+1}. CREATE TITLE. {column_name}:{list_column_width[col_num]}')

		worksheet.set_row(0, 24)
		worksheet.set_row(1, 24)
		worksheet.set_row(HEADER_ROW, 60)

		now = datetime.datetime.now()

		worksheet.write(0, 0, f'{report_name} на {now.strftime('"%d" %B %Y')}', title_name_report)
		worksheet.write(0, 10, report_code, title_name_report)


		### ЗАПИСЬ
		for row_num, record in enumerate(rows):
			worksheet.write( DATA_START_ROW + row_num, 0, row_num, text_format_center )
			for col_num, (column_name, value) in enumerate(record.items()):
				if any(column_name.lower() in name.lower() for name in list_name_date):
					worksheet.write( DATA_START_ROW + row_num, col_num+1, value, date_format )
				if any(column_name.lower() in name.lower() for name in list_name_money):
					if value is None:
						continue
					# worksheet.write( DATA_START_ROW + row_num, col_num, float(value.replace(' ', '').replace(',', '.')), currency_format )
					worksheet.write( DATA_START_ROW + row_num, col_num+1, value, currency_format )
				if any(column_name.lower() in name.lower() for name in list_name_text):
					worksheet.write( DATA_START_ROW + row_num, col_num+1, value, text_format )
				if any(column_name.lower() in name.lower() for name in list_name_text_center):
					worksheet.write( DATA_START_ROW + row_num, col_num+1, value, text_format_center )
				# if any(column_name.lower() in name.lower() for name in list_name_text_list):
				# 	text='\n'.join(value)
				# 	worksheet.write( DATA_START_ROW + row_num, col_num, text, list_format )

		stop_time = now.strftime("%H:%M:%S")

		worksheet.write(1, 10, f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})', title_format_it)


	log.info(f'REPORT: {report_code}. Формирование отчета {safe_filename} завершено ({s_date} - {stop_time}).')

	excel_bytes = output.getvalue()
	return Response(
		excel_bytes,
		mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		headers={"Content-Disposition": f"attachment; filename={safe_filename}"}
	)
