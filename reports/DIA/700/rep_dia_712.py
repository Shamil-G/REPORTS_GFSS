# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 712 (процедура Rep_Actuar_12).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средние размеры социальных выплат получателям по потере кормильца: по числу
иждивенцев число и средний размер выплаты для «новых» получателей (расчёт
назначения в периоде) и для «всех» на конец периода.

Источник и логика те же, что в 711 (`sipr_payer_arc` + `sihs_history` на месяц
конца периода, `file_type = 'D'`, состояния 12 и 13), вид 0701; группа -
последняя цифра вида (число иждивенцев), 4 печатается как «4 и более».

Таблицы `sihs_history`, `sipr_payer_arc`, `siap_action_protocol` лежат в схеме
SSWH боевой БД, в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '712'
report_name = ('Средние размеры социальных выплат получателям по потере '
               'кормильца\nза период с {date_from} по {date_to}')

COLUMNS = [
    Col('Количество иждивенцев', 'cnt_i', 'center', 20),
    Group('Для "новых" получателей', [
        Col('Кол-во', 'cnt_new', 'int', 14),
        Col('Средний размер', 'avg_new', 'money', 18, total=False),
    ]),
    Group('Для "всех" получателей', [
        Col('Кол-во', 'cnt_all', 'int', 14),
        Col('Средний размер', 'avg_all', 'money', 18, total=False),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная (конец + 1 сутки).
STMT = """
select case when cnt_i = '4' then cnt_i || ' и более' else cnt_i end cnt_i,
       count(case when in_date >= :d_from and in_date < :d_to then 1 end) cnt_new,
       avg(case when in_date >= :d_from and in_date < :d_to then sum_all end) avg_new,
       count(1) cnt_all, avg(sum_all) avg_all
  from (select /*+index (p xp_sipr_payer_arc)*/
               substr(p.rfpm_id, -1) cnt_i, p.sum_all,
               (select /*+index (pa xp_sipr_payer_arc)*/ ap.date_calc
                  from sipr_payer_arc pa, siap_action_protocol ap
                 where pa.sipr_id = p.sipr_id
                   and p.actp_id = ap.actp_id
                   and rownum = 1) in_date
          from sihs_history h, sipr_payer_arc p
         where h.act_month = trunc(:d_to - 1, 'month')
           and h.file_type = 'D'
           and h.sipr_id = p.sipr_id
           and h.actp_sipr = p.actp_id
           and p.rfpm_id like '0701%'
           and p.state in (12, 13))
 group by cnt_i
 order by cnt_i
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
