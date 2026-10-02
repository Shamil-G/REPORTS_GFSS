# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3120 (процедура REP_R_3120).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения об иностранных гражданах - получателях социальных выплат
в разрезе стран.

Источник - `pnpd_document` + `person` + `dic_country`, иностранец -
`citizenship_id <> 105`, документы за месяц с отбором как в остальных
отчётах по выплатам (`pnsp_id > 0`, `ridt_id in (4, 6, 7, 8)`,
`status in (0, 1, 2, 3, 5, 7)`). Количество - уникальные `pncd_id`.

Категория: страны ЕАС - коды 112, 51, 417, 643, остальные - «Другие
страны». Порядок: сначала ЕАС, внутри категории - по убыванию количества
(`order by 1, 4 desc`).

Название дословно (двойной пробел после дефиса убран). Период - месяц
(в оригинале `pDateTo = last_day(pMonth)`); подпись `to_char(pMonth,
'month yyyy')` - месяц строчными, год через пробел.

`dic_country` лежит в схеме SSWH боевой БД, в тестовой reports_test её нет:
на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '3120'
report_name = ('Сведения об иностранных гражданах - получателях социальных '
               'выплат в разрезе стран, {period} года')

_period_label = make_period_label({1: '{month} {year}'})

COLUMNS = [
    Col('Страна', 'ru_name', 'text', 40),
    Col('Категория', 'tip', 'text', 20),
    Col('Количество, человек', 'cnt', 'int', 20),
]

# :d_from / :d_to - границы месяца, :d_to исключительная.
STMT = """
select case when dc.code in (112, 51, 417, 643) then 0 else 1 end ord,
       case when dc.code in (112, 51, 417, 643) then 'Страны ЕАС'
            else 'Другие страны' end tip,
       dc.ru_name,
       count(distinct pd.pncd_id) cnt
  from pnpd_document pd, person p, dic_country dc
 where pd.pncd_id = p.sicid
   and p.citizenship_id = dc.id
   and p.citizenship_id <> 105
   and pd.pncp_date >= :d_from
   and pd.pncp_date <  :d_to
   and pd.pnsp_id > 0
   and pd.ridt_id in (4, 6, 7, 8)
   and pd.status in (0, 1, 2, 3, 5, 7)
 group by dc.ru_name, dc.code
 order by 1, 4 desc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
