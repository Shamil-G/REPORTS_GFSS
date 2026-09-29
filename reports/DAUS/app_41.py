# -*- coding: utf-8 -*-
"""Приложение 41. Коэффициент замещения дохода при уходе за ребёнком по
достижении им возраста одного года (СВ 0705), в разрезе регионов.

Перенос REP_STAT_EXTEND.app_40_41_spool + Rep_app_40_41(iTypePay='0705')
(pck_utf8.sql, 5746-6272). Реестр: та же группа 1400, что у app_40.py -
третий параметр формы выбирает 0703/0705 (см. app_40.py про разделение на
два модуля).

В отличие от app_40.py, здесь нет измерения "стаж" (PrnOneGoup для '0705'
не читает справочник moon и не выводит колонку стажа, строки 6018-6038) и
только ОДИН уровень итога - "итого:" по всем регионам (строки 6221-6227,
нет отдельной строки "Всего по республике"). Это укладывается в обычный
totals=True фреймворка: единственный groupby - по региону, итог получается
из тех же sum(cnt)/sum(sm_all)/... через avg_of, без ручного построения
дополнительных строк, как в app_40.py.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'APP.41'
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай потери дохода в связи с уходом за '
               'ребенком по достижении им возраста одного года в разрезе '
               'регионов, за {period}')

_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

# p_PageHead (строки 6129-6135): "По уходу до года" - заголовок колонки
# региона, не первой AddCol (тот же приём, что в app_40.py/app_38.py).
COLUMNS = [
    Col('По уходу до года', 'reg', 'text', 30),
    Col('Кол-во, * (человек)', 'cnt', 'int'),
    Col('Сумма назначенных размеров социальных выплат, (тенге)**',
        'sm_all', 'money', 18),
    Col('Средний размер назначенных соцвыплат, (тенге) *** гр.3/гр2',
        'avg_size', 'avg', 18, avg_of=('sm_all', 'cnt')),
    Col('Среднемес. доход, принятый для исчисления выплат (тенге)',
        'avg_smd', 'avg', 20, avg_of=('sum_avg', 'cnt')),
    Col('К замещения (%)', 'kof', 'avg', 14, avg_of=('kof_num', 'cnt')),
]

FOOTNOTE = (
    '* количество - количество человек, которым СВ утверждена '
    'Департаментами по контролю и социальной защите в отчетном периоде\n'
    '**сумма назначенных размеров соцвыплат (СВ)за весь отчетный период\n'
    '***средний размер назначенных соцвыплат - средневзвешенный '
    '(определяется как частное суммы всех назначенных соцвыплат за '
    'отчетный период на количество получателей в отчетном периоде)\n'
    '**** коэффициент (K) замещения - среднее математическое значение '
    'коэффициентов замещения каждого получателя'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# Источник и формулы - как в app_40.py, без измерения "стаж" и без фильтра
# sum_all > 0 (в оригинале он есть только в ветке '0703', строка 5822).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           s.sipr_id,
           s.sum_all,
           s.sum_avg,
           s.sum_all / nullif(s.sum_avg, 0) kof_per
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
),
agg as (
    select reg_id,
           count(distinct sipr_id) cnt,
           sum(sum_all)            sm_all,
           sum(sum_avg)            sm_avg,
           sum(kof_per)            sm_kof
      from base
     group by reg_id
)
select rr.name                                        reg,
       nvl(a.cnt, 0)                                    cnt,
       nvl(a.sm_all, 0)                                 sm_all,
       case when nvl(a.cnt, 0) > 0
            then a.sm_all / a.cnt else 0 end             avg_size,
       case when nvl(a.cnt, 0) > 0
            then a.sm_avg / a.cnt else 0 end             avg_smd,
       case when nvl(a.cnt, 0) > 0
            then (a.sm_kof / a.cnt) * 100 else 0 end     kof,
       nvl(a.sm_avg, 0)                                  sum_avg,
       nvl(a.sm_kof, 0) * 100                            kof_num
  from RFRG_REGION rr, agg a
 where a.reg_id(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label, footnote=FOOTNOTE,
)
