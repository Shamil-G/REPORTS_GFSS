# -*- coding: utf-8 -*-
"""Приложение 39. Коэффициент замещения дохода при потере кормильца
(СВ 0701), в разрезе регионов и количества иждивенцев.

Перенос REP_STAT_EXTEND.app_39_spool + Rep_app_39 (pck_utf8.sql, 5149-5700).
Реестр: группа 1390, вызов app_39_1m('m') и аналоги по типам периода 1-5.

Устройство и формула коэффициента - как у app_38.py (см. там подробный
разбор источника, почему это "отношение сумм", а не "среднее отношений", и
про сознательное отступление в подсчёте построчных avg/kof). Здесь то же
самое, только:
  - вид выплаты 0701 (потеря кормильца), а не 0702;
  - фильтр `sum_all > 0` в источнике (строка 5213, "чтобы избавиться от
    отрицательных сумм") - сохранён;
  - группировка не по степени утраты трудоспособности, а по количеству
    иждивенцев: substr(rfpm_id,-1) даёт 1, 2, 3 или 4 (строка 692-723 в
    другой процедуре подтверждает, что "4" в справочнике выплат уже
    означает "4 и более", доп. группировка по >=4 не нужна) - четыре
    группы вместо трёх у app_38.

Как и app_38, зарегистрирован в реестре в двух версиях одновременно: этот
модуль (группа 1390 - без ГСП) и app_39_v2.py (группа 2290 - с выбором
учёта ГСП). См. app_39_v2.py про формулу коэффициента там же и про то, чем
v2 этого семейства отличается от app_38_v2.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.39'
# cSPTitle дословно (строка 5310).
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай потери кормильца в разрезе регионов, за '
               '{period}')

# Begin блок Rep_app_39 (строки 5678-5692) - текстуально совпадает с
# app_38.py (тип 4 здесь конкатенируется с rep_steep, но при вызове за
# 9 месяцев rep_steep всегда null, поэтому итог тот же - один пробел).
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

_GROUPS = [
    ('1', 'c 1-иждевенцем'),
    ('2', 'c 2-иждевенцами'),
    ('3', 'c 3-иждевенцами'),
    ('4', 'c 4-иждевенцами и более'),
]


def _metric_group(suffix, title):
    return Group(title, [
        Col('Количество *(человек)', f'cnt{suffix}', 'int'),
        Col('Сумма назначенных размеров соц. выплат,**(тенге)',
            f'sm_all{suffix}', 'money', 18),
        Col('Средний размер назначенных соц. выплат ***(тенге)',
            f'avg_size{suffix}', 'avg', 18, avg_of=(f'sm_all{suffix}', f'cnt{suffix}')),
        Col('Среднемесяч. доход, принятый для исчисления выплат (тенге)',
            f'avg_smd{suffix}', 'avg', 20, avg_of=(f'sum_avg{suffix}', f'cnt{suffix}')),
        Col('К замещения ****, %',
            f'kof{suffix}', 'avg', 14, avg_of=(f'kof_num{suffix}', f'sum_avg{suffix}')),
    ])


COLUMNS = [
    Col('По утере кормильца', 'reg', 'text', 30),
    *[_metric_group(suffix, title) for suffix, title in _GROUPS],
    _metric_group('_t', 'Всего'),
]

# Дословно (строки 5695-5699); формулировка "**** ..." здесь чуть другая,
# чем в app_38.py ("среднее математическое ЗНАЧЕНИЕ коэффициентов
# замещения" - лишнее слово в оригинале и Латинская "K" вместо кириллической
# "К" в последней строке) - копируется как есть.
FOOTNOTE = (
    '* количество - количество человек, которым СВ утверждена '
    'Департаментами по контролю и социальной защите в отчетном периоде\n'
    '** сумма назначенных размеров СВ за весь отчетный период\n'
    '*** средний размер назначенных СВ - средневзвешенный (определяется '
    'как частное суммы всех назначенных СВ за отчетный период на '
    'количество получателей в отчетном периоде)\n'
    '**** коэффициент (K) замещения - среднее математическое значение '
    'коэффициентов замещения каждого получателя\n'
    'коэффициент (K) = sum(расчет.)/sum(доход)'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# См. подробный разбор в app_38.py - здесь то же самое плюс фильтр
# sum_all > 0 и 4 группы вместо 3.
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           substr(s.rfpm_id, -1)   step_utr,
           s.sipr_id,
           s.sum_all,
           s.sum_avg
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0701'
       and s.sum_all > 0
       and trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
),
agg as (
    select reg_id, step_utr,
           count(distinct sipr_id) cnt,
           sum(sum_all)            sm_all,
           sum(sum_avg)            sm_avg
      from base
     group by reg_id, step_utr
),
pivot as (
    select reg_id,
           sum(case when step_utr = '1' then cnt    end) cnt1,
           sum(case when step_utr = '1' then sm_all  end) sm_all1,
           sum(case when step_utr = '1' then sm_avg  end) sm_avg1,
           sum(case when step_utr = '2' then cnt    end) cnt2,
           sum(case when step_utr = '2' then sm_all  end) sm_all2,
           sum(case when step_utr = '2' then sm_avg  end) sm_avg2,
           sum(case when step_utr = '3' then cnt    end) cnt3,
           sum(case when step_utr = '3' then sm_all  end) sm_all3,
           sum(case when step_utr = '3' then sm_avg  end) sm_avg3,
           sum(case when step_utr = '4' then cnt    end) cnt4,
           sum(case when step_utr = '4' then sm_all  end) sm_all4,
           sum(case when step_utr = '4' then sm_avg  end) sm_avg4
      from agg
     group by reg_id
)
select rr.name                                                  reg,
       nvl(v.cnt1, 0)                                            cnt1,
       nvl(v.sm_all1, 0)                                         sm_all1,
       nvl(v.sm_avg1, 0)                                         sum_avg1,
       case when nvl(v.cnt1, 0) > 0
            then v.sm_all1 / v.cnt1 else 0 end                   avg_size1,
       case when nvl(v.cnt1, 0) > 0
            then v.sm_avg1 / v.cnt1 else 0 end                   avg_smd1,
       case when nvl(v.sm_avg1, 0) > 0
            then (v.sm_all1 / v.sm_avg1) * 100 else 0 end        kof1,
       nvl(v.sm_all1, 0) * 100                                   kof_num1,
       nvl(v.cnt2, 0)                                            cnt2,
       nvl(v.sm_all2, 0)                                         sm_all2,
       nvl(v.sm_avg2, 0)                                         sum_avg2,
       case when nvl(v.cnt2, 0) > 0
            then v.sm_all2 / v.cnt2 else 0 end                   avg_size2,
       case when nvl(v.cnt2, 0) > 0
            then v.sm_avg2 / v.cnt2 else 0 end                   avg_smd2,
       case when nvl(v.sm_avg2, 0) > 0
            then (v.sm_all2 / v.sm_avg2) * 100 else 0 end        kof2,
       nvl(v.sm_all2, 0) * 100                                   kof_num2,
       nvl(v.cnt3, 0)                                            cnt3,
       nvl(v.sm_all3, 0)                                         sm_all3,
       nvl(v.sm_avg3, 0)                                         sum_avg3,
       case when nvl(v.cnt3, 0) > 0
            then v.sm_all3 / v.cnt3 else 0 end                   avg_size3,
       case when nvl(v.cnt3, 0) > 0
            then v.sm_avg3 / v.cnt3 else 0 end                   avg_smd3,
       case when nvl(v.sm_avg3, 0) > 0
            then (v.sm_all3 / v.sm_avg3) * 100 else 0 end        kof3,
       nvl(v.sm_all3, 0) * 100                                   kof_num3,
       nvl(v.cnt4, 0)                                            cnt4,
       nvl(v.sm_all4, 0)                                         sm_all4,
       nvl(v.sm_avg4, 0)                                         sum_avg4,
       case when nvl(v.cnt4, 0) > 0
            then v.sm_all4 / v.cnt4 else 0 end                   avg_size4,
       case when nvl(v.cnt4, 0) > 0
            then v.sm_avg4 / v.cnt4 else 0 end                   avg_smd4,
       case when nvl(v.sm_avg4, 0) > 0
            then (v.sm_all4 / v.sm_avg4) * 100 else 0 end        kof4,
       nvl(v.sm_all4, 0) * 100                                   kof_num4,
       nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) + nvl(v.cnt4, 0)
                                                                  cnt_t,
       nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0)
         + nvl(v.sm_all4, 0)                                     sm_all_t,
       nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0)
         + nvl(v.sm_avg4, 0)                                     sum_avg_t,
       case when nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0) > 0
            then (nvl(v.sm_all1,0)+nvl(v.sm_all2,0)+nvl(v.sm_all3,0)+nvl(v.sm_all4,0))
               / (nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0))
            else 0 end                                           avg_size_t,
       case when nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0) > 0
            then (nvl(v.sm_avg1,0)+nvl(v.sm_avg2,0)+nvl(v.sm_avg3,0)+nvl(v.sm_avg4,0))
               / (nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0))
            else 0 end                                           avg_smd_t,
       case when nvl(v.sm_avg1,0)+nvl(v.sm_avg2,0)+nvl(v.sm_avg3,0)+nvl(v.sm_avg4,0) > 0
            then (nvl(v.sm_all1,0)+nvl(v.sm_all2,0)+nvl(v.sm_all3,0)+nvl(v.sm_all4,0))
               / (nvl(v.sm_avg1,0)+nvl(v.sm_avg2,0)+nvl(v.sm_avg3,0)+nvl(v.sm_avg4,0)) * 100
            else 0 end                                           kof_t,
       (nvl(v.sm_all1,0)+nvl(v.sm_all2,0)+nvl(v.sm_all3,0)+nvl(v.sm_all4,0)) * 100
                                                                  kof_num_t
  from RFRG_REGION rr, pivot v
 where v.reg_id(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label, footnote=FOOTNOTE,
)
