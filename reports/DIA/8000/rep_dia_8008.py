# -*- coding: utf-8 -*-
"""8008. Количество назначенных социальных выплат за все годы в разрезе рисков.

Перенос WEB_REP_R_8008 (AIS 8008, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8008.xlsx` (2005-2025).

Строка - год назначения (`sipr_maket_first_approve_2.date_approve`) от 2005 до
выбранного периода, колонки - число назначений всего и по видам: 0702 (утрата
трудоспособности), 0701 (потеря кормильца), 0703 (потеря работы), 0704 (по
беременности и родам), 0705 (уход за ребенком). Период - с начала года по
выбранный месяц (в оригинале зашит 01.08.2025).

«Итого» - сумма по годам. В оригинале итог считался отдельным запросом с
соединением `person`, а строки по годам - без него; на сопоставимых данных числа
те же, но у назначения без записи в `person` итог был бы меньше суммы строк.
Граница периода: оригинал брал `date_approve < дата + 1`, то есть включал первое
августа; здесь - строго по последнее число выбранного месяца.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '8008'
report_name = ('Количество назначенных социальных выплат из АО "ГФСС" '
               '{period} в разрезе рисков\nпо состоянию на {today}г. '
               '(8008, составлен без технического задания)')

_period_label = make_period_label({7: 'за 2005-{year} годы'})

COLUMNS = [
    Col('Год', 'y', 'center', 12),
    Col('Количество получателей*, человек', 'cnt', 'int', 18),
    Group('в том числе', [
        Col('утрата трудоспособности', 'svut', 'int', 16),
        Col('потеря кормильца', 'svpk', 'int', 16),
        Col('потеря работы', 'svpr', 'int', 16),
        Col('по беременности и родам', 'svbr', 'int', 16),
        Col('уход за ребенком', 'svur', 'int', 16),
    ]),
]

# date_approve от 2005 года - не :y_from: отчёт за все годы.
STMT = """
with a as (
    select to_char(sfa.date_approve, 'yyyy') y,
           substr(sfa.rfpm_id, 1, 4) rfpm
      from sipr_maket_first_approve_2 sfa
     where sfa.date_approve >= date '2005-01-01'
       and sfa.date_approve <  :d_to
),
g as (
    select y,
           count(rfpm) cnt,
           count(case when rfpm = '0702' then 1 end) svut,
           count(case when rfpm = '0701' then 1 end) svpk,
           count(case when rfpm = '0703' then 1 end) svpr,
           count(case when rfpm = '0704' then 1 end) svbr,
           count(case when rfpm = '0705' then 1 end) svur
      from a
     group by y
)
select y, cnt, svut, svpk, svpr, svbr, svur, bold
  from (
    select y ord, y, cnt, svut, svpk, svpr, svbr, svur, 0 bold from g
    union all
    select 'zzzz', 'Итого', sum(cnt), sum(svut), sum(svpk), sum(svpr),
           sum(svbr), sum(svur), 1
      from g
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    bold_key='bold',
)
