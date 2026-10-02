# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3316 (процедура REP_R_3316).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Назначение СВпр (социальная выплата по потере работы): обращения и принятые
решения о назначении по регионам и источникам подачи.

Две части, объединённые `union` (признак `prt`):
  1 - обращения: `ss_z_doc` + `ss_m_sol`, новые заявления (`id_tip = 'NEW'`,
      `id_osn = 103`) с датой ввода `d_inp` в периоде, у которых есть
      действующая запись `ss_m_sol_st` со статусом 4, 16 или 29 (запись не
      отменена и не является откатом);
  2 - решения о назначении: `sipr_maket_first_approve_2` по виду 0703 с датой
      утверждения макета `date_approve` в периоде.
Источник подачи (`id_sour`): CON - ЦОН, GCV - Дирекция ГК, PEP - ПЭП,
ZSP - Центр занятости. Регион - первые два знака отделения + '00'.

`d_inp` и `id_osn` в оригинале стоят без алиаса - это колонки `ss_z_doc`
(`ss_m_sol` их не содержит), здесь они так же. `trunc(date_approve) between`
заменено на полуоткрытый интервал (правило проекта).

Название: «с» перед датой кириллическая (в оригинале латинская «c»). В `sum(case ... end)`
для общих колонок нет `else 0` (в оригинале): регион без обращений даёт пустую
ячейку, итог при этом суммирует как ноль.

Таблицы `ss_*` и `sipr_maket_first_approve_2` лежат в схеме SSWH боевой БД,
в тестовой reports_test их нет: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3316'
report_name = 'Назначение СВпр с {period} года'


def _sources(prefix):
    return Group('В том числе', [
        Col('ЦОН', f'{prefix}c', 'int', 10),
        Col('Дирекция ГК', f'{prefix}g', 'int', 12),
        Col('ПЭП', f'{prefix}p', 'int', 10),
        Col('Центр занятости', f'{prefix}z', 'int', 14),
    ])


COLUMNS = [
    Col('Регион', 'name', 'text', 36),
    Col('Всего обращений', 'ob', 'int', 14),
    _sources('ob'),
    Col('Всего оказано услуг (принято решение о назначении)', 'na', 'int', 22),
    _sources('na'),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select b.name,
       sum(case when t.prt = 1 then t.cnt end) ob,
       sum(case when t.prt = 1 and t.id_sour = 'CON' then t.cnt else 0 end) obc,
       sum(case when t.prt = 1 and t.id_sour = 'GCV' then t.cnt else 0 end) obg,
       sum(case when t.prt = 1 and t.id_sour = 'PEP' then t.cnt else 0 end) obp,
       sum(case when t.prt = 1 and t.id_sour = 'ZSP' then t.cnt else 0 end) obz,
       sum(case when t.prt = 2 then t.cnt end) na,
       sum(case when t.prt = 2 and t.id_sour = 'CON' then t.cnt else 0 end) nac,
       sum(case when t.prt = 2 and t.id_sour = 'GCV' then t.cnt else 0 end) nag,
       sum(case when t.prt = 2 and t.id_sour = 'PEP' then t.cnt else 0 end) nap,
       sum(case when t.prt = 2 and t.id_sour = 'ZSP' then t.cnt else 0 end) naz
  from rfbn_branch b,
       (select 1 prt,
               substr(ms.brid, 1, 2) || '00' br,
               zd.id_sour,
               count(ms.id) cnt
          from ss_z_doc zd, ss_m_sol ms
         where d_inp >= :d_from
           and d_inp <  :d_to
           and id_osn = 103
           and zd.id_tip = 'NEW'
           and zd.id = ms.id
           and exists (select 1
                         from ss_m_sol_st st
                        where st.sid = ms.id
                          and st.st2 in (4, 16, 29)
                          and not exists (select 1 from ss_m_sol_st e
                                           where e.backid = st.id
                                             and e.sid = st.sid)
                          and not exists (select 1 from ss_m_sol_st e
                                           where e.id = st.id
                                             and e.backid is not null))
         group by substr(ms.brid, 1, 2), zd.id_sour
        union
        select 2 prt,
               substr(rfbn_id, 1, 2) || '00' br,
               zd.id_sour,
               count(sipr_id) cnt
          from sipr_maket_first_approve_2 sfa, ss_z_doc zd
         where date_approve >= :d_from
           and date_approve <  :d_to
           and rfpm_id like '0703%'
           and sfa.sipr_id = zd.id
         group by substr(rfbn_id, 1, 2), zd.id_sour) t
 where b.rfbn_id = t.br
 group by b.rfbn_id, b.name
 order by b.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
