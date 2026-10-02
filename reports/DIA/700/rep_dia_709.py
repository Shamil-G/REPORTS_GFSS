# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 709 (процедура Rep_Actuar_9).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средний возраст иждивенцев получателей СВ по потере кормильца: по категории
иждивенцев число мужчин и женщин и средний возраст (лет).

Источник - `payment_history` (вид 0701, месяц `act_month`) + `sidt_dependant`
(иждивенцы получателя: `pnpt_id = sifl_id`, категория `srdc_id` задана) +
`person` (`dt.sic_id = sicid`). Возраст - `months_between(act_month, birthdate)
/ 12`. Категория печатается как «код - название» (`dep_categor_name` -
функция схемы SSWH). Итоги по колонкам «Кол-во».

В оригинале месяц не параметр: всегда текущий (`trunc(sysdate, 'month')`).
Здесь месяц выбирается в форме (по умолчанию текущий) - это единственное
отличие. Название дословно, но слитное «иждивенцевпо» (в оригинале две строки склеены без
пробела) исправлено на «иждивенцев по»; дата - первое число месяца.
"""
from db.connect import LOADER_PROFILE
from util.period import first_date_label
from util.xlsx_report import build_report, Col, Group

report_code = '709'
report_name = 'Средний возраст иждивенцев по состоянию на {period}'

COLUMNS = [
    Col('Категория иждивенцев', 'srdc', 'text', 40),
    Group('Мужчины', [
        Col('Кол-во', 'cnt_m', 'int', 14),
        Col('Средний возраст', 'age_m', 'money', 16, total=False),
    ]),
    Group('Женщины', [
        Col('Кол-во', 'cnt_f', 'int', 14),
        Col('Средний возраст', 'age_f', 'money', 16, total=False),
    ]),
]

# :d_from - первое число месяца (act_month - месячная дата).
STMT = """
select dt.srdc_id || ' - ' || dep_categor_name(dt.srdc_id) srdc,
       sum(decode(pr.sex, '1', 1)) cnt_m,
       avg(months_between(ph.act_month, decode(pr.sex, '1', pr.birthdate))) / 12 age_m,
       sum(decode(pr.sex, '0', 1)) cnt_f,
       avg(months_between(ph.act_month, decode(pr.sex, '0', pr.birthdate))) / 12 age_f
  from (select *
          from payment_history ph
         where act_month = :d_from
           and rfpm_id like '0701%') ph, sidt_dependant dt, person pr
 where ph.pnpt_id = dt.sifl_id
   and srdc_id is not null
   and dt.sic_id = pr.sicid
 group by dt.srdc_id
 order by dt.srdc_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True,
    period_label=first_date_label,
)
