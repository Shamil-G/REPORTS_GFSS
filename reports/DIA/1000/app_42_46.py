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
значение ksu). По замечанию Заказчика (07.10.2026) "свыше 60 месяцев"
разбита по годам стажа: коэффициенты 1,0 ... 1,28 с шагом 0,02 - группы
"от 60 до 72" ... "от 228 до 240 месяцев", последняя "более 240 месяцев"
(1,3) осталась catch-all, как 7-я в оригинале: в неё же идут значения ksu,
не являющиеся коэффициентом стажа (у 0704 там число дней, у 0705 пусто). ksu берётся с фолбэком на справочник sipr_ksu, если в самой
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

# (ksu, заголовок группы стажа); у последней ksu нет - она catch-all
_STAJ = [
    ('0.1', 'менее 6 месяцев'),
    ('0.7', 'от 6 до 12 месяцев'),
    ('0.75', 'от 12 до 24 месяцев'),
    ('0.85', 'от 24 до 36 месяцев'),
    ('0.9', 'от 36 до 48 месяцев'),
    ('0.95', 'от 48 до 60 месяцев'),
    *[(f'{1 + 0.02 * i:.2f}', f'от {60 + 12 * i} до {72 + 12 * i} месяцев')
      for i in range(15)],
    (None, 'более 240 месяцев'),
]
_N = len(_STAJ)
_TOTAL = _N + 1             # номер пары колонок "Итого"

COLUMNS = [
    Col('Наименование', 'reg', 'text', 30),
    Col('Возраст', 'age', 'text', 14),
    *[Group(title, [
        Col('Количество(человек)', f'cnt{n}', 'int'),
        Col('Сумма(тенге)', f'summ{n}', 'money', 16),
    ]) for n, (_, title) in enumerate(_STAJ, start=1)],
    Group('Итого', [
        Col('Количество(человек)', f'cnt{_TOTAL}', 'int'),
        Col('Сумма(тенге)', f'summ{_TOTAL}', 'money', 16),
    ]),
]

_DECODE = ', '.join(f'{k}, {n}' for n, (k, _) in enumerate(_STAJ, start=1) if k)
_PIVOT = ',\n'.join(f'           sum(case when staj = {n} then cnt  end) cnt{n},\n'
                     f'           sum(case when staj = {n} then summ end) summ{n}'
                     for n in range(1, _N + 1))
_COLS = ', '.join(f'v.cnt{n}, v.summ{n}' for n in range(1, _N + 1))
_CNT_ALL = ' + '.join(f'nvl(v.cnt{n}, 0)' for n in range(1, _N + 1))
_SUMM_ALL = ' + '.join(f'nvl(v.summ{n}, 0)' for n in range(1, _N + 1))

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :rfpm_id - выбранный вид выплаты (LIST_RFPM).
STMT = f"""
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           decode(nvl(s.ksu, t.ksu), {_DECODE}, {_N})             staj,
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
{_PIVOT}
      from agg
     group by reg_id, age
),
ages as (
    select to_char(level, 'fm00') age from dual connect by level <= 11
)
select rr.name  reg,
       ga.age   age,
       {_COLS},
       {_CNT_ALL} cnt{_TOTAL},
       {_SUMM_ALL} summ{_TOTAL}
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
