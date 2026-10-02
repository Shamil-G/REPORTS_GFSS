# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3009 (процедура REP_MT_ATT_09).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о численности получателей социальных выплат, за которых
производятся перечисления в ЕНПФ (приложение Минтруда №9).

Источник - `pnpd_document` + `pnpt_payment` (внешнее соединение по
`source_id`), число уникальных `pnpt_id` по виду выплаты и КНП. Графа 2 -
все КНП, кроме 010; «из графы 2, участники накопительной пенсионной
системы» - КНП 010 (как в оригинале: `knp <> '010'` и `knp = '010'`).
Список видов выплат - `rfpm_payments`, строки без выплат в отчёт не
попадают (соединение внутреннее, как в оригинале).

Период - один месяц (в оригинале параметр - любая дата месяца,
`trunc(..., 'MM')` и `last_day`). Заголовок «с ... по ...» печатает
первый и последний день месяца. «Приложение №9.» в начале названия не
переносится - так же, как номера приложений в REP_STAT_EXTEND и
REP_MINTRUD: это служебная нумерация бланка.

Нули в оригинале печатаются нулями (`Rep.td` без `nullif`) - blank_zero
не нужен.
"""
from db.connect import LOADER_PROFILE
from util.period import dates_label
from util.xlsx_report import build_report, Col

report_code = '3009'
report_name = ('Сведения о численности получателей социальных выплат, за '
               'которых производятся перечисления в ЕНПФ с {period}')

COLUMNS = [
    Col('Категории получателей', 'name', 'text', 60),
    Col('Количество выплат', 'p_all', 'int', 20),
    Col('Из графы 2, участники накопительной пенсионной системы',
        'p10', 'int', 30),
]

# :d_from / :d_to - границы месяца, :d_to исключительная.
STMT = """
select pm.name,
       sum(case when t.knp <> '010' then t.cnt else 0 end) p_all,
       sum(case when t.knp  = '010' then t.cnt else 0 end) p10
  from (select substr(pd.rfpm_id, 1, 4) rfpm_id,
               count(distinct pp.pnpt_id)              cnt,
               pd.knp
          from pnpd_document pd, pnpt_payment pp
         where pd.pncp_date >= :d_from
           and pd.pncp_date <  :d_to
           and pd.source_id = pp.pnpt_id(+)
           and pd.pnsp_id > 0
           and pd.ridt_id in (4, 6, 7, 8)
           and pd.status in (0, 1, 2, 3, 5, 7)
         group by substr(pd.rfpm_id, 1, 4), pd.knp) t,
       rfpm_payments pm
 where pm.rfpm_id = t.rfpm_id
 group by pm.rfpm_id, pm.name
 order by pm.rfpm_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=dates_label,
)
