# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3121 (процедура REP_R_3121).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения об иностранных гражданах - получателях социальных выплат
в разрезе документов (вид документа, удостоверяющего личность).

Источник - `pnpd_document` + `person` + `rfdt_doc_type` (`person.doctype =
rfdt_id`), иностранец - `citizenship_id <> 105`. Отбор документов за месяц
такой же, как в 3120. Количество - уникальные `pncd_id`, порядок - по
названию документа.

Название дословно (двойной пробел после дефиса убран). Период - месяц
(`pDateTo = last_day(pMonth)`), подпись `to_char(pMonth, 'month yyyy')` -
месяц строчными, год через пробел.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '3121'
report_name = ('Сведения об иностранных гражданах - получателях социальных '
               'выплат в разрезе документов, {period} года')

_period_label = make_period_label({1: '{month} {year}'})

COLUMNS = [
    Col('Документ', 'name', 'text', 50),
    Col('Количество, человек', 'cnt', 'int', 20),
]

# :d_from / :d_to - границы месяца, :d_to исключительная.
STMT = """
select dt.name,
       count(distinct pd.pncd_id) cnt
  from pnpd_document pd, person p, rfdt_doc_type dt
 where pd.pncd_id = p.sicid
   and p.doctype = dt.rfdt_id
   and p.citizenship_id <> 105
   and pd.pncp_date >= :d_from
   and pd.pncp_date <  :d_to
   and pd.pnsp_id > 0
   and pd.ridt_id in (4, 6, 7, 8)
   and pd.status in (0, 1, 2, 3, 5, 7)
 group by dt.name
 order by dt.name
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
