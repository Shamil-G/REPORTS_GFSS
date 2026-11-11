from configparser import ConfigParser
import xlsxwriter
import datetime
from   util.logger import log
import oracledb
import os.path
from   model.manage_reports import set_status_report
from util.trunc_date import get_month_name
from util.period import month_first_day

report_name = 'Динамика численности получателей и сумм социальных выплат из АО "Государственный фонд социального страхования" по видам социальных рисков за '
report_code = 'DYN.9_1'

stmt_report = """
with dt as (select trunc(to_date(:dt_from,'YYYY-MM-DD'),'MM') dt_from from dual)
-- платежи отчётного месяца (как Fill_F11: ridt_id = 6, ключ - source_id)
, cur as (
	select unique d.source_id, d.pncd_id, substr(d.rfpm_id,1,4) rfpm
	From pnpd_document d, dt
	Where d.pncp_date = dt.dt_from
	And d.rfpm_id like '07%' And d.rfpm_id not like '0704%'
	And d.ridt_id = 6
	And d.status In (0, 1, 2, 3, 5, 7)
	And d.pnsp_id > 0
)
-- платежи предыдущего месяца
, prv as (
	select unique d.source_id, d.pncd_id, substr(d.rfpm_id,1,4) rfpm
	From pnpd_document d, dt
	Where d.pncp_date = add_months(dt.dt_from, -1)
	And d.rfpm_id like '07%' And d.rfpm_id not like '0704%'
	And d.ridt_id = 6
	And d.status In (0, 1, 2, 3, 5, 7)
	And d.pnsp_id > 0
)
-- события месяца по человеку: приход 1-назначен(100) 2-восстановлен(120,121) 3-прибыл(110);
-- уход 1-умер(122) 2-снят(151,152) 3-убыл(150). Меньший код приоритетнее (как order by 1 в Fill_F11)
, ev as (
	select ap.pncd_id,
	       min(decode(ap.riac_id, 100, 1, 120, 2, 121, 2, 110, 3)) in_op,
	       min(decode(ap.riac_id, 122, 1, 151, 2, 152, 2, 150, 3)) out_op
	From pnap_act_prt_2 ap, dt
	Where ap.act_month >= dt.dt_from
	And   ap.act_month <  add_months(dt.dt_from, 1)
	And   ap.riac_id In (100, 120, 121, 110, 122, 150, 151, 152)
	Group By ap.pncd_id
)
-- движение: FULL OUTER JOIN cur/prv по source_id, записанный через (+) как два LEFT-соединения
-- (в Oracle FULL JOIN с (+) невозможен, ORA-01468).
-- IN  - есть в текущем месяце, нет в прошлом; OUT - есть в прошлом, нет в текущем.
-- Нет события в pnap_act_prt_2 -> по умолчанию 2 (восстановленный / снятый), как no_data_found в Fill_F11
, mv as (
	select c.rfpm, 'IN' dir, nvl(e.in_op, 2) op
	From cur c, prv p, ev e
	Where c.source_id = p.source_id (+)
	And   p.source_id is null
	And   c.pncd_id = e.pncd_id (+)

	union all

	select p.rfpm, 'OUT' dir, nvl(e.out_op, 2) op
	From prv p, cur c, ev e
	Where p.source_id = c.source_id (+)
	And   c.source_id is null
	And   p.pncd_id = e.pncd_id (+)
)
-- впервые включённые в выплату в отчётном месяце (приход с событием 100 'назначение')
, nw as (
	select c.source_id, c.rfpm
	From cur c, prv p, ev e
	Where c.source_id = p.source_id (+)
	And   p.source_id is null
	And   c.pncd_id = e.pncd_id
	And   e.in_op = 1
)
select * from
	(
	select ' 1. численность получателей на начало месяца, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from prv group by rfpm)
	union

	select ' 2. Сумма выплат, тенге' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select substr(d.rfpm_id,1,4) rfpm, sum(d.pay_sum + d.sum_debt) cnt
		From pnpd_document d, dt
		Where d.pncp_date = dt.dt_from
		And d.rfpm_id like '07%' And d.rfpm_id not like '0704%'
		And d.ridt_id In (6, 7, 8)
		And d.status In (0, 1, 2, 3, 5, 7)
		And d.pnsp_id > 0
		Group By substr(d.rfpm_id,1,4))
	union

	select ' 3. назначение, человек*' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (SELECT substr(sfa.rfpm_id,1,4) rfpm, count(*) cnt
		FROM sswh.sipr_maket_first_approve_2 sfa, dt
		WHERE substr(sfa.rfpm_id,1,4) in ('0701','0702','0703','0705')
		and sfa.date_approve >= dt.dt_from
		and sfa.date_approve < add_months(dt.dt_from, 1)
		group by substr(sfa.rfpm_id,1,4))
	union

	select ' 4. сумма социальных выплат для назначенных, тенге' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (SELECT substr(sfa.rfpm_id,1,4) rfpm, sum(sfa.sum_all) cnt
		FROM sswh.sipr_maket_first_approve_2 sfa, dt
		WHERE substr(sfa.rfpm_id,1,4) in ('0701','0702','0703','0705')
		and sfa.date_approve >= dt.dt_from
		and sfa.date_approve < add_months(dt.dt_from, 1)
		group by substr(sfa.rfpm_id,1,4))
	union

	select ' 4.1 выплачено назначенным в отчётном месяце с учётом задолженности, тенге' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select nw.rfpm rfpm, sum(d.pay_sum + d.sum_debt) cnt
		From nw, pnpd_document d, dt
		Where d.source_id = nw.source_id
		And d.pncp_date = dt.dt_from
		And d.ridt_id In (6, 7, 8)
		And d.status In (0, 1, 2, 3, 5, 7)
		And d.pnsp_id > 0
		Group By nw.rfpm)

	union

	select ' 4.2 в т.ч. сумма задолженности, тенге' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select nw.rfpm rfpm, sum(d.sum_debt) cnt
		From nw, pnpd_document d, dt
		Where d.source_id = nw.source_id
		And d.pncp_date = dt.dt_from
		And d.ridt_id In (6, 7, 8)
		And d.status In (0, 1, 2, 3, 5, 7)
		And d.pnsp_id > 0
		Group By nw.rfpm)

	union

	select ' 5. смертность, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from mv where dir='OUT' and op=1 group by rfpm)
	union

	select ' 6. прибывшие из-за пределов Республики Казахстан, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from mv where dir='IN' and op=3 group by rfpm)
	union

	select ' 7. Убывшие за пределы Республики Казахстан, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from mv where dir='OUT' and op=3 group by rfpm)
	union

	select ' 8. восстановленные, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from mv where dir='IN' and op=2 group by rfpm)
	union

	select ' 9. снятые, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from mv where dir='OUT' and op=2 group by rfpm)
	union

	select '10. численность выплат на конец месяца, человек' line,
		sum( case when rfpm='0702' then cnt else 0 end) v_0702,
		sum( case when rfpm='0701' then cnt else 0 end) v_0701,
		sum( case when rfpm='0703' then cnt else 0 end) v_0703,
		sum( case when rfpm='0705' then cnt else 0 end) v_0705
	from (select rfpm, count(*) cnt from cur group by rfpm)
) order by line
"""


LINE_MARKS = {'1': ' ¹', '3': ' ²', '4': ' ⁶', '5': ' ³', '6': ' ³', '7': ' ³', '8': ' ⁴', '9': ' ⁵', '10': ' ¹'}

# Значения строк версии 1 (rep_dia_dynamic) за тот же месяц - для живых примеров в примечаниях
stmt_v1 = """
with dt as (select trunc(to_date(:dt_from,'YYYY-MM-DD'),'MM') dt_from from dual)
select
 (select count(unique d.pncd_id) from pnpd_document d, dt
   where d.pncp_date = add_months(dt.dt_from, -1) and substr(d.rfpm_id,1,4) = '0702'
   and d.ridt_id in (4,6,7,8) and d.status in (0,1,2,3,5,7) and d.pnsp_id > 0) start_0702,
 (select count(unique d.pncd_id || '/' || ap.riac_id) from pnpd_document d, pnap_act_prt_2 ap, dt
   where d.pncp_date = add_months(dt.dt_from, -1) and ap.act_month >= dt.dt_from and ap.act_month < add_months(dt.dt_from, 1)
   and d.pncd_id = ap.pncd_id and substr(d.rfpm_id,1,4) = '0701' and d.ridt_id in (4,6,7,8)
   and d.status in (0,1,2,3,5,7) and d.pnsp_id > 0 and ap.riac_id in (120, 121)) rest_0701,
 (select count(unique d.pncd_id || '/' || ap.riac_id) from pnpd_document d, pnap_act_prt_2 ap, dt
   where d.pncp_date = add_months(dt.dt_from, -1) and ap.act_month >= dt.dt_from and ap.act_month < add_months(dt.dt_from, 1)
   and d.pncd_id = ap.pncd_id and substr(d.rfpm_id,1,4) = '0703' and d.ridt_id in (4,6,7,8)
   and d.status in (0,1,2,3,5,7) and d.pnsp_id > 0 and ap.riac_id in (151, 152)) snyat_0703,
 (select count(unique sfa.iin) from sswh.sipr_maket_first_approve_2 sfa, dt
   where substr(sfa.rfpm_id,1,4) = '0703' and sfa.date_approve >= dt.dt_from and sfa.date_approve < add_months(dt.dt_from, 1)) uniq_0703,
 (select count(unique sfa.iin) from sswh.sipr_maket_first_approve_2 sfa, dt
   where substr(sfa.rfpm_id,1,4) = '0705' and sfa.date_approve >= dt.dt_from and sfa.date_approve < add_months(dt.dt_from, 1)) uniq_0705
from dual
"""

COLS = {'0702': 1, '0701': 2, '0703': 3, '0705': 4}


def _fmt(n):
	if n is None:
		return '-'
	return f'{n:,.0f}'.replace(',', ' ')


def line_values(records):
	"""{('4.1', '0702'): значение}: номер строки берётся из начала названия строки"""
	import re
	res = {}
	for rec in records:
		m = re.match(r'\s*(\d+(?:\.\d+)?)', rec[0])
		if not m:
			continue
		for code, idx in COLS.items():
			res[(m.group(1), code)] = rec[idx]
	return res


def build_notes(v, v1, period):
	"""Примечания: общее описание логики + живой пример за выбранный период"""
	ex = f'Например, за {period} было: '
	g = lambda n, c: _fmt(v.get((n, c)))
	notes = ['Примечания (отличия от отчёта rep_dia_dynamic, версия 1):']
	notes.append(
		'¹ Строки 1 и 10. В версии 1 считались люди (count unique pncd_id, ridt_id 4,6,7,8). Здесь считаются платежи: '
		'source_id, ridt_id = 6, как в REP_MINTRUD_WEB.Fill_F11 и в АИС. Один человек с несколькими платежами даёт '
		'несколько единиц, поэтому значения отличаются на единицы. Строка 10 = строка 1 + приход - уход. '
		+ ex + f"строка 1, 0702 - {g('1', '0702')} вместо {_fmt(v1.get('start_0702'))} в версии 1.")
	notes.append(
		'² Строка 3. Источник тот же (sipr_maket_first_approve_2, date_approve), но count(*) вместо count(unique iin): '
		'считаются назначения, а не люди, как на листе 8Д. Строка 4 не изменилась: это назначенный размер (sum_all), '
		'а не фактическая выплата за месяц, поэтому она может быть существенно меньше суммы для назначенных с учётом '
		'задолженности (строка 4.1). '
		+ ex + f"строка 3, 0703 - {g('3', '0703')} вместо {_fmt(v1.get('uniq_0703'))}, "
		f"0705 - {g('3', '0705')} вместо {_fmt(v1.get('uniq_0705'))}; "
		f"строка 4, 0702 - {g('4', '0702')} против {g('4.1', '0702')} в строке 4.1.")
	notes.append(
		'³ Строки 5, 6, 7. В версии 1 брались только люди из документов прошлого месяца, имевшие событие месяца. '
		'Теперь выбывшие и прибывшие определяются разностью платежей двух месяцев по source_id, а вид события '
		'берётся из pnap_act_prt_2 с приоритетом как в Fill_F11 (меньший код важнее).')
	notes.append(
		'⁴ Строка 8. В версии 1 восстановленные искались среди тех, кто был в прошлом месяце, поэтому почти не находились. '
		'Теперь это все прибывшие без события «назначение» (100) и «прибытие» (110); прибывший без записи события '
		'в pnap_act_prt_2 тоже считается восстановленным. '
		+ ex + f"строка 8, 0701 - {g('8', '0701')} вместо {_fmt(v1.get('rest_0701'))} в версии 1.")
	notes.append(
		'⁵ Строка 9. Теперь это все выбывшие без события «смерть» (122) и «убытие» (150); выбывший без записи события '
		'считается снятым. '
		+ ex + f"строка 9, 0703 - {g('9', '0703')} вместо {_fmt(v1.get('snyat_0703'))} в версии 1.")
	notes.append(
		'⁶ Строки 4.1 и 4.2 добавлены (в версии 1 их нет). Строка 4 - назначенный размер (sum_all). Строка 4.1 - '
		'фактически начислено в отчётном месяце тем, кто впервые попал в выплату (приход с событием 100): '
		'pay_sum + sum_debt по документам ridt_id 6, 7, 8. Строка 4.2 - из них задолженность (sum_debt); '
		'именно она объясняет разрыв между строками 4 и 4.1. '
		+ ex + f"0702: строка 4 - {g('4', '0702')}, строка 4.1 - {g('4.1', '0702')}, "
		f"в т.ч. задолженность (4.2) - {g('4.2', '0702')}.")
	return notes



def format_worksheet(worksheet, common_format, title_format, title_format_it, date_first):
	worksheet.set_row(0, 48)
	# worksheet.set_row(1, 24)
	worksheet.set_row(2, 48)
	#worksheet.set_row(3, 48)
	worksheet.set_row(5, 88)

	worksheet.set_column(0, 0, 64)
	worksheet.set_column(1, 1, 18)
	worksheet.set_column(2, 2, 18)
	worksheet.set_column(3, 3, 18)
	worksheet.set_column(4, 4, 18)

	worksheet.merge_range('D1:E1', 'Приложение №9 к Приказу Министра труда и социальной защиты населения Республики Казахстан от "18" мая 2023 года №158', title_format_it)
	worksheet.merge_range('A3:E3', f'Динамика числености поучателей и сумм социальных выплат из АО "Государственный фонд социального страхования" по видам социальных рисков за {get_month_name(date_first)} {date_first[0:4]}г.', common_format)

	worksheet.merge_range('A5:A6', 'Наименование', title_format)
	worksheet.merge_range('B5:E5', 'По видам социальных рисков', title_format)
	worksheet.write(5,1, '0702 - по случаю утраты трудоспособности', title_format)
	worksheet.write(5,2, '0701 - по случаю потери кормильца', title_format)
	worksheet.write(5,3, '0703 - по случаю потери работы', title_format)
	worksheet.write(5,4, '0705 - по случаю потери дохода в связи с уходом за ребенком по достижении им возраста 1,5 лет', title_format)

	worksheet.write(6,0, '1', title_format)
	worksheet.write(6,1, '2', title_format)
	worksheet.write(6,2, '3', title_format)
	worksheet.write(6,3, '4', title_format)
	worksheet.write(6,4, '5', title_format)


def do_report(file_name: str, date_first: str = None, rep_year=None, period=None, **_):
	# Месяц выбирается списками "год" + "месяц"; прямая дата date_first оставлена для старых вызовов
	if not date_first:
		date_first = month_first_day(rep_year, period)
	if os.path.isfile(file_name):
		log.info(f'Отчет уже существует {file_name}')
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

			title_name_report = workbook.add_format({'align': 'left', 'font_color': 'black', 'font_size': '18'})
			title_name_report .set_align('vcenter')
			title_name_report .set_bold()

			title_format_it = workbook.add_format({'align': 'justify', 'font_size': '10', 'text_wrap': True })
			title_format_it.set_align('vcenter')
			title_format_it.set_italic()

			date_create_format = workbook.add_format({'align': 'right', 'font_size': '10'})
			date_create_format.set_align('vcenter')
			date_create_format.set_italic()

			common_format = workbook.add_format({'align': 'center', 'font_color': 'black', 'text_wrap': True, 'font_size': '18' })
			common_format.set_align('vcenter')
			# common_format.set_border(1)

			name_format = workbook.add_format({'align': 'left', 'font_color': 'black'})
			name_format.set_align('vcenter')
			name_format.set_border(1)

			sum_pay_format = workbook.add_format({'num_format': '###,###,###,##0.00', 'font_color': 'black', 'align': 'vcenter'})
			sum_pay_format.set_border(1)

			date_format = workbook.add_format({'num_format': 'dd.mm.yyyy', 'align': 'center'})
			date_format.set_border(1)
			date_format.set_align('vcenter')

			digital_format = workbook.add_format({'num_format': '### ### ### ##0', 'align': 'right'})
			digital_format.set_border(1)
			digital_format.set_align('vcenter')

			digital_format_center = workbook.add_format({'num_format': '### ### ### ##0', 'align': 'center'})
			digital_format_center.set_border(1)
			digital_format_center.set_align('vcenter')

			money_format = workbook.add_format({'num_format': '### ### ### ### ##0.00', 'align': 'right'})
			money_format.set_border(1)
			money_format.set_align('vcenter')

			now = datetime.datetime.now()
			log.info(f'Начало формирования {file_name}: {now.strftime("%d-%m-%Y %H:%M:%S")}')
			page_num = 1
			worksheet = []
			worksheet.append( workbook.add_worksheet(f'Список {page_num}') )
			sql_sheet = workbook.add_worksheet('SQL')
			merge_format = workbook.add_format({
				'bold':     False,
				'border':   6,
				'align':    'left',
				'valign':   'vcenter',
				'fg_color': '#FAFAD7',
				'text_wrap': True
			})
			sql_sheet.merge_range(f'A1:I{len(stmt_report.splitlines())}', f'{stmt_report}', merge_format)

			worksheet[page_num-1].activate()

			format_worksheet(worksheet=worksheet[page_num-1], common_format=common_format, title_format=title_format, title_format_it=title_format_it, date_first=date_first)

			# worksheet[page_num-1].write(0, 0, report_name, title_name_report)
			# worksheet[page_num-1].write(1, 0, f'За период: {date_first}', title_name_report)

			log.info(f'REPORT {report_code}. CREATING REPORT')

			try:
				cursor.execute(stmt_report, dt_from=date_first)
			except oracledb.DatabaseError as e:
				error, = e.args
				log.error(f"ERROR. REPORT {report_code}. error_code: {error.code}, error: {error.message}")
				log.info(f'\n---------\n{stmt_report}\n---------')
				set_status_report(file_name, 3)
				return
			finally:
				log.info(f'REPORT: {report_code}. Выборка из курсора завершена')
			
			log.info(f'REPORT: {report_code}. Формируем выходную EXCEL таблицу')

			row_cnt = 1
			all_cnt = 0
			shift_row = 6
			cnt_part = 0

			records = []
			records = cursor.fetchall()
			#for record in records:
			for record in records:
				col = 0
				start_char='1'
				for list_val in record:
					if isinstance(list_val, str): 
						start_char = list_val[0]
						# знак сноски добавляется здесь, а не в SQL: через драйвер надстрочные символы превращаются в '?'
						list_val += LINE_MARKS.get(list_val.split('.')[0].strip(), '')
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, name_format)
					elif start_char in ('2','4'):
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, money_format)
					else:
						worksheet[page_num-1].write(row_cnt+shift_row, col, list_val, digital_format)
					col+= 1
				row_cnt+= 1
				cnt_part+= 1


			stop_time = now.strftime("%H:%M:%S")
			worksheet[page_num-1].write(row_cnt+shift_row+1, 0, '* потребность на месяц', title_format_it)
			info = f'Дата формирования: {now.strftime("%d.%m.%Y ")}({s_date} - {stop_time})'
			worksheet[page_num-1].write(row_cnt+shift_row+1, 4, info, date_create_format)

			note_format = workbook.add_format({'align': 'left', 'valign': 'top', 'text_wrap': True, 'font_size': '10'})
			note_row = row_cnt + shift_row + 3
			# значения версии 1 за тот же месяц для живых примеров; при ошибке примечания идут без цифр версии 1
			v1 = {}
			try:
				cursor.execute(stmt_v1, dt_from=date_first)
				cols = [c[0].lower() for c in cursor.description]
				row = cursor.fetchone()
				v1 = dict(zip(cols, row)) if row else {}
			except oracledb.DatabaseError as e:
				log.error(f'REPORT {report_code}. stmt_v1: {e}')
			period = f'{get_month_name(date_first)} {date_first[0:4]}г.'
			NOTES = build_notes(line_values(records), v1, period)
			for i, note in enumerate(NOTES):
				worksheet[page_num-1].merge_range(note_row + i, 0, note_row + i, 4, note, note_format)
				worksheet[page_num-1].set_row(note_row + i, 15 if i == 0 else 72)

			workbook.close()

			log.info(f'REPORT: {report_code}. Формирование отчета {file_name} завершено ({s_date} - {stop_time}), Загружено {all_cnt} записей')
			set_status_report(file_name, 2)


def thread_report(file_name: str, date_first: str = None, rep_year=None, period=None, **_):
	if not date_first:
		date_first = month_first_day(rep_year, period)
	import threading
	log.info(f'THREAD REPORT. {datetime.datetime.now().strftime("%d-%m-%Y %H:%M:%S")} -> {file_name}')
	log.info(f'THREAD REPORT. PARAMS: date_from: {date_first}')
	threading.Thread(target=do_report, args=(file_name, date_first), daemon=True).start()
	return {"status": 1, "file_path": file_name}


if __name__ == "__main__":
    log.info(f'Отчет {report_code} запускается.')
    do_report('test_dyn9_1.xlsx', '2026-10-01')
