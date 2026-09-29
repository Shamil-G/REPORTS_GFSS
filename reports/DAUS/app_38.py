# -*- coding: utf-8 -*-
"""Приложение 38. Коэффициент замещения дохода при утрате трудоспособности
(СВ 0702), в разрезе регионов и степени утраты трудоспособности.

Перенос REP_STAT_EXTEND.app_38_spool + Rep_app_38 (pck_utf8.sql, 4607-5145).
Реестр: группа 1380, вызов app_38_1m('m') и аналоги по типам периода 1-5.

app_38 зарегистрирован в реестре в ДВУХ версиях одновременно: этот модуль
(группа 1380 - без учёта ГСП) и app_38_v2.py (группа 2280 - с выбором,
учитывать ли государственную базовую пенсию). Это не смена версии, а два
живых отчёта с разной формулой коэффициента - см. app_38_v2.py, там разбор
отличия подробно.

Степень утраты трудоспособности - последний символ rfpm_id (substr(...,-1)):
1 = "от 80% до 100%", 2 = "от 60% до 80%", 3 = "от 30% до 60%" (соответствие
подтверждено по аналогичной группировке в другом месте пакета, строки
12201-12203, а не по мнемонике самого кода).

СОЗНАТЕЛЬНОЕ ОТСТУПЛЕНИЕ (согласовано по прецеденту app_32, см.
migration-plan.md): столбцы "Средний размер СВ", "Среднемес. доход" и
"К замещения" в оригинале для периодов длиннее месяца считаются неверно -
Rep_app_38 копит эти отношения из EAV, где они уже посчитаны ПОМЕСЯЧНО
(app_38_spool строки 4638-4640: avg_size/avg_smd/kof - частные за месяц), а
печать строки региона (PrnOneGoup, строки 4864-4868) складывает эти месячные
частные напрямую, без пересчёта - для квартала/полугодия/9 месяцев/года это
сумма нескольких помесячных отношений, а не отношение за весь период. Только
строка "По республике" в подвале пересчитывает правильно, через сумму сумм
(строки 4894-4896). Здесь эта же правильная формула (отношение сумм, а не
сумма отношений) применяется к КАЖДОЙ строке региона, не только к итогу: для
месячного периода результат идентичен оригиналу, для остальных периодов -
отличается и это ожидаемо при сверке.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.38'
# cSPTitle дословно (строка 4766-4767).
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай утраты трудоспособности в разрезе '
               'регионов, за {period}')

# Подпись периода (Begin блок Rep_app_38, строки 5080-5092) - в этом
# семействе, в отличие от app_34_35/36_37, у типов 2/3/5 НЕТ ведущего
# пробела (p_PH_per присваивается напрямую, не конкатенируется с уже
# существующим значением), а у типа 4 пробел одинарный, не двойной.
# Пробел между месяцем и годом в типе 1 - как и в app_34/35/36/37,
# сознательно добавлен для читаемости (в оригинале слитно).
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

_STEPS = [
    ('1', 'степень утраты общей трудоспособности от 80% до 100%'),
    ('2', 'степень утраты общей трудоспособности от 60% до 80%'),
    ('3', 'степень утраты общей трудоспособности от 30% до 60%'),
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


# Первая колонка называется дословно "По утрате трудоспособности" - так в
# исходнике назван не заголовок отчёта, а первый лист заголовка таблицы
# (p_PageHead, строка 4945), хотя по факту в ней название региона. Число
# колонок сходится с AddCol только при этом прочтении (1 + 4*5 = 21).
COLUMNS = [
    Col('По утрате трудоспособности', 'reg', 'text', 30),
    *[_metric_group(suffix, title) for suffix, title in _STEPS],
    _metric_group('_t', 'Всего'),
]

FOOTNOTE = (
    '* количество - количество человек, которым СВ утверждена '
    'Департаментами по контролю и социальной защите в отчетном периоде\n'
    '** сумма назначенных размеров СВ за весь отчетный период\n'
    '*** средний размер назначенных СВ - средневзвешенный (определяется '
    'как частное суммы всех назначенных СВ за отчетный период на '
    'количество получателей в отчетном периоде)\n'
    '**** коэффициент (К) замещения - среднее математическое '
    'коэффициентов замещения каждого получателя\n'
    'коэффициент (K) = sum(расчет.)/sum(доход)'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# base - строки sipr_maket_first_approve_2 за период с кодом выплаты 0702
# (потеря трудоспособности), step_utr - степень утраты (последний символ
# rfpm_id, строка 4652).
#
# agg/pivot - per-регион суммы по 3 степеням: cnt (count distinct sipr_id,
# как count(unique...) в оригинале), sm_all (сумма назначенных выплат),
# sum_avg (сумма среднемесячного дохода - в EAV не хранилась отдельно,
# только готовое отношение avg_smd, поэтому в оригинале сумма отношений;
# здесь считается из первоисточника напрямую).
#
# avg_size/avg_smd/kof на каждую степень и на "Всего" вычисляются в самом
# select (не через avg_of) - so per-row значения в отчёте всегда отношение
# сумм за весь период. avg_of на Col нужен только для правильного итога
# framework'а по строке "Итого" (сумма по всем регионам).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           substr(s.rfpm_id, -1)   step_utr,
           s.sipr_id,
           s.sum_all,
           s.sum_avg
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0702'
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
           sum(case when step_utr = '3' then sm_avg  end) sm_avg3
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
       nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0)           cnt_t,
       nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0)  sm_all_t,
       nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0)  sum_avg_t,
       case when nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) > 0
            then (nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0))
               / (nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0))
            else 0 end                                           avg_size_t,
       case when nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) > 0
            then (nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0))
               / (nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0))
            else 0 end                                           avg_smd_t,
       case when nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0) > 0
            then (nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0))
               / (nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0)) * 100
            else 0 end                                           kof_t,
       (nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0)) * 100
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
