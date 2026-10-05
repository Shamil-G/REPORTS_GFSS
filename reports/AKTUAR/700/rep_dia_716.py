# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 716 (процедура Rep_Actuar_16).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средняя продолжительность (факт) осуществления социальных выплат получателям
по потере кормильца: по текущему числу иждивенцев число получателей и
средняя продолжительность в месяцах для «новых» получателей (расчёт
назначения в периоде) и для «всех».

Источник - `payment_history` (месяц конца периода, вид 0701) + `sifl_file` +
`sipr_payer`. Продолжительность - `months_between(least(конец, nvl(stop_date,
конец)), appoint_date)`. Группа - последняя цифра вида (число иждивенцев), 4
печатается как «4 и более». Итоги по колонкам «Кол-во». Конец периода, как в
оригинале, сдвигается на конец месяца (`last_day`), в названии печатается этот
день.

Таблицы `sipr_payer`, `sifl_file`, `payment_history` в тестовой reports_test
доступны не все (`sipr_payer_arc`, `siap_action_protocol` - нет): на данных
отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '716'
report_name = ('Средняя продолжительность осуществления социальных выплат '
               'получателям по потере кормильца\n'
               'за период с {date_from} по {date_to_eom}')

_AVG = 'Ср. продолжительность, мес'

COLUMNS = [
    Col('Текущее количество иждивенцев', 'cnt_i', 'center', 22),
    Group('Для "новых" получателей', [
        Col('Кол-во', 'cnt_new', 'int', 12),
        Col(_AVG, 'avg_new', 'money', 18, total=False),
    ]),
    Group('Для "всех" получателей', [
        Col('Кол-во', 'cnt_all', 'int', 12),
        Col(_AVG, 'avg_all', 'money', 18, total=False),
    ]),
]

# :d_from - начало периода; конец - last_day(:d_to - 1) (конец месяца даты «по»).
STMT = """
select case when cnt_i = '4' then cnt_i || ' и более' else cnt_i end cnt_i,
       count(case when in_date >= :d_from
                   and in_date < last_day(:d_to - 1) + 1 then 1 end) cnt_new,
       avg(case when in_date >= :d_from
                 and in_date < last_day(:d_to - 1) + 1 then mnt end) avg_new,
       count(1) cnt_all, avg(mnt) avg_all
  from (select substr(h.rfpm_id, -1) cnt_i,
               months_between(least(last_day(:d_to - 1),
                                    nvl(p.stop_date, last_day(:d_to - 1))),
                              p.appoint_date) mnt,
               (select /*+index (pa xp_sipr_payer_arc)*/ ap.date_calc
                  from sipr_payer_arc pa, siap_action_protocol ap
                 where pa.sipr_id = p.sipr_id
                   and p.actp_id = ap.actp_id
                   and rownum = 1) in_date
          from payment_history h, sifl_file f, sipr_payer p
         where h.act_month = trunc(:d_to - 1, 'month')
           and h.rfpm_id like '0701%'
           and h.pnpt_id = f.sifl_id
           and f.sipr_id = p.sipr_id)
 group by cnt_i
 order by cnt_i
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
