# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3327 (процедура REP_R_3327).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Количество отказанных дел по причинам, в разрезе областей: число людей с
отказом (статус 12) на 1-м и на 2-м этапе обращения по регионам.

Источник - `all_list_42500` + `ss_m_sol_st` (по номеру дела и статусу) +
`rfbn_branch`. Две части (`union all`): «1-этап» - отказ на 1-м этапе
(`st_code1 = 12`, на 2-м пусто, 0 или 12), дата обращения 1-го этапа в
периоде; «2-этап» - отказ на 2-м этапе без решения на 1-м, дата обращения
2-го этапа в периоде. Регион человека -
`first_value(substr(rfbn_id, 1, 2) || '00') over (partition by sicid)`,
без порядка - как в оригинале (если у человека несколько регионов в списке,
выбор произвольный; на практике в `all_list_42500` одна строка на человека).

Название дословно, но «с» перед датой кириллическая (в оригинале латинская «c»).
«Этап» печатается текстом «1-этап» / «2-этап». Сортировка - по этапу и коду региона (`order by 1, 2`).
Закомментированные в оригинале условия не переносятся.

`all_list_42500` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3327'
report_name = ('Количество отказанных дел по причинам, в разрезе областей '
               'с {period}')

COLUMNS = [
    Col('Этап', 'period', 'center', 12),
    Col('Код региона', 'rfbn', 'center', 12),
    Col('Наименование региона', 'name', 'text', 40),
    Col('Кол-во', 'sicid', 'int', 14),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select '1-этап' as period,
       substr(rfbn, 1, 2) rfbn,
       br.name name,
       count(sicid) sicid
  from (select a.sicid,
               first_value(substr(a.rfbn_id, 1, 2) || '00')
                   over (partition by a.sicid) rfbn
          from all_list_42500 a, ss_m_sol_st st
         where st.sid = a.id_p1
           and st.s_st = a.st_code1
           and coalesce(a.st_code1, 0) in (12)
           and coalesce(a.st_code2, 0) in (0, 12)
           and a.date_obr_p1 >= :d_from
           and a.date_obr_p1 <  :d_to) c,
       rfbn_branch br
 where c.rfbn = br.rfbn_id
 group by br.name, substr(rfbn, 1, 2)
union all
select '2-этап' as period,
       substr(rfbn, 1, 2) rfbn,
       br2.name name,
       count(sicid) sicid
  from (select b.sicid,
               first_value(substr(b.rfbn_id, 1, 2) || '00')
                   over (partition by b.sicid) rfbn
          from all_list_42500 b, ss_m_sol_st sol
         where sol.sid = b.id_p2
           and sol.s_st = b.st_code2
           and coalesce(b.st_code2, 0) in (12)
           and coalesce(b.st_code1, 0) in (0)
           and b.date_obr_p2 >= :d_from
           and b.date_obr_p2 <  :d_to) d,
       rfbn_branch br2
 where d.rfbn = br2.rfbn_id
 group by br2.name, substr(rfbn, 1, 2)
 order by 1, 2
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
