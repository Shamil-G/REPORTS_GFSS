# -*- coding: utf-8 -*-
# ============================================================
# ЗАМЕНЁН (дублируется) - по сообщению Заказчика (02.10.2026).
# Заменяющий отчёт: консолидированные, 7CP.
# Закомментирован в model/list_reports.py (группа «Согласно Приказа Минтруда (REP_MINTRUD)»), ключ 03. Код не удалён - для итоговой сверки.
# Oracle: REP_MINTRUD.Fill_F5, Rep_5m/5k/5hy/5_9m/5y
# ============================================================
"""============================================================
REP_MINTRUD (Rep_Mintrud.pck) - см. заглавие f3.py про разделение с
REP_STAT_EXTEND.
============================================================

Форма 5 (Rep_Mintrud.Fill_F5 + Rep_5m/_5k/_5hy/_5_9m/_5y). Средний размер
назначенных социальных выплат из ГФСС, по регионам и видам СВ.

Перенос Rep_Mintrud.pck (строки 854-1065 - Fill_F5/Prn_F5/Rep_5*). Реестр:
rep_mintrud.fill_f5(rep_year, date_type, date_spare) - подтверждён
сборочным логом (04.09.2026). Типы периода 1-5, как в F4.

Заголовок отчёта в исходнике использует ТУ ЖЕ строку `cF4Title`, что и
Форма 4 (отдельной константы для формы 5 в пакете нет, строки 977-1065) -
это не ошибка переноса, дословное повторение оригинала.

Источник - `cur_F5`: `payment_history` + `pnpd_document`,
`Group By Grouping Sets((reg, rfpm), (rfpm))` - то есть считает СРАЗУ два
уровня: средний размер по (регион, вид выплаты) и отдельно средний размер
по виду выплаты БЕЗ разреза по региону by (Всего по республике, region is
null). Второй уровень - не сумма или простое среднее первого, а
самостоятельный `avg()` по всем строкам вида выплаты сразу, независимо от
региона. Здесь оба уровня считаются двумя отдельными агрегатами
(`by_reg`/`by_all`) вместо `GROUPING SETS`, чтобы не городить `GROUPING()`
в пивоте - результат тот же.

Строка "Всего по республике" - `region is null` в EAV (`nvl(i.region,
cRegAll)`, строка 943) сопоставляется с кодом 'ZZ', здесь просто отдельный
литерал в конце списка строк.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'MINTRUD.F5'
report_name = ('Сведения о числе получателей и суммах социальных выплат '
               'из АО "Государственный фонд социального страхования" за '
               '{period}')

_period_label = make_period_label({
    1: '{month} {year} года',
    2: '{n} квартал {year} года',
    3: '{n} полугодие {year} года',
    4: '9 месяцев {year} года',
    5: '{year} год',
})

# Порядок и заголовки видов выплат - те же, что в f4.py.
_TYPES = [
    ('0702', 'по случаю утраты трудоспособности'),
    ('0701', 'по случаю потери кормильца'),
    ('0703', 'по случаю потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, '
             'с усыновлением (удочерением) новорожденного ребенка(детей)'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

COLUMNS = [
    Col('Регион', 'reg', 'text', 30),
    Group('Средний размер назначенных социальных выплат, тенге', [
        Col(title, f'avg_{code}', 'money', 20) for code, title in _TYPES
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
STMT = """
with base as (
    select ph.sum_pay,
           substr(ph.rfbn_id, 1, 2) reg,
           substr(ph.rfpm_id, 1, 4) rfpm
      from payment_history ph, pnpd_document pd
     where pd.pnpd_id = ph.pnpd_id
       and pd.act_month >= :d_from
       and pd.act_month <  :d_to
       and substr(pd.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
       and pd.ridt_id in (6, 7, 8)
       and pd.status in (0, 1, 2, 3, 5, 7)
       and pd.pnsp_id > 0
),
by_reg as (
    select reg, rfpm, round(avg(sum_pay), 2) sz_avg
      from base
     group by reg, rfpm
),
by_all as (
    select rfpm, round(avg(sum_pay), 2) sz_avg
      from base
     group by rfpm
),
pivot_reg as (
    select reg,
           sum(case when rfpm = '0702' then sz_avg end) avg_0702,
           sum(case when rfpm = '0701' then sz_avg end) avg_0701,
           sum(case when rfpm = '0703' then sz_avg end) avg_0703,
           sum(case when rfpm = '0704' then sz_avg end) avg_0704,
           sum(case when rfpm = '0705' then sz_avg end) avg_0705
      from by_reg
     group by reg
),
pivot_all as (
    select sum(case when rfpm = '0702' then sz_avg end) avg_0702,
           sum(case when rfpm = '0701' then sz_avg end) avg_0701,
           sum(case when rfpm = '0703' then sz_avg end) avg_0703,
           sum(case when rfpm = '0704' then sz_avg end) avg_0704,
           sum(case when rfpm = '0705' then sz_avg end) avg_0705
      from by_all
)
select rr.rfrg_id || ' - ' || rr.name reg, 0 ord,
       p.avg_0702, p.avg_0701, p.avg_0703, p.avg_0704, p.avg_0705
  from RFRG_REGION rr, pivot_reg p
 where rr.rfrg_id != '00'
   and p.reg(+) = rr.rfrg_id
union all
select 'Всего по республике', 1,
       avg_0702, avg_0701, avg_0703, avg_0704, avg_0705
  from pivot_all
 order by ord, reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=False,
    period_label=_period_label,
)
