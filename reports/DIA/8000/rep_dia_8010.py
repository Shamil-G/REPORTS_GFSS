# -*- coding: utf-8 -*-
"""8010. Динамика поступлений сумм СО и пени за два года.

Перенос WEB_REP_R_8010 (AIS 8010, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8010.xlsx` (2024 и 2025 гг.,
январь - июль).

Строка - месяц от января до выбранного: число различных участников с КНП 012,
сумма СО (КНП 012) и пеня (КНП 017) за выбранный год и за предыдущий, темп
роста = текущий / прошлый - 1. Месяц платежа - по `pay_date_gfss`, платежи
берутся с предыдущего месяца (`pay_date >= add_months(начало месяца, -1)`) -
как в 8005.

Оригинал читал EAV `rptb_rep_mintrud_data` (`rep_year` 2024 и 2025,
`value_type` 1 - число, 2 - СО, 3 - пеня), а последнюю строку (без названия)
вставлял литералами: 6 230 860 / 355 407 152 714,80 / 1 188 384 566,45 за 2024
и 6 403 827 / 532 149 568 482,20 / 1 092 191 426,47 за 2025. Здесь месяцы
считаются из `si_member_2`, а итоговая строка - теми же условиями за весь
период с начала года: различные участники за период, а не сумма помесячных
(людей повторяет), СО и пеня - суммы. Название итоговой строки, как в
оригинале, пустое. Модуль не зависит от EAV и устаревших значений.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '8010'
report_name = 'Динамика поступлений сумм СО и пени {period}'

_CNT = 'количество участников*, человек'


def _label(rep_year, date_type, date_start=None):
    return f'за {int(rep_year) - 1}-{int(rep_year)} гг.'


COLUMNS = [
    Col('Месяц', 'mon_name', 'text', 16),
    Group('{prev_year} год', [
        Col(_CNT, 'p_cnt', 'int', 18),
        Col('Социальные отчисления', 'p_so', 'money', 22),
        Col('Пеня', 'p_pen', 'money', 18),
    ]),
    Group('{year} год', [
        Col(_CNT, 'c_cnt', 'int', 18),
        Col('Социальные отчисления', 'c_so', 'money', 22),
        Col('Пеня', 'c_pen', 'money', 18),
    ]),
    Group('Темп роста, %', [
        Col(_CNT, 'r_cnt', 'pct', 18),
        Col('Социальные отчисления', 'r_so', 'pct', 22),
        Col('Пеня', 'r_pen', 'pct', 18),
    ]),
]

# yr: 0 - предыдущий год, 1 - выбранный. per - месяцы периода, ytd - весь период.
STMT = """
with n as (
    select level k from dual
   connect by level <= months_between(:d_to, :y_from)
),
per as (
    select 0 yr, k, add_months(:y_from, k - 13) d1, add_months(:y_from, k - 12) d2 from n
    union all
    select 1 yr, k, add_months(:y_from, k - 1), add_months(:y_from, k) from n
),
mm as (
    select /*+parallel(4)*/
           per.yr, per.k,
           count(distinct case when m.knp = '012' then m.sicid end) cnt,
           sum(case when m.knp = '012' then m.sum_pay else 0 end) so,
           sum(case when m.knp = '017' then m.sum_pay else 0 end) pen
      from per, si_member_2 m
     where m.pay_date_gfss >= per.d1
       and m.pay_date_gfss <  per.d2
       and m.pay_date >= add_months(per.d1, -1)
       and m.pay_date <  per.d2
     group by per.yr, per.k
),
yy as (
    select 0 yr, add_months(:y_from, -12) d1, add_months(:d_to, -12) d2 from dual
    union all
    select 1, :y_from, :d_to from dual
),
ytd as (
    select /*+parallel(4)*/
           yy.yr, 99 k,
           count(distinct case when m.knp = '012' then m.sicid end) cnt,
           sum(case when m.knp = '012' then m.sum_pay else 0 end) so,
           sum(case when m.knp = '017' then m.sum_pay else 0 end) pen
      from yy, si_member_2 m
     where m.pay_date_gfss >= yy.d1
       and m.pay_date_gfss <  yy.d2
       and m.pay_date >= add_months(yy.d1, -1)
       and m.pay_date <  yy.d2
     group by yy.yr
),
u as (
    select yr, k, cnt, so, pen from mm
    union all
    select yr, k, cnt, so, pen from ytd
),
w as (
    select k,
           max(decode(yr, 0, cnt)) p_cnt, max(decode(yr, 0, so)) p_so, max(decode(yr, 0, pen)) p_pen,
           max(decode(yr, 1, cnt)) c_cnt, max(decode(yr, 1, so)) c_so, max(decode(yr, 1, pen)) c_pen
      from u
     group by k
)
select decode(k, 99, null,
              initcap(trim(to_char(add_months(:y_from, k - 1), 'fmMonth',
                                   'NLS_DATE_LANGUAGE=RUSSIAN')))) mon_name,
       p_cnt, p_so, p_pen, c_cnt, c_so, c_pen,
       c_cnt / nullif(p_cnt, 0) - 1 r_cnt,
       c_so / nullif(p_so, 0) - 1 r_so,
       c_pen / nullif(p_pen, 0) - 1 r_pen,
       decode(k, 99, 1, 0) bold
  from w
 order by k
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_label,
    bold_key='bold',
)
