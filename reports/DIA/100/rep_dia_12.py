# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 12 (процедура rep_r_12).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения об участниках ССС, обратившихся за социальной выплатой по случаю
потери работы (0703) за период: по областям - сколько всего обратилось и
из них подготовлено, утверждено, поставлено на выплату.

Источник - макеты двух поколений, `union all`: `sipr_payer_maket` +
`sifl_file_maket` (подготовлено - состояния 1, 2, 6, 7, 9, 10; утверждено -
состояние 3) и `sipr_payer` + `sifl_file` (поставлено на выплату - состояние
12); период по `date_address`. Число - `count(unique sifl_id)`. «Всего
обратилось» - сумма трёх колонок (в оригинале `cnt1 + cnt2 + cnt3`).
Итоговая строка - «Всего»; область - функция схемы SSWH `s_region_name`.

Название дословно; лишняя кавычка после «г.» убрана, добавлена запятая после
«ССС», двойной пробел исправлен, `<br>` убраны.
Колонки - из `SetPageHead`.

Таблицы `sipr_payer_maket`, `sifl_file_maket`, `sipr_payer`, `sifl_file` лежат в
схеме SSWH боевой БД, в тестовой reports_test недоступны: на данных отчёт не
сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '12'
report_name = ('Сведения об участниках ССС, обратившихся за социальной '
               'выплатой по случаю потери работы за период с {date_from} '
               'года по {date_to} года')

COLUMNS = [
    Col('Наименование областей', 'reg_n', 'text', 36),
    Col('Всего обратилось за социальной выплатой', 'cnt_all', 'int', 18),
    Group('из них', [
        Col('Подготовлено', 'cnt1', 'int', 16),
        Col('Утверждено', 'cnt2', 'int', 16),
        Col('Поставлено на выплату', 'cnt3', 'int', 18),
    ]),
]

# :d_from / :d_to - период из формы по date_address, :d_to исключительная.
STMT = """
select case when reg_n is null then 'Всего' else reg_n end reg_n,
       cnt1 + cnt2 + cnt3 cnt_all, cnt1, cnt2, cnt3
  from (select s_region_name(reg) reg_n,
               sum(cnt) cnt1, sum(utv) cnt2, sum(vyp) cnt3
          from (select substr(fm.rfbn_id, 1, 2) reg,
                       count(unique (case when fm.state in (1, 2, 6, 7, 9, 10)
                                          then sm.sifl_id else null end)) cnt,
                       count(unique (case when fm.state in (3)
                                          then sm.sifl_id else null end)) utv,
                       0 vyp
                  from sipr_payer_maket fm, sifl_file_maket sm
                 where fm.sipr_id = sm.sipr_id
                   and fm.rfpm_id like '0703%'
                   and sm.date_address >= :d_from
                   and sm.date_address <  :d_to
                 group by substr(fm.rfbn_id, 1, 2)
                union all
                select substr(fm.rfbn_id, 1, 2) reg, 0 cnt, 0 utv,
                       count(unique (case when fm.state in (12)
                                          then sm.sifl_id else null end)) vyp
                  from sipr_payer fm, sifl_file sm
                 where fm.sipr_id = sm.sipr_id
                   and fm.rfpm_id like '0703%'
                   and sm.date_address >= :d_from
                   and sm.date_address <  :d_to
                 group by substr(fm.rfbn_id, 1, 2))
         group by grouping sets (1, (s_region_name(reg))))
 order by reg_n
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
