# -*- coding: utf-8 -*-
"""8012. Участники и социальные отчисления Единого платежа в разрезе регионов.

Перенос WEB_REP_R_8012 (AIS 8012, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8012.xlsx`. Период - с начала
года по выбранный месяц (в оригинале зашит 01.01.2025 - 01.08.2025).

Платежи социальных отчислений (`type_payment = 'O'`, КНП 012) с датой
поступления в ГФСС в периоде и датой платежа не раньше начала предыдущего
месяца до начала периода (как в 8005). Регион - по отделению участника
(`person.branchid`, первые два знака + `00` -> `branch`), включая «ГЦВП центр».
«Количество участников» - число различных `sicid`, «Сумма» - сумма `sum_pay`.
Последняя строка без названия, как в оригинале, - итог по всем регионам
(участники - различные, а не сумма по регионам).

Отличие от образца: название региона - `branch.name` (полное: «Акмолинская
область»), а в оригинале `short_name_`, обрезанное до 15 знаков («Вост-Казахст.об»,
«Западно-Казахст»).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '8012'
report_name = 'В разрезе регионов (8012, составлен без технического задания)'

COLUMNS = [
    Col('Регион', 'region', 'text', 36),
    Col('Количество участников (человек)*', 'cnt', 'int', 20),
    Col('Сумма соц. отчислений (тенге)', 'sm', 'money', 24),
]

STMT = """
with c as (
    select /*+parallel(4)*/
           b.rfbn_id, b.name, p.sicid, m.sum_pay
      from si_member_2 m, person p, branch b
     where m.pay_date_gfss >= :y_from
       and m.pay_date_gfss <  :d_to
       and m.pay_date >= add_months(:y_from, -1)
       and m.pay_date <  :d_to
       and m.sicid = p.sicid
       and m.type_payment = 'O'
       and m.knp = '012'
       and b.rfbn_id = substr(p.branchid, 1, 2) || '00'
)
select region, cnt, sm, bold
  from (
    select c.rfbn_id ord, c.name region, count(distinct c.sicid) cnt,
           sum(c.sum_pay) sm, 0 bold
      from c
     group by c.rfbn_id, c.name
    union all
    select 'zzzz', null, count(distinct c.sicid), sum(c.sum_pay), 1
      from c
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, bold_key='bold',
)
