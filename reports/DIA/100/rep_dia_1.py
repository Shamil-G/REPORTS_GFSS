# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 1 (процедура rep_r_3).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Анализ назначения социальных выплат с начала года по состоянию на месяц:
по регионам число обратившихся за выплатой по беременности и родам (0704)
и по уходу за ребёнком до года (0705) - с начала года и за отчётный месяц.

Источник - макеты дел двух поколений, `union all`: `sipr_payer_maket` +
`sifl_file_maket` (макеты не в состоянии 0) и `sipr_payer` + `sifl_file`
(дела в состоянии 12). Считаются обращения (`sifl_id`) по дате
обращения `date_address`: с начала года (строго позже 1 января, как в
оригинале: `> trunc(pmonth, 'year')`) и в отчётном месяце. Итоговая строка -
`grouping sets (1, (reg, s_region_name(reg)))`: у неё код и название пустые,
как в оригинале.

Отклонение от оригинала в названии: в процедуре год был зашит литералом
(«... на <u>сентябрь 2009 </u> г.»), поэтому отчёт любого года печатал 2009.
Здесь год берётся из параметра, остальное дословно (двойной пробел после
«по состоянию» убран). Месяц строчными (`month_name`), год через пробел.
`<br>`, `<u>` и `<center>` оригинала не переносятся.

Таблицы `sipr_payer_maket`, `sifl_file_maket`, `sipr_payer`, `sifl_file` лежат в
схеме SSWH боевой БД, в тестовой reports_test недоступны: на данных отчёт не
сверен. `s_region_name` - функция схемы SSWH (название области из `rfrg_region`).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '1'
report_name = ('Анализ назначения социальных выплат с начала года по '
               'состоянию на {period} г.')

_period_label = make_period_label({1: '{month} {year}'})

COLUMNS = [
    Col('Код области', 'reg', 'center', 10),
    Col('Наименование области', 'rname', 'text', 36),
    Group('Виды назначений социальных выплат', [
        Group('По беременности', [
            Col('обратившиеся с начала года', 'cnt0704', 'int', 16),
            Col('За отчетный месяц', 'cnt0704_', 'int', 16),
        ]),
        Group('По уходу до 1 года', [
            Col('обратившиеся с начала года', 'cnt0705', 'int', 16),
            Col('За отчетный месяц', 'cnt_0705_', 'int', 16),
        ]),
    ]),
]

# :d_from / :d_to - границы выбранного месяца, :y_from - начало года.
STMT = """
select reg, s_region_name(reg) rname,
       sum(cnt0704) cnt0704, sum(cnt0704_) cnt0704_,
       sum(cnt0705) cnt0705, sum(cnt0705_) cnt_0705_
  from (select /*+ first_rows*/
               substr(fm.rfbn_id, 1, 2) reg,
               count(case when fm.rfpm_id like '0704%' then sm.sifl_id else null end) cnt0704,
               count(case when fm.rfpm_id like '0704%'
                           and sm.date_address >= :d_from
                           and sm.date_address <  :d_to then sm.sifl_id else null end) cnt0704_,
               count(case when fm.rfpm_id like '0705%' then sm.sifl_id else null end) cnt0705,
               count(case when fm.rfpm_id like '0705%'
                           and sm.date_address >= :d_from
                           and sm.date_address <  :d_to then sm.sifl_id else null end) cnt0705_
          from sipr_payer_maket fm, sifl_file_maket sm
         where fm.sipr_id = sm.sipr_id
           and sm.date_address > :y_from
           and fm.state != 0
           and substr(fm.rfpm_id, 1, 4) in ('0704', '0705')
         group by substr(fm.rfbn_id, 1, 2)
        union all
        select /*+ first_rows*/
               substr(fm.rfbn_id, 1, 2) reg,
               count(case when fm.rfpm_id like '0704%' then sm.sifl_id else null end) cnt0704,
               count(case when fm.rfpm_id like '0704%'
                           and sm.date_address >= :d_from
                           and sm.date_address <  :d_to then sm.sifl_id else null end) cnt0704_,
               count(case when fm.rfpm_id like '0705%' then sm.sifl_id else null end) cnt0705,
               count(case when fm.rfpm_id like '0705%'
                           and sm.date_address >= :d_from
                           and sm.date_address <  :d_to then sm.sifl_id else null end) cnt0705_
          from sipr_payer fm, sifl_file sm
         where fm.sipr_id = sm.sipr_id
           and sm.date_address > :y_from
           and fm.state = 12
           and substr(fm.rfpm_id, 1, 4) in ('0704', '0705')
         group by substr(fm.rfbn_id, 1, 2))
 group by grouping sets (1, (reg, s_region_name(reg)))
 order by 1, 2
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
