# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 5 (процедура rep_r_5).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Анализ поступлений социальных отчислений и социальных выплат из Фонда за год:
по регионам и месяцам - поступления и выплаты, и «Всего» за год.

Источник - справочник фактических показателей `rfrr_reference` (по годам
и месяцам): поступления - типы 8 и 9 (`rf_type`), выплаты - типы 11-15,
значение - `fact_value`. Месяц - `in_month` ('01'...'12'), строки без месяца
не берутся. Итоговая строка - `grouping sets (1, (reg, s_region_name(reg)))`
с пустыми кодом и названием. «Всего» по строке - сумма двенадцати месяцев
(в оригинале считалась в процедуре, здесь - в запросе).

Параметр - год (в оригинале число `pyear`). Название дословно: «за <год> г.»,
двойной пробел после «отчислений» убран.

`rfrr_reference` и `s_region_name` в тестовой reports_test недоступны: на
данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '5'
report_name = ('Анализ поступлений социальных отчислений и социальных '
               'выплат из Фонда за {rep_year} г.')

_MONTHS = ('Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль',
           'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь')

COLUMNS = (
    [Col('Код области', 'reg', 'center', 10),
     Col('Наименование области', 'name', 'text', 36)]
    + [Group(m, [Col('Поступления', f'sum{n:02d}', 'money', 18),
                 Col('Выплаты', f'sum{n:02d}2', 'money', 18)])
       for n, m in enumerate(_MONTHS, start=1)]
    + [Group('Всего', [Col('Поступления', 'sum_in', 'money', 20),
                       Col('Выплаты', 'sum_out', 'money', 20)])]
)

_MONTH_COLS = ',\n'.join(
    f"       sum(case when r.rf_type in (8, 9) and in_month = '{n:02d}' "
    f"then fact_value else 0 end) sum{n:02d},\n"
    f"       sum(case when r.rf_type in (11, 12, 13, 14, 15) and in_month = '{n:02d}' "
    f"then fact_value else 0 end) sum{n:02d}2" for n in range(1, 13))

_LIST = ',\n'.join(f'       sum{n:02d}, sum{n:02d}2' for n in range(1, 13))
_SUM_IN = ' + '.join(f'sum{n:02d}' for n in range(1, 13))
_SUM_OUT = ' + '.join(f'sum{n:02d}2' for n in range(1, 13))

# :rep_year - год из формы.
STMT = f"""
select reg, name,
{_LIST},
       {_SUM_IN} sum_in,
       {_SUM_OUT} sum_out
  from (select reg, s_region_name(reg) name,
{_MONTH_COLS}
          from rfrr_reference r
         where r.in_year = to_number(:rep_year)
           and r.rf_type in (11, 12, 13, 14, 15, 8, 9)
           and in_month is not null
         group by grouping sets (1, (reg, s_region_name(reg))))
 order by reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, title_params=('rep_year',),
)
