# -*- coding: utf-8 -*-
"""Приложение 37. Число страховых случаев и суммы соцвыплат по видам,
в разрезе пола и возраста (СВ 0701-0705).

Перенос REP_STAT_EXTEND.app_36_37_spool + Rep_app_36_37(..., iRepNum='age')
(pck_utf8.sql, 3873-4560). Реестр: группа 1370, вызов app_36_37_1m('age','m')
и аналоги по типам периода 1-5.

Общее устройство - как у app_36.py (см. там подробный разбор источника и
почему это два модуля, а не флаг). Отличие - строки строятся по паре
(регион, возрастная группа): возраст - width_bucket(лет, 20, 65, 9) + 1,
11 корзин (строка 3908), лет считается от risk_date (строка 3910), подписи
берутся из group_age2. Фиксированный набор строк - все регионы x все 11
корзин, порождается CROSS JOIN с CONNECT BY, а не из данных.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.37'
report_name = ('Сведения о числе получателей  и суммах социальных выплат '
               '(в разрезе пола и возраста), {period}')

_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: '  9 месяцев {year} года ',
    5: ' {year} год ',
})

_PAY_TYPES = [
    ('0701', '1', 'по случаю потери кормильца', True),
    ('0702', '2', 'по случаю утраты трудоспособности', False),
    ('0703', '3', 'по случаю потери работы', False),
    ('0704', '4', 'на случай потери дохода в связи с беременностью и родами, '
                  'с усыновлением (удочерением) новорожденного ребенка '
                  '(детей)', False),
    ('0705', '5', 'на случай потери дохода в связи с уходом за ребенком по '
                  'достижении им возраста 1 года', False),
]


def _pay_group(suffix, title, footnote):
    money_title = 'Всего Сумма Выплат *(тенге)' if footnote \
        else 'Всего Сумма Выплат (тенге)'
    return Group(title, [
        Col('Всего СТРАХОВЫХ СЛУЧАЕВ', f'all_cnt{suffix}', 'int'),
        Group('в том числе', [
            Col('Мужчин', f'cnt_m{suffix}', 'int'),
            Col('Женщин', f'cnt_w{suffix}', 'int'),
        ]),
        Col(money_title, f'summ_all{suffix}', 'money', 18),
        Group('в том числе', [
            Col('Мужчин', f'summ_m{suffix}', 'money', 18),
            Col('Женщин', f'summ_w{suffix}', 'money', 18),
        ]),
    ])


COLUMNS = [
    Col('Области, города', 'reg', 'text', 30),
    Col('Возраст', 'age', 'text', 14),
    *[_pay_group(suffix, title, footnote)
      for _, suffix, title, footnote in _PAY_TYPES],
    Group('Число СТРАХОВЫХ СЛУЧАЕВ', [
        Col('Всего', 'all_all_cnt', 'int'),
        Group('в том числе', [
            Col('Мужчин', 'all_cnt_m', 'int'),
            Col('Женщин', 'all_cnt_w', 'int'),
        ]),
    ]),
    Group('Сумма Выплат (тенге)', [
        Col('Всего', 'sum_summ_all', 'money', 18),
        Group('в том числе', [
            Col('Мужчин', 'all_summ_m', 'money', 18),
            Col('Женщин', 'all_summ_w', 'money', 18),
        ]),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# См. подробный разбор в app_36.py - здесь то же самое плюс возрастная
# корзина (age) в base/agg/pivot и в наборе строк (регион x 11 корзин).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           substr(s.rfpm_id, 1, 4) rfpm,
           s.sum_all,
           pr.sex,
           to_char(width_bucket(
               trunc(months_between(s.risk_date, pr.birthdate) / 12),
               20, 65, 9) + 1, 'fm00') age
      from sipr_maket_first_approve_2 s, person pr
     where trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
       and s.sicp_id = pr.sicid
       and substr(s.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
),
agg as (
    select reg_id, age, rfpm, sex,
           count(1)     cnt,
           sum(sum_all) summ
      from base
     group by reg_id, age, rfpm, sex
),
pivot as (
    select reg_id, age,
           sum(case when rfpm = '0701' and sex = 1 then cnt  end) cnt_m1,
           sum(case when rfpm = '0701' and sex = 0 then cnt  end) cnt_w1,
           sum(case when rfpm = '0701' and sex = 1 then summ end) summ_m1,
           sum(case when rfpm = '0701' and sex = 0 then summ end) summ_w1,
           sum(case when rfpm = '0702' and sex = 1 then cnt  end) cnt_m2,
           sum(case when rfpm = '0702' and sex = 0 then cnt  end) cnt_w2,
           sum(case when rfpm = '0702' and sex = 1 then summ end) summ_m2,
           sum(case when rfpm = '0702' and sex = 0 then summ end) summ_w2,
           sum(case when rfpm = '0703' and sex = 1 then cnt  end) cnt_m3,
           sum(case when rfpm = '0703' and sex = 0 then cnt  end) cnt_w3,
           sum(case when rfpm = '0703' and sex = 1 then summ end) summ_m3,
           sum(case when rfpm = '0703' and sex = 0 then summ end) summ_w3,
           sum(case when rfpm = '0704' and sex = 1 then cnt  end) cnt_m4,
           sum(case when rfpm = '0704' and sex = 0 then cnt  end) cnt_w4,
           sum(case when rfpm = '0704' and sex = 1 then summ end) summ_m4,
           sum(case when rfpm = '0704' and sex = 0 then summ end) summ_w4,
           sum(case when rfpm = '0705' and sex = 1 then cnt  end) cnt_m5,
           sum(case when rfpm = '0705' and sex = 0 then cnt  end) cnt_w5,
           sum(case when rfpm = '0705' and sex = 1 then summ end) summ_m5,
           sum(case when rfpm = '0705' and sex = 0 then summ end) summ_w5
      from agg
     group by reg_id, age
),
ages as (
    select to_char(level, 'fm00') age from dual connect by level <= 11
)
select rr.name                                        reg,
       ga.age                                          age,
       nvl(v.cnt_m1, 0) + nvl(v.cnt_w1, 0)             all_cnt1,
       nvl(v.cnt_m1, 0)                                cnt_m1,
       nvl(v.cnt_w1, 0)                                cnt_w1,
       nvl(v.summ_m1, 0) + nvl(v.summ_w1, 0)           summ_all1,
       nvl(v.summ_m1, 0)                               summ_m1,
       nvl(v.summ_w1, 0)                               summ_w1,
       nvl(v.cnt_m2, 0) + nvl(v.cnt_w2, 0)             all_cnt2,
       nvl(v.cnt_m2, 0)                                cnt_m2,
       nvl(v.cnt_w2, 0)                                cnt_w2,
       nvl(v.summ_m2, 0) + nvl(v.summ_w2, 0)           summ_all2,
       nvl(v.summ_m2, 0)                               summ_m2,
       nvl(v.summ_w2, 0)                               summ_w2,
       nvl(v.cnt_m3, 0) + nvl(v.cnt_w3, 0)             all_cnt3,
       nvl(v.cnt_m3, 0)                                cnt_m3,
       nvl(v.cnt_w3, 0)                                cnt_w3,
       nvl(v.summ_m3, 0) + nvl(v.summ_w3, 0)           summ_all3,
       nvl(v.summ_m3, 0)                               summ_m3,
       nvl(v.summ_w3, 0)                               summ_w3,
       nvl(v.cnt_m4, 0) + nvl(v.cnt_w4, 0)             all_cnt4,
       nvl(v.cnt_m4, 0)                                cnt_m4,
       nvl(v.cnt_w4, 0)                                cnt_w4,
       nvl(v.summ_m4, 0) + nvl(v.summ_w4, 0)           summ_all4,
       nvl(v.summ_m4, 0)                               summ_m4,
       nvl(v.summ_w4, 0)                               summ_w4,
       nvl(v.cnt_m5, 0) + nvl(v.cnt_w5, 0)             all_cnt5,
       nvl(v.cnt_m5, 0)                                cnt_m5,
       nvl(v.cnt_w5, 0)                                cnt_w5,
       nvl(v.summ_m5, 0) + nvl(v.summ_w5, 0)           summ_all5,
       nvl(v.summ_m5, 0)                               summ_m5,
       nvl(v.summ_w5, 0)                               summ_w5,
       nvl(v.cnt_m1,0)+nvl(v.cnt_w1,0)+nvl(v.cnt_m2,0)+nvl(v.cnt_w2,0)
         + nvl(v.cnt_m3,0)+nvl(v.cnt_w3,0)+nvl(v.cnt_m4,0)+nvl(v.cnt_w4,0)
         + nvl(v.cnt_m5,0)+nvl(v.cnt_w5,0)             all_all_cnt,
       nvl(v.cnt_m1,0)+nvl(v.cnt_m2,0)+nvl(v.cnt_m3,0)
         + nvl(v.cnt_m4,0)+nvl(v.cnt_m5,0)             all_cnt_m,
       nvl(v.cnt_w1,0)+nvl(v.cnt_w2,0)+nvl(v.cnt_w3,0)
         + nvl(v.cnt_w4,0)+nvl(v.cnt_w5,0)             all_cnt_w,
       nvl(v.summ_m1,0)+nvl(v.summ_w1,0)+nvl(v.summ_m2,0)+nvl(v.summ_w2,0)
         + nvl(v.summ_m3,0)+nvl(v.summ_w3,0)+nvl(v.summ_m4,0)+nvl(v.summ_w4,0)
         + nvl(v.summ_m5,0)+nvl(v.summ_w5,0)           sum_summ_all,
       nvl(v.summ_m1,0)+nvl(v.summ_m2,0)+nvl(v.summ_m3,0)
         + nvl(v.summ_m4,0)+nvl(v.summ_m5,0)           all_summ_m,
       nvl(v.summ_w1,0)+nvl(v.summ_w2,0)+nvl(v.summ_w3,0)
         + nvl(v.summ_w4,0)+nvl(v.summ_w5,0)           all_summ_w
  from RFRG_REGION rr, ages a, group_age2 ga, pivot v
 where ga.id_age(+) = a.age
   and v.reg_id(+)  = rr.rfrg_id
   and v.age(+)     = a.age
 order by rr.rfrg_id, a.age
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
    footnote=('* - без учета удержаний обязательных пенсионных взносов'),
)
