# -*- coding: utf-8 -*-
"""============================================================
REP_MINTRUD (Rep_Mintrud.pck) - отдельный source-пакет, статутные отчёты
по Приказу Министра труда. Своя EAV-таблица (rptb_rep_mintrud_data),
свои источники (pnpd_document/pnpt_payment/payment_history/si_member_2
напрямую) - НЕ путать с app_NN из REP_STAT_EXTEND. См. верхний уровень
docs/migration-plan.md, раздел "Пакет 2: REP_MINTRUD".
============================================================

Форма 3 (Rep_Mintrud.Fill_F3 + Rep_3m/_3k/_3hy/_3_9m/_3y/_3_24m).
Суммы социальных отчислений и пени, поступивших в ГФСС, и число
участников СОСС, по регионам.

Перенос Rep_Mintrud.pck (строки 403-627 - Fill_F3/Prn_F3/Rep_3*).
Реестр вызовов: rep_mintrud.fill_f3(rep_year, date_type, date_spare) -
подтверждён сборочным логом (04.09.2026) как живой.

Источник - `cur_F3` (единственный ДЕЙСТВУЮЩИЙ курсор в пакете; `cur_F3_old`
и `cur_F3_older` - предыдущие версии, оставлены закомментированными в
исходнике как история, не переносятся). Регион участника определяется
как в app_34/35 REP_STAT_EXTEND: последняя по времени организация
(`first_value(...) over (partition by sicid order by decode(knp,'012',0,1),
pay_date desc)`), только здесь цепочка короче - `rfon_organization` →
`rfbn_cato` (не `cato_branch`). Не нашедшие организацию/регион - код 'ZZ'
("Не определена", а не "00"/"Не определен", как в REP_STAT_EXTEND - в этом
пакете своя мнемоника).

Метрики: `cnt` - число уникальных участников с начислением knp='012' за
период; `sm_012` - сумма этих начислений; `sm_017` - сумма пени (knp='017',
без отдельного счётчика людей - в исходнике для 017 count не считается).

Зануление - через `nullif(значение, 0)` в самом Rep.td (строки 493-496
оригинала): и отсутствие данных, и настоящий ноль дают пустую ячейку -
поэтому blank_zero=True.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label, period_bounds
from util.xlsx_report import build_report, Col

report_code = 'MINTRUD.F3'
# cF3Title дословно (строки 79-82 исходника, теги <br>/<div> оригинала не
# переносятся - как и во всех модулях REP_STAT_EXTEND, оформление берёт на
# себя framework, а не сама официальная формулировка). "Приложение №N" /
# "Форма №5-x" / блок со ссылкой на приказ (cOrderName) тоже не переносятся -
# тот же принцип, что и с "Форма № XX" в REP_STAT_EXTEND: это служебная
# нумерация бланка, не часть текста отчёта.
report_name = ('Сведения о суммах социальных отчислений и пени, '
               'поступивших в АО "Государственный фонд социального '
               'страхования", и числе участников системы обязательного '
               'социального страхования за {period}')

# Дословные фразы периода из Rep_3m/_3k/_3hy/_3_9m/_3y (строки 523-621):
# месяц - строчными буквами (to_char(...,'month') в Oracle даёт нижний
# регистр, в отличие от v_rep_list_month.cap в REP_STAT_EXTEND, который
# давал заглавную) и без пробела перед годом; год - "год", не "года".
_base_label = make_period_label({
    1: '{month}{year} года',
    2: '{n} квартал {year} года',
    3: '{n} полугодие {year} года',
    4: '9 месяцев {year} года',
    5: '{year} год',
    6: 'последние 24 месяца по состоянию на D_TO года',
})


def _period_label(rep_year, date_type, date_start=None):
    label = _base_label(rep_year, date_type, date_start)
    if int(date_type) == 6:
        _, d_to = period_bounds(rep_year, 6, date_start)
        label = label.replace('D_TO', d_to.strftime('%d.%m.%Y'))
    return label


COLUMNS = [
    Col('Регион', 'reg', 'text', 30),
    Col('Сумма социальных отчислений, тенге', 'sm_012', 'money', 20),
    Col('Пеня, тенге', 'sm_017', 'money', 18),
    Col('Число участников, человек', 'cnt', 'int'),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# member_win - строки si_member_2 в периоде (окно pay_date на месяц шире,
# как и в оригинале - строки 108-109 исходника).
# located - регион по последней организации участника (rfon_organization
# -> rfbn_cato), 'ZZ' если не нашлась.
STMT = """
with member_win as (
    select m.sicid, m.knp, m.sum_pay,
           first_value(m.p_rnn) over (
               partition by m.sicid
               order by decode(m.knp, '012', 0, 1), m.pay_date desc
               rows between unbounded preceding and unbounded following) p_rnn
      from si_member_2 m
     where m.pay_date_gfss >= :d_from
       and m.pay_date_gfss <  :d_to
       and m.pay_date       >= add_months(:d_from, -1)
       and m.pay_date       <  :d_to
),
located as (
    select s.sicid, s.knp, s.sum_pay,
           substr(nvl(cb.rfbn_id, 'ZZ'), 1, 2) reg_id
      from member_win s, rfon_organization rf, rfbn_cato cb
     where s.p_rnn = rf.bin(+)
       and substr(rf.cato, 1, 4) = cb.cato_reg(+)
),
agg as (
    select reg_id,
           count(distinct case when knp = '012' then sicid end) cnt,
           sum(case when knp = '012' then sum_pay end)          sm_012,
           sum(case when knp = '017' then sum_pay end)          sm_017
      from located
     group by reg_id
)
select nvl(rr.name, 'Не определена') reg,
       a.sm_012                       sm_012,
       a.sm_017                       sm_017,
       a.cnt                          cnt
  from (select rfrg_id reg_id, 0 ord from RFRG_REGION where rfrg_id != '00'
        union all
        select 'ZZ', 1 from dual) v,
       RFRG_REGION rr,
       agg a
 where rr.rfrg_id(+) = v.reg_id
   and a.reg_id(+)   = v.reg_id
 order by v.ord, v.reg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
)
