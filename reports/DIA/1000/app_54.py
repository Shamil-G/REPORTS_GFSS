# -*- coding: utf-8 -*-
"""Приложение 54. Назначенные СВур (уход за ребёнком до 1 года, СВ 0705),
доведённые до размера ГСП, - сравнение выбранного квартала и того же
квартала прошлого года (плюс "с начала года" для обоих, если квартал не
первый).

Перенос REP_STAT_EXTEND.app_54_spool + Rep_app_54 (pck_utf8.sql,
10981-11431). Реестр: группа 1540, обе строки (1541 и 1542) зовут один и
тот же app_54_2k('m') - дубль в реестре, переносится один раз (см.
migration-plan.md, "Дубли и особые случаи"). Только тип периода 2
(квартал) - структура отчёта (квартал vs тот же квартал год назад, плюс
накопительный итог с начала года) специфична для квартала, остальные типы
периода здесь не имеют смысла и не добавлены (в отличие от большинства
других отчётов раздела).

Единственный отчёт семейства, где "период" - это НЕ границы одного
запроса, а точка отсчёта для ЧЕТЫРЁХ разных периодов сразу: тот же квартал
год назад, с начала прошлого года по конец того же квартала, сам квартал,
с начала текущего года. Все четыре выводятся из :d_from/:d_to/:y_from
(которые framework и так считает через period=True) простой сдвижкой на
12 месяцев - ни доп. параметров, ни доп. запросов к period_bounds не
понадобилось.

Строки "с начала года" (обе) не выводятся, когда выбранный квартал - I
(date_spare=1): тогда "с начала года" совпадает с самим кварталом, и
оригинал их не показывает (строки 11337 и 11386 - ветки date_spare_ in
(2,3,4), а не 1..4). Проверяется прямо в SQL: :d_from = :y_from истинно
только для I квартала (d_from совпадает с началом года).

Как и в app_47/48/50: НЕТ явного зануления через "если 0 то пусто" -
Rep_app_54 просто не печатает ячейку, если для неё не нашлось СТРОКИ в
EAV (а строка не создаётся, если group by отдал ноль строк - то есть за
период не было вообще ни одной СВур). Соответствует `having count(1)>0`
на каждый под-период здесь: если по периоду нет ни одной записи, вся
строка целиком не появляется - так же, как в оригинале.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'APP.54'
# cSPTitle дословно (строки 11156-11157, заканчивается ", " - подпись
# периода продолжает фразу без своей запятой).
report_name = ('Сведения о количестве назначенных социальных выплатах по '
               'уходу за ребенком по достижении им возраста 1 года, '
               '{period}')

# Begin блок Rep_app_54 (строка 11427) - без ведущей запятой (она уже
# в cSPTitle).
_period_label = make_period_label({
    2: 'за {n} квартал {year} года ',
})

COLUMNS = [
    Col('Период', 'period', 'text', 26),
    Col('Количество назначенных СВур, всего (чел.)', 'cnt_svur', 'int'),
    Col('Количество назначенных СВур, доведенных до размера ГСП (чел.)',
        'cnt_uptogsp', 'int'),
    Col('Сумма СВур, назначенная на уровне ГСП (тенге)', 'sm_uptogsp',
        'money', 18),
    Col('Сумма СВур, рассчитанная на основании поступивших социальных '
        'отчислений (тенге)', 'sm_sumcalc', 'money', 18),
    Col('Сумма СВур, доведенная до размера ГСП (тенге)', 'sm_sumdop',
        'money', 18),
]

FOOTNOTE = ('* - параметры в периоде определяются по дате утверждения '
           'назначения СВ Департаментами по контролю и социальной защите')

# :d_from / :d_to - границы выбранного квартала (:d_to исключительная),
# :y_from - начало текущего года. Прошлогодние периоды получаются сдвигом
# на 12 месяцев назад - тот же приём для обеих пар (квартал/с начала года).
#
# Метрики: cnt_svur - все назначенные СВур за период; cnt_uptogsp/
# sm_uptogsp/sm_sumcalc/sm_sumdop - только те, что доведены до ГСП
# (sum_dop > 0), количество и три денежные величины.
#
# having count(1) > 0 - период без единой СВур не должен появиться строкой
# вообще (как в оригинале при пустом group by).
STMT = """
with q_prev as (
    select count(1)                                             cnt_svur,
           sum(case when sum_dop > 0 then 1 else 0 end)         cnt_uptogsp,
           sum(case when sum_dop > 0 then sum_all  else 0 end)  sm_uptogsp,
           sum(case when sum_dop > 0 then sum_calc else 0 end)  sm_sumcalc,
           sum(case when sum_dop > 0 then sum_dop  else 0 end)  sm_sumdop
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and trunc(s.date_approve) >= add_months(:d_from, -12)
       and trunc(s.date_approve) <  add_months(:d_to, -12)
    having count(1) > 0
),
q_now as (
    select count(1)                                             cnt_svur,
           sum(case when sum_dop > 0 then 1 else 0 end)         cnt_uptogsp,
           sum(case when sum_dop > 0 then sum_all  else 0 end)  sm_uptogsp,
           sum(case when sum_dop > 0 then sum_calc else 0 end)  sm_sumcalc,
           sum(case when sum_dop > 0 then sum_dop  else 0 end)  sm_sumdop
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
    having count(1) > 0
),
ytd_prev as (
    select count(1)                                             cnt_svur,
           sum(case when sum_dop > 0 then 1 else 0 end)         cnt_uptogsp,
           sum(case when sum_dop > 0 then sum_all  else 0 end)  sm_uptogsp,
           sum(case when sum_dop > 0 then sum_calc else 0 end)  sm_sumcalc,
           sum(case when sum_dop > 0 then sum_dop  else 0 end)  sm_sumdop
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and trunc(s.date_approve) >= add_months(:y_from, -12)
       and trunc(s.date_approve) <  add_months(:d_to, -12)
    having count(1) > 0
),
ytd_now as (
    select count(1)                                             cnt_svur,
           sum(case when sum_dop > 0 then 1 else 0 end)         cnt_uptogsp,
           sum(case when sum_dop > 0 then sum_all  else 0 end)  sm_uptogsp,
           sum(case when sum_dop > 0 then sum_calc else 0 end)  sm_sumcalc,
           sum(case when sum_dop > 0 then sum_dop  else 0 end)  sm_sumdop
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and trunc(s.date_approve) >= :y_from
       and trunc(s.date_approve) <  :d_to
    having count(1) > 0
)
select 1 ord,
       to_char(:d_from, 'Q') || ' квартал ' || to_char(add_months(:d_from, -12), 'YYYY') || ' года' period,
       cnt_svur, cnt_uptogsp, sm_uptogsp, sm_sumcalc, sm_sumdop
  from q_prev
union all
select 2,
       'с начала ' || to_char(add_months(:d_from, -12), 'YYYY') || ' года',
       cnt_svur, cnt_uptogsp, sm_uptogsp, sm_sumcalc, sm_sumdop
  from ytd_prev
 where :d_from != :y_from
union all
select 3,
       to_char(:d_from, 'Q') || ' квартал ' || to_char(:d_from, 'YYYY') || ' года',
       cnt_svur, cnt_uptogsp, sm_uptogsp, sm_sumcalc, sm_sumdop
  from q_now
union all
select 4,
       'с начала ' || to_char(:d_from, 'YYYY') || ' года',
       cnt_svur, cnt_uptogsp, sm_uptogsp, sm_sumcalc, sm_sumdop
  from ytd_now
 where :d_from != :y_from
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
