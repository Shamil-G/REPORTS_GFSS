# -*- coding: utf-8 -*-
"""8005. Доля социальных выплат по отношению к сумме поступивших социальных
отчислений.

Перенос WEB_REP_R_8005 (AIS 8005, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8005.xlsx` (2025 год, январь
- июль). В оригинале период был зашит (01.01.2025 - 01.08.2025), здесь это
«с начала года по выбранный месяц».

Строка - месяц от января до выбранного. Социальные отчисления (с учётом пени) -
сумма `si_member_2.sum_pay` по месяцу поступления в ГФСС (`pay_date_gfss`) за
платежи, сделанные в предыдущем и в этом месяце (`pay_date` с первого числа
предыдущего месяца). Социальные выплаты - сумма `pay_sum + sum_debt`
платёжных документов `pnpd_document` по месяцу `pncp_date`. Доля = выплаты /
отчисления. Обе суммы - в миллионах тенге (в образце так же; оригинал отдавал
тенге, деление на миллион делал веб-слой).

Оригинал соединял `payment_history`, не используя ни одной её колонки; здесь
таблица не берётся.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '8005'
report_name = ('Доля социальных выплат по отношению к сумме поступивших '
               'социальных отчислений {period} '
               '(8005, составлен без технического задания)')

_period_label = make_period_label({7: 'в {year} году'})

COLUMNS = [
    Col('Месяц', 'mon_name', 'text', 24),
    Col('Социальные отчисления (с учетом пени), млн.тенге', 'so', 'money', 26),
    Col('Социальные выплаты, млн. тенге', 'sv', 'money', 22),
    Col('Доля СВ/СО, %', 'perc', 'pct', 14),
]

STMT = """
with mo as (
    select add_months(:y_from, level - 1) d1, add_months(:y_from, level) d2
      from dual
   connect by add_months(:y_from, level - 1) < :d_to
),
si as (
    select mo.d1, sum(m.sum_pay) so
      from mo, si_member_2 m
     where m.pay_date_gfss >= mo.d1
       and m.pay_date_gfss <  mo.d2
       and m.pay_date >= add_months(mo.d1, -1)
       and m.pay_date <  mo.d2
     group by mo.d1
),
pv as (
    select /*+parallel(4)*/
           trunc(d.pncp_date, 'MM') d1, sum(d.pay_sum + d.sum_debt) sv
      from pnpd_document d
     where d.pncp_date >= :y_from
       and d.pncp_date <  :d_to
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
     group by trunc(d.pncp_date, 'MM')
),
t as (
    select mo.d1, si.so / 1000000 so, pv.sv / 1000000 sv
      from mo, si, pv
     where si.d1(+) = mo.d1
       and pv.d1(+) = mo.d1
)
select mon_name, so, sv, perc, bold
  from (
    select t.d1 ord,
           initcap(trim(to_char(t.d1, 'fmMonth', 'NLS_DATE_LANGUAGE=RUSSIAN'))) mon_name,
           t.so, t.sv, t.sv / nullif(t.so, 0) perc, 0 bold
      from t
    union all
    select date '9999-01-01', 'С начала года',
           sum(t.so), sum(t.sv), sum(t.sv) / nullif(sum(t.so), 0), 1
      from t
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    bold_key='bold',
)
