# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «3154 - Потеря работы», отчёт 3162 (процедура REP_R_3162).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Половозрастная структура получателей СВпр (0703): число получателей по полным
годам возраста на конец периода - всего, мужчин, женщин. В отбор попадают
документы выплат (`pnpd_document`) за период по месяцу выплаты (`pncp_date`),
типы выплаты 4, 6, 7, 8, статусы 0-3, 5, 7, `pnsp_id > 0`; число - уникальных
получателей. Возраст - `trunc(months_between(дата по, дата рождения) / 12)`.

Параметр «область» (в оригинале третий, `0000` или пусто - вся республика,
иначе первые две цифры кода): необязательный список областей; в
зарегистрированной форме его не было, добавлен. Период:
`pncp_date < pDateTo + 1` - как `< :d_to`. Итоги по трём колонкам. В названии
латинская «c» исправлена.

Таблицы reports_test видит; проверено запуском на данных боевой БД (только
чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3162'
report_name = ('Половозрастная структура получателей социальной выплаты на '
               'случай потери работы с {date_from} по {date_to} года')

COLUMNS = [
    Col('Возраст, лет', 'let', 'center', 14),
    Group('Количество получателей социальной выплаты на случай потери работы, человек', [
        Col('Всего', 'cnt', 'int', 12),
        Group('в том числе', [
            Col('Мужчины', 'cnt_m', 'int', 12),
            Col('Женщины', 'cnt_w', 'int', 12),
        ]),
    ]),
]

# :d_from, :d_to - период (d_to исключительная); :rfbn_id - две цифры области
# (пусто - вся республика).
STMT = """
select let,
       count(distinct pncd_id) cnt,
       count(distinct case when sex = 1 then pncd_id end) cnt_m,
       count(distinct case when sex = 0 then pncd_id end) cnt_w
  from (select d.pncd_id, p.sex,
               trunc(months_between(:d_to - 1, p.birthdate) / 12) let
          from pnpd_document d, person p
         where d.pncd_id = p.sicid
           and d.pncp_date >= :d_from and d.pncp_date < :d_to
           and substr(d.rfpm_id, 1, 4) = '0703'
           and d.rfbn_id like :rfbn_id || '%'
           and d.ridt_id in (4, 6, 7, 8)
           and d.status in (0, 1, 2, 3, 5, 7)
           and d.pnsp_id > 0)
 group by let
 order by let
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
