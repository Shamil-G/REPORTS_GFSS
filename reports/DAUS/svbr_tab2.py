# -*- coding: utf-8 -*-
"""СВБР, таблица 2: получатели в разрезе среднемесячного дохода (доли МЗП).

Перенос REP_STAT_EXTEND.svbr_tab1_2_spool (таблица 2) + svbr_tab1_2.Prn_SP
(таблица 2, pck_utf8.sql, 13366-13417 - расчёт; 13635-13690 - вывод).
Реестр: та же группа 2020, что у svbr_tab1.py (см. там про разделение на
два модуля и про мёртвую "таблицу 3").

Источник и фильтры - как в svbr_tab1.py (sipr_payer, state in (12,13),
LIKE по виду выплаты). Разрез - 12 бакетов дохода относительно МЗП
(sum_avg/mrzp), те же границы, что и в app_47/app_50 (<1,<2,...,<10,=10,
>10), но по другому источнику и другому полю.

Строки - фиксированный справочник s_incominsize (как в app_47/50), а не
данные: если для бакета нет строк, в оригинале всё равно печатается пустая
строка таблицы (Rep.tr вне if tbl2.exists, строки 13663-13672) - здесь
это НЕ ничем не подписанная пустая строка, а обычная строка с названием
бакета и пустыми количеством/суммой (тот же приём, что и в app_47/50) -
более полезно для Excel, чем совсем пустая строка без подписи.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'SVBR.TAB2'
report_name = '{rfpm_id}{period}'

_RFPM_TEXT = {
    '0701': 'Получатели СВ по потери кормильца, за ',
    '0702': 'Получатели СВ по утраты трудоспособности, за ',
    '0703': 'Получатели СВ по потери работы, за ',
    '0704': ('Получатели СВ по потери дохода в связи с беременностью и '
             'родами, с усыновлением (удочерением) новорожденного ребенка '
             '(детей), за '),
    '0705': ('Получатели СВ по потери дохода в связи с уходом за ребенком '
             'по достижении им возраста одного года, за '),
}

_period_label = make_period_label({
    1: '{Month} месяц {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: '9 месяцев {year} года ',
    5: '{year} год ',
})

COLUMNS = [
    Col('СМД', 'smd', 'text', 20),
    Col('Кол-во получатей (чел.)', 'cnt', 'int'),
    Col('Общая сумма СВбр (тг.)', 'sm', 'money', 18),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :rfpm_id - выбранный вид выплаты, сравнение через LIKE (как в
# svbr_tab1.py).
STMT = """
with base as (
    select case
             when sum_avg / mrzp <  1 then 1
             when sum_avg / mrzp <  2 then 2
             when sum_avg / mrzp <  3 then 3
             when sum_avg / mrzp <  4 then 4
             when sum_avg / mrzp <  5 then 5
             when sum_avg / mrzp <  6 then 6
             when sum_avg / mrzp <  7 then 7
             when sum_avg / mrzp <  8 then 8
             when sum_avg / mrzp <  9 then 9
             when sum_avg / mrzp < 10 then 10
             when sum_avg / mrzp = 10 then 11
             when sum_avg / mrzp > 10 then 12
           end coun,
           sum_all
      from sipr_payer
     where rfpm_id like :rfpm_id || '%'
       and state in (12, 13)
       and sum_all > 0
       and risk_date >= :d_from
       and risk_date <  :d_to
),
agg as (
    select coun,
           count(1)     cnt,
           sum(sum_all) sm
      from base
     group by coun
)
select s.is_name  smd,
       a.cnt       cnt,
       a.sm        sm
  from s_incominsize s, agg a
 where a.coun(+) = s.is_id
 order by s.is_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label, sheet_name='Таблица 2',
    text_params={'rfpm_id': _RFPM_TEXT},
)
