# -*- coding: utf-8 -*-
"""Приложение 52. СВ по беременности и родам, усыновлению и по уходу за ребенком,
в разрезе стажа участия в СОСС.

Перенос REP_STAT_EXTEND.app_52_spool + Rep_app_52 (pck_utf8.sql, 10075-10460).
Реестр: группа 1520, все 5 типов периода зарегистрированы (app_52_1m..._5y, 'm').

Отличие от плана: в docs/migration-plan.md отчёт отнесён к "плоским, один
уровень шапки" - это была предварительная прикидка до разбора исходника.
На деле шапка двухуровневая, как у app_50/51/55: три группы (СВбр, из них по
уходу за ребенком, по усыновлению) по две колонки (количество/сумма) в каждой.

Строки - фиксированный стаж участия в СОСС от 1 до 61 (61 - "61 и более"),
порождаются CONNECT BY и внешним соединением с агрегатом, а не из данных: в
оригинале (Prn_SP, r In 1..61) стаж 0 существует в EAV, но не выводится - цикл
начинается с 1. Это сознательно воспроизведено: 0 не показывается.

Зануление - как в оригинале (PrnOneGoup): что для отсутствующей, что для
фактически нулевой пары "стаж/показатель" печатается пустая ячейка -
blank_zero=True покрывает оба случая одинаково через nvl(...,0) в SQL.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.52'
# cSPTitle дословно (строка 10259-10261 исходника; перенос строки в PL/SQL -
# артефакт форматирования кода, в HTML он схлопывался в пробел).
report_name = ('Количество назначенных социальных выплат по беременности и '
               'родам, усыновлению (удочерению) ребенка (детей) и по уходу '
               'за ребенком по достижении им возраста одного года{period}')

# PH_per (строки 10395-10409): ", за <период> <год> года " - подпись без
# пробела перед годом у месячного периода и с цифрой (не римской) у квартала
# и полугодия. Двойной пробел у "9 месяцев" - тоже из оригинала
# (', за ' || ' 9 месяцев ' - два пробела на стыке), сохранён дословно.
_period_label = make_period_label({
    1: ', за {Month} {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за  9 месяцев {year} года ',
    5: ', за {year} год ',
})

_COUNT_SUM = 'количество получателей (чел)'
_MONEY_SUM = 'сумма выплат (тенге)'

COLUMNS = [
    Col('Стаж участия в СОСС', 'stag', 'text', 20, align='center'),
    Col('Общая сумма социальных отчислений (тенге)', 'sum_co', 'money', 20),
    Group('по беременности и родам (СВбр)', [
        Col(_COUNT_SUM, 'cnt4', 'int'),
        Col(_MONEY_SUM, 'sum4', 'money', 18),
    ]),
    Group('из них получают: по уходу за ребенком по достижении им возраста '
          'одного года', [
        Col(_COUNT_SUM, 'cnt5', 'int'),
        Col(_MONEY_SUM, 'sum5', 'money', 18),
    ]),
    Group('по усыновлению(удочерению) новорожденного ребенка(детей)', [
        Col(_COUNT_SUM, 'cnt3', 'int'),
        Col(_MONEY_SUM, 'sum3', 'money', 18),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# У отчёта нет колонок "с начала года" - в оригинале Rep_app_52 читает EAV
# строго по одному date_type/date_spare, без накопления, поэтому :y_from не
# нужен.
#
# aa - назначения СВбр (0704), bb - назначения по уходу за ребёнком (0705),
# соединены внешне по sicp_id с окном "risk_date .. risk_date+9 месяцев"
# (строки 10141-10146). gp (si_member_2) даёт стаж участия (число уникальных
# pay_month) и сумму отчислений по тем же условиям, что и в spool.
#
# rfpm=3 означает 070403 (усыновление/удочерение) - 6-й символ rfpm_id,
# сохранено как в оригинале (rfpm, строка 10131): 070403 - подмножество 0704,
# поэтому cnt4/sum4 уже включают cnt3/sum3, а не суммируются отдельно.
#
# decode(bb.rfpm_id, null, null, 'Y') эквивалентен оригинальному
# decode(bb.rfpm_id,'','','Y'): в Oracle пустая строка и null неразличимы,
# decode их приравнивает - семантика та же (нет соответствия в bb -> null).
STMT = """
with src as (
    select /*+parallel(4)*/ aa.sicp_id,
           decode(bb.rfpm_id, null, null, 'Y')                     with_0705,
           case when substr(aa.rfpm_id, 6, 1) = 3 then 3 else 4 end rfpm,
           aa.sum_all sm_0704,
           bb.sum_all sm_0705,
           count(distinct gp.pay_month) cnt_people,
           sum(gp.sum_pay)               sm_co
      from (select /*+parallel(2)*/ s.rfbn_id, s.rfpm_id, s.sum_all, s.sicp_id, s.risk_date,
                   s.date_address, trunc(s.date_approve) date_calc
              from sipr_maket_first_approve_2 s
             where substr(s.rfpm_id, 1, 4) = '0704') aa,
           (select /*+parallel(2)*/ s.rfbn_id, s.rfpm_id, s.sum_all, s.sicp_id, s.risk_date,
                   s.date_address, trunc(s.date_approve) date_calc
              from sipr_maket_first_approve_2 s
             where substr(s.rfpm_id, 1, 4) = '0705') bb,
           si_member_2 gp
     where aa.date_calc >= :d_from
       and aa.date_calc <  :d_to
       and gp.sicid = aa.sicp_id
       and bb.sicp_id(+) = aa.sicp_id
       and nvl(bb.risk_date, aa.risk_date) between aa.risk_date
                                              and add_months(aa.risk_date, 9)
       and gp.pay_date < trunc(aa.date_address, 'MONTH')
       and gp.pay_month < aa.risk_date
       and gp.knp = '012'
     group by aa.sicp_id, decode(bb.rfpm_id, null, null, 'Y'),
              case when substr(aa.rfpm_id, 6, 1) = 3 then 3 else 4 end,
              aa.sum_all, bb.sum_all
),
agg as (
    select /*+parallel(4)*/
           least(cnt_people, 61)                             stag,
           sum(sm_co)                                        sum_co,
           count(1)                                           cnt4,
           sum(sm_0704)                                       sum4,
           count(with_0705)                                    cnt5,
           sum(sm_0705)                                        sum5,
           sum(case when rfpm = 3 then 1 else 0 end)           cnt3,
           sum(case when rfpm = 3 then sm_0704 else 0 end)     sum3
      from src
     group by least(cnt_people, 61)
)
select case when v.stag = 61 then '61 и более' else to_char(v.stag) end stag,
       nvl(a.sum_co, 0) sum_co,
       nvl(a.cnt4, 0)   cnt4,
       nvl(a.sum4, 0)   sum4,
       nvl(a.cnt5, 0)   cnt5,
       nvl(a.sum5, 0)   sum5,
       nvl(a.cnt3, 0)   cnt3,
       nvl(a.sum3, 0)   sum3
  from (select level stag from dual connect by level <= 61) v,
       agg a
 where a.stag(+) = v.stag
 order by v.stag
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
)
