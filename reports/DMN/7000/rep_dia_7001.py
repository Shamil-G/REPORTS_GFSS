# -*- coding: utf-8 -*-
"""============================================================
ДМЭН, группа 7000, отчёт 7001. Новый отчёт (07.10.2026), не перенос из AIS.
============================================================

Оказание услуг по отделениям за день: число завершённых услуг, из них
длительностью 15 минут и более, и число отказов.

Источник - журнал услуг `services_journ` схемы dasorp: услуга относится к
отделению сотрудника (`web_gs_emp.branch_id`), берутся услуги, начатые в
выбранный день (`start_date`). Строки - все отделения справочника
`con_codes` (внешнее соединение), у отделения без услуг нули.

Схема dasorp основной учётке приложения не видна, поэтому отчёт работает под
профилем DASORP_PROFILE (секция [dasorp_db_60] в db_config.ini).

Фильтр по области - первые две цифры `branch_id`; пусто - вся республика.

Дата приходит из формы строкой 'YYYY-MM-DD' (input type=date).
"""
from db.connect import DASORP_PROFILE
from util.xlsx_report import build_report, Col

report_code = '7001'
report_name = 'Сведения об оказанных услугах по отделениям за {day_text}'

COLUMNS = [
    Col('Код отделения', 'branch_id', 'center', 12),
    Col('Наименование отделения', 'name', 'text', 40),
    Col('Завершено услуг', 'cnt_finished', 'int', 16),
    Col('Из них длительностью 15 минут и более', 'duration', 'int', 18),
    Col('Отказано', 'refused', 'int', 14),
]

STMT = """
select c.branch_id,
       c.name,
       coalesce(a.cnt_finished, 0) cnt_finished,
       coalesce(a.duration, 0) duration,
       coalesce(a.refused, 0) refused
  from (select c.branch_id,
               count(s.mess_id) cnt_finished,
               sum(case when (cast(s.finish_date as date) - cast(s.start_date as date)) * 24 * 60 >= 15
                        then 1 else 0 end) duration,
               sum(case when s.refused = 'Отказано' then 1 else 0 end) refused
          from con_codes c, web_gs_emp w, services_journ s
         where c.branch_id = w.branch_id
           and s.user_id = w.emp_id
           and s.start_date >= to_date(:date_first, 'YYYY-MM-DD')
           and s.start_date <  to_date(:date_first, 'YYYY-MM-DD') + 1
         group by c.branch_id) a,
       con_codes c
 where c.branch_id = a.branch_id(+)
   and (:rfbn_id is null or substr(c.branch_id, 1, 2) = :rfbn_id)
 order by c.branch_id
"""

# дата для названия в виде dd.mm.yyyy
TITLE_SQL = "select to_char(to_date(:date_first, 'YYYY-MM-DD'), 'dd.mm.yyyy') day_text from dual"

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=DASORP_PROFILE, title_sql=TITLE_SQL,
)
