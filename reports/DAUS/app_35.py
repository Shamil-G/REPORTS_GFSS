# -*- coding: utf-8 -*-
"""Приложение 35. Состав участников СОСС в разрезе "возраст" (плюс пол).

Перенос REP_STAT_EXTEND.app_34_35_spool + Rep_app_34_35(..., iRepNum='age')
(pck_utf8.sql, 3143-3826). Реестр: группа 1350, вызов app_34_35_1m('age','m')
и аналоги по типам периода 1-5. Тип 7 в реестре для 'age' не зарегистрирован
(пробел в реестре, см. migration-plan.md), но не запрещён и здесь доступен
по общему решению "все 7 типов периода доступны любому отчёту".

Общее устройство и источник данных - как у app_34.py (парная процедура,
разный SQL/колонки, поэтому два модуля, не флаг). Отличие - строки строятся
по паре (регион, возрастная группа), а не только по региону: возраст - это
width_bucket(лет, 20, 65, 9) + 1, 11 корзин (строка 3172), подписи берутся
из group_age2 (строка 3382). Фиксированный набор строк - все регионы (+ '00'
"Не определен") x все 11 корзин, порождается CROSS JOIN с CONNECT BY, а не
из данных - иначе строки без данных пропадут.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.35'
# Дословно из исходника (cSPTitle, строки 3325-3327 + Prn_SP, строка 3501):
# "Сведения о  " (два пробела) + cSPTitle (начинается с пробела) + период -
# на выходе три пробела подряд перед "составе". Сохранено как в оригинале.
report_name = ('Сведения о   составе участников системы обязательного '
               'социального страхования и суммах социальных отчислений, '
               'поступивших в АО"Государственный фонд социального '
               'страхования", за {period}')

_MONTH_WORD = {1: 'месяц', 2: 'месяца', 3: 'месяца', 4: 'месяца'}


def _month_word(s: int) -> str:
    return _MONTH_WORD.get(s, 'месяцев')


# Те же шаблоны подписи периода, что и у app_34 (Begin блок Rep_app_34_35
# общий для обоих разрезов, строки 3752-3771; пробел между месяцем и годом
# в типе 1 - сознательное отступление от оригинала, см. app_34.py).
_base_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: '  9 месяцев {year} года ',
    5: ' {year} год ',
    7: ' {n} MONTHWORD {year} год ',
})


def _period_label(rep_year, date_type, date_start=None):
    label = _base_label(rep_year, date_type, date_start)
    if int(date_type) == 7:
        label = label.replace('MONTHWORD', _month_word(int(date_start)))
    return label


_COUNT = 'Число участников (человек)'
_SUM = 'Сумма социальных отчислений (тенге)'
_PEN = 'Пеня (тенге)'
_TOTAL = 'Всего'
_OF_WHICH = 'в том числе'
_M = 'мужчины'
_F = 'женщины'

COLUMNS = [
    Col('Области, города', 'reg', 'text', 30),
    Col('Возраст', 'age', 'text', 14),
    Group(_COUNT, [
        Col(_TOTAL, 'cnt_all', 'int'),
        Group(_OF_WHICH, [
            Col(_M, 'cnt_m', 'int'),
            Col(_F, 'cnt_f', 'int'),
        ]),
    ]),
    Group(_SUM, [
        Col(_TOTAL, 'sum_all', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'sum_m', 'money', 18),
            Col(_F, 'sum_f', 'money', 18),
        ]),
    ]),
    Group(_PEN, [
        Col(_TOTAL, 'pen_all', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'pen_m', 'money', 18),
            Col(_F, 'pen_f', 'money', 18),
        ]),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# См. подробный разбор источника в app_34.py - здесь то же самое плюс
# возрастная корзина (age) в located/agg/pivot и в наборе строк.
STMT = """
with raw_member as (
    select /*+parallel(4)*/
           a.sicid, a.knp, a.sum_pay,
           first_value(a.p_rnn) over (
               partition by a.sicid
               order by decode(a.knp, '012', 0, 1), a.pay_date_gfss desc
               rows between unbounded preceding and unbounded following) last_rnn,
           first_value(a.pay_date_gfss) over (
               partition by a.sicid
               order by decode(a.knp, '012', 0, 1), a.pay_date_gfss desc
               rows between unbounded preceding and unbounded following) last_date
    from si_member_2 a
    where a.pay_date_gfss >= :d_from
    and a.pay_date_gfss <  :d_to
),
member as (
    select r.sicid, r.knp, r.sum_pay, r.last_rnn, p.sex,
           trunc(months_between(r.last_date, p.birthdate) / 12) let
    from raw_member r, person p
    where r.sicid = p.sicid(+)
),
located as (
    select /*+parallel(2)*/ m.sicid, m.knp, m.sum_pay, m.sex,
           to_char(width_bucket(m.let, 20, 65, 9) + 1, 'fm00') age,
           substr(nvl(br.rfbn_id, '00'), 1, 2) reg_id
    from member m, rfon_organization rf, cato_branch br
    where m.last_rnn = rf.bin(+)
    and rf.cato    = br.code(+)
),
agg as (
    select /*+parallel(4)*/ 
           reg_id, age, sex, knp,
           count(distinct sicid) cnt,
           sum(sum_pay)          summ
    from located
    group by reg_id, age, sex, knp
),
pivot as (
    select reg_id, age,
           sum(case when sex = 1 and knp = '012' then cnt  end) cnt_m,
           sum(case when sex = 0 and knp = '012' then cnt  end) cnt_f,
           sum(case when sex = 1 and knp = '012' then summ end) sum_m,
           sum(case when sex = 0 and knp = '012' then summ end) sum_f,
           sum(case when sex = 1 and knp = '017' then summ end) pen_m,
           sum(case when sex = 0 and knp = '017' then summ end) pen_f
    from agg
    group by reg_id, age
),
regions as (
    select rfrg_id reg_id, 0 ord from RFRG_REGION
    union all
    select '00', 1 from dual
),
ages as (
    select to_char(level, 'fm00') age from dual connect by level <= 11
)
select /*+parallel(4)*/ 
       nvl(rr.name, 'Не определен')         reg,
       ga.age                               age,
       nvl(v.cnt_m, 0) + nvl(v.cnt_f, 0)    cnt_all,
       nvl(v.cnt_m, 0)                      cnt_m,
       nvl(v.cnt_f, 0)                      cnt_f,
       nvl(v.sum_m, 0) + nvl(v.sum_f, 0)    sum_all,
       nvl(v.sum_m, 0)                      sum_m,
       nvl(v.sum_f, 0)                      sum_f,
       nvl(v.pen_m, 0) + nvl(v.pen_f, 0)    pen_all,
       nvl(v.pen_m, 0)                      pen_m,
       nvl(v.pen_f, 0)                      pen_f
  from regions r, ages a, RFRG_REGION rr, group_age2 ga, pivot v
 where rr.rfrg_id(+) = r.reg_id
   and ga.id_age(+)  = a.age
   and v.reg_id(+)   = r.reg_id
   and v.age(+)      = a.age
 order by r.ord, r.reg_id, a.age
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
)
