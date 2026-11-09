# -*- coding: utf-8 -*-
"""Средние СО за период.

Не перенос из PL/SQL: отчёт собран по образцу рабочего запроса (средний размер
СО на получателя и средний возраст), в группе 1000 стоит вместе с официальными
отчётами, но сам официальным не является - название задано заказчиком.

Четыре среза в строках: с начала года по выбранный месяц, только выбранный
месяц и те же два периода годом раньше. Период в форме - REP_YEAR + PERIOD_YTD
(тип 7), прошлый год считается сдвигом на 12 месяцев прямо в запросе.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = 'AVG.SO'
report_name = 'Средние СО за период'

COLUMNS = [
    Col('Период', 'slice_name', 'text', 52),
    Col('Количество получателей, чел.', 'cnt_sicid', 'int', 18),
    Col('Среднее по средним СО, тенге', 'avg_of_avg', 'avg', 20),
    Col('Средний возраст, лет', 'avg_age', 'avg', 16),
    Col('Усредненное по всем сразу, тенге', 'avg_all', 'avg', 20),
]

# :d_from / :d_to - границы периода "с начала года по месяц", :d_to исключительная.
# Все четыре среза считаются одним проходом: slices - четыре строки с границами
# периода, к ним соединяются платежи. Условия как в исходном запросе: и дата
# платежа, и месяц платежа внутри одного и того же периода.
# Середина периода (mediate_date) берётся для каждого среза своя - от неё
# считается возраст.
# Срез без данных остаётся в отчёте: slices соединяется с итогами внешним
# соединением, пустые средние печатаются пустой ячейкой (деления на 0 нет).
STMT = """
with slices as (
    select 1 ord, 'Текущий год: с начала года' title,
           :d_from start_date, :d_to before_date from dual
    union all
    select 2, 'Текущий год: за месяц',
           add_months(:d_to, -1), :d_to from dual
    union all
    select 3, 'Прошлый год: с начала года',
           add_months(:d_from, -12), add_months(:d_to, -12) from dual
    union all
    select 4, 'Прошлый год: за месяц',
           add_months(:d_to, -13), add_months(:d_to, -12) from dual
),
parm as (
    select s.ord, s.title, s.start_date, s.before_date,
           s.start_date + (s.before_date - s.start_date) / 2 as mediate_date
    from slices s
),
per_person as (
    select /*+parallel(4)*/
           prm.ord,
           si.sicid,
           sum(si.sum_pay)                                   as sum_pay,
           count(unique si.pay_month)                        as cnt_month,
           sum(si.sum_pay) / count(unique si.pay_month)      as avg_sum,
           months_between(prm.mediate_date, p.birthdate) / 12 as age
    from si_member_2 si, person p, parm prm
    where si.knp = '012'
    and   si.pay_date  >= prm.start_date
    and   si.pay_date  <  prm.before_date
    and   si.pay_month >= trunc(prm.start_date,'YY')
    and   si.pay_month <  prm.before_date
    and   si.type_payer != 'Е'
    and   si.sicid = p.sicid
    group by prm.ord, si.sicid, p.birthdate, prm.mediate_date
),
agg as (
    select ord,
           count(sicid)        as cnt_sicid,
           sum(avg_sum)               as sum_avg,
           sum(age)                   as sum_age,
           sum(sum_pay)               as sum_pay,
           sum(cnt_month)             as cnt_month
    from per_person
    group by ord
)
select prm.title                                         as slice_name,
       nvl(a.cnt_sicid, 0)                               as cnt_sicid,
       case when a.cnt_sicid > 0 then a.sum_avg / a.cnt_sicid end as avg_of_avg,
       case when a.cnt_sicid > 0 then a.sum_age / a.cnt_sicid end as avg_age,
       case when a.cnt_month > 0 then a.sum_pay / a.cnt_month end as avg_all
from parm prm, agg a
where a.ord(+) = prm.ord
order by prm.ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True,
)
