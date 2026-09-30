# -*- coding: utf-8 -*-
"""Приложения 42-46. Получатели и суммы СВ (любой из 5 видов) в разрезе
региона, возраста и стажа участия в СОСС.

Перенос REP_STAT_EXTEND.app_42_46_spool + Rep_app_42_46 (pck_utf8.sql,
6327-6716). Реестр: группа 1420, вызов app_42_46_1m('m') и аналоги; третий
параметр формы (Rep.ParAsChar(3)) выбирает вид выплаты 0701-0705 - как и
в app_50.py, это обычный параметр формы `rfpm_id` (LIST_RFPM), а не 5
модулей: SQL/колонки одинаковы, меняются только фильтр и слова в названии
(комментарий самого исходника прямо перечисляет соответствие: "приложение
42 - 0701, приложение 43 - 0702, приложение 44 - 0703, приложение 45 -
0704, приложение 46 - 0705", строка 6477).

Стаж участия (`staj`) - decode(ksu, 0.1,1, 0.7,2, 0.75,3, 0.85,4, 0.9,5,
0.95,6, 7) - 7 групп, 7-я - "свыше 60 месяцев" (catch-all, а не отдельное
значение ksu). ksu берётся с фолбэком на справочник sipr_ksu, если в самой
строке назначения он пуст (nvl(s.ksu, t.ksu), строка 6398). Возраст - те
же 11 корзин width_bucket(...,20,65,9), что и в app_34/36/42, считается от
risk_date (не от даты последней выплаты).

Зануление - обычное (blank_zero=True), кроме колонки "Итого": она,
как и в app_34/36/38 и других, всегда показывает число (в т.ч. 0), потому
что p_all_a/p_all_b по умолчанию 0 и наращиваются только при наличии
данных (строки 6531-6602, накопление вне if-exists), а не читаются из
tbl напрямую.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.42-46'
# cSPTitle дословно (строка 6481, двойной пробел перед "на случай" - как
# в исходнике) + cSPTitleSV (зависит от вида выплаты, строки 6592-6606,
# уже включает завершающее ", за ").
report_name = ('Сведения по количеству получателей и суммам социальных '
               'выплат  на случай {rfpm_id}{period}')

_RFPM_TEXT = {
    '0701': 'потери кормильца в разрезе регионов и стажа участия, за ',
    '0702': 'утраты трудоспособности в разрезе регионов и стажа участия, за ',
    '0703': 'потери работы в разрезе регионов и стажа участия, за ',
    '0704': ('потери дохода в связи с беременностью и родами, с '
             'усыновлением (удочерением) новорожденного ребенка (детей) '
             'в разрезе регионов и стажа участия, за '),
    '0705': ('потери дохода в связи с уходом за ребенком по достижении '
             'им возраста одного года в разрезе регионов и стажа '
             'участия, за '),
}

# Begin блок Rep_app_42_46 (строки 6688-6700) - без ", за"-приставки, тип 1
# с добавленным пробелом между месяцем и годом (сознательное отступление,
# как и в остальных отчётах раздела).
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

_STAJ = [
    (1, 'менее 6 месяцев'),
    (2, 'от 6 до 12 месяцев'),
    (3, 'от 12 до 24 месяцев'),
    (4, 'от 24 до 36 месяцев'),
    (5, 'от 36 до 48 месяцев'),
    (6, 'от 48 до 60 месяцев'),
    (7, 'свыше 60 месяцев'),
]

COLUMNS = [
    Col('Наименование', 'reg', 'text', 30),
    Col('Возраст', 'age', 'text', 14),
    *[Group(title, [
        Col('Количество(человек)', f'cnt{n}', 'int'),
        Col('Сумма(тенге)', f'summ{n}', 'money', 16),
    ]) for n, title in _STAJ],
    Group('Итого', [
        Col('Количество(человек)', 'cnt8', 'int'),
        Col('Сумма(тенге)', 'summ8', 'money', 16),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :rfpm_id - выбранный вид выплаты (LIST_RFPM).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           decode(nvl(s.ksu, t.ksu), 0.1, 1, 0.7, 2, 0.75, 3, 0.85, 4,
                  0.9, 5, 0.95, 6, 7)                            staj,
           to_char(width_bucket(
               trunc(months_between(s.risk_date, pr.birthdate) / 12),
               20, 65, 9) + 1, 'fm00')                            age,
           s.sipr_id,
           s.sum_all
      from sipr_maket_first_approve_2 s, sipr_ksu t, person pr
     where s.sipr_id = t.sipr_id(+)
       and pr.sicid  = s.sicp_id
       and substr(s.rfpm_id, 1, 4) = :rfpm_id
       and s.sum_all > 0
       and s.date_approve >= :d_from
       and s.date_approve <  :d_to
),
agg as (
    select reg_id, age, staj,
           count(1)     cnt,
           sum(sum_all) summ
      from base
     group by reg_id, age, staj
),
pivot as (
    select reg_id, age,
           sum(case when staj = 1 then cnt  end) cnt1,
           sum(case when staj = 1 then summ end) summ1,
           sum(case when staj = 2 then cnt  end) cnt2,
           sum(case when staj = 2 then summ end) summ2,
           sum(case when staj = 3 then cnt  end) cnt3,
           sum(case when staj = 3 then summ end) summ3,
           sum(case when staj = 4 then cnt  end) cnt4,
           sum(case when staj = 4 then summ end) summ4,
           sum(case when staj = 5 then cnt  end) cnt5,
           sum(case when staj = 5 then summ end) summ5,
           sum(case when staj = 6 then cnt  end) cnt6,
           sum(case when staj = 6 then summ end) summ6,
           sum(case when staj = 7 then cnt  end) cnt7,
           sum(case when staj = 7 then summ end) summ7
      from agg
     group by reg_id, age
),
ages as (
    select to_char(level, 'fm00') age from dual connect by level <= 11
)
select rr.name  reg,
       ga.age   age,
       v.cnt1, v.summ1, v.cnt2, v.summ2, v.cnt3, v.summ3, v.cnt4, v.summ4,
       v.cnt5, v.summ5, v.cnt6, v.summ6, v.cnt7, v.summ7,
       nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) + nvl(v.cnt4, 0)
         + nvl(v.cnt5, 0) + nvl(v.cnt6, 0) + nvl(v.cnt7, 0)          cnt8,
       nvl(v.summ1, 0) + nvl(v.summ2, 0) + nvl(v.summ3, 0) + nvl(v.summ4, 0)
         + nvl(v.summ5, 0) + nvl(v.summ6, 0) + nvl(v.summ7, 0)       summ8
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
    text_params={'rfpm_id': _RFPM_TEXT},
)
