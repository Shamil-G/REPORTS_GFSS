# -*- coding: utf-8 -*-
"""8007. Ежемесячные сведения о социальных выплатах.

Перенос WEB_REP_R_8007 (AIS 8007, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8007.xlsx` (2025 год).

Оригинал читал EAV `rptb_rep_mintrud_data` (год, `date_type = 1`, помесячно,
`value_type` 4 - число получателей, 5 - сумма; заполняет REP_MINTRUD.fill_f4,
признан устаревшим), а строку «С начала года» считал напрямую по
`pnpd_document`. Здесь обе части считаются по `pnpd_document` теми же
условиями, что и f4 / отчёт 3003 (`ridt_id in (4, 6, 7, 8)`,
`status in (0, 1, 2, 3, 5, 7)`, `pnsp_id > 0`): по месяцу `pncp_date` и виду
выплаты - число различных получателей (`pncd_id`) и сумма `pay_sum +
sum_debt`. Регион в EAV разбивал получателей по областям, итог по областям
давал то же число различных получателей, поэтому здесь регион не нужен.

«Всего» по строке - сумма по видам (получатель, получающий выплаты двух видов,
посчитан дважды), как в оригинале. Строка «С начала года» - различные
получатели за весь период по виду, а не сумма по месяцам.

Отличие от образца в строке «С начала года»: оригинал определял вид выплаты там
по `pnpt_payment.rfpm_id` (у 2690 документов за 01-07.2025 платежа нет, их
сумма в виды не попадала, а суммы 0702 и 0703 расходились с суммой по месяцам:
30 002 920 485 против 30 093 872 097,78). Здесь везде вид - `rfpm_id`
документа, поэтому строка равна сумме месяцев. Помесячные суммы образца
сошлись до копейки; численность по 0701/0705 в паре месяцев на единицы-десятки
больше образца (EAV считалась в момент заполнения).

Период - с начала года по выбранный месяц; в оригинале показывались все 12
месяцев года из EAV, при этом «С начала года» шла только до 01.08.2025.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '8007'
report_name = ('Ежемесячные сведения о социальных выплатах {period} '
               '(8007, составлен без технического задания)')

_period_label = make_period_label({7: 'в {year} году'})

_CNT = 'Число получателей (человек)'
_SUM = 'Сумма выплат (тенге)'

# (код вида, подпись) - порядок колонок оригинала: 0702, 0701, 0703, 0704, 0705
_TYPES = [
    ('0702', 'по случаю утраты трудоспособности'),
    ('0701', 'по случаю потери кормильца'),
    ('0703', 'по случаю потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, с '
             'усыновлением (удочерением) новорожденного ребенка(детей)'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

COLUMNS = [
    Col('Регион', 'region', 'text', 18),
    Group('Всего', [
        Col(_CNT, 'cnt_all', 'int', 14, align='center'),
        Col(_SUM, 'sum_all', 'money', 22),
    ]),
    Group('в том числе по видам социальных выплат', [
        Group(f'{code}\n{title}', [
            Col(_CNT, f'cnt_{code}', 'int', 14, align='center'),
            Col(_SUM, f'sum_{code}', 'money', 22),
        ]) for code, title in _TYPES
    ]),
]

_PIVOT = ',\n'.join(
    f"       max(case when rfpm = '{code}' then cnt end) cnt_{code},\n"
    f"       max(case when rfpm = '{code}' then sm end) sum_{code}"
    for code, _ in _TYPES)

STMT = f"""
with base as (
    select /*+parallel(4)*/
           trunc(d.pncp_date, 'MM') mon,
           substr(d.rfpm_id, 1, 4) rfpm,
           d.pncd_id,
           d.pay_sum + d.sum_debt sm
      from pnpd_document d
     where d.pncp_date >= :y_from
       and d.pncp_date <  :d_to
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
),
m as (
    select mon, rfpm, count(distinct pncd_id) cnt, sum(sm) sm
      from base
     group by mon, rfpm
),
y as (
    select date '9999-01-01' mon, rfpm, count(distinct pncd_id) cnt, sum(sm) sm
      from base
     group by rfpm
),
u as (
    select mon, rfpm, cnt, sm from m
    union all
    select mon, rfpm, cnt, sm from y
)
select decode(mon, date '9999-01-01', 'С начала года',
              initcap(trim(to_char(mon, 'fmMonth', 'NLS_DATE_LANGUAGE=RUSSIAN')))) region,
       sum(cnt) cnt_all,
       sum(sm) sum_all,
{_PIVOT},
       decode(mon, date '9999-01-01', 1, 0) bold
  from u
 group by mon
 order by mon
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    bold_key='bold',
)
