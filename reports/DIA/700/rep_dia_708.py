# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 708 (процедура Rep_Actuar_8).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средний возраст получателей социальных выплат по потере трудоспособности
на месяц: по коэффициенту утраты трудоспособности (КУТ) число мужчин и женщин
и средний возраст (лет) каждого пола.

Источник - `payment_history` (выплаты месяца `act_month`, вид 0702) +
`person` (`pncd_id = sicid`). КУТ - последняя цифра кода выплаты:
1 -> 0,7; 2 -> 0,5; 3 -> 0,3 (в оригинале справочник `p_Kut`). Возраст -
`months_between(act_month, birthdate) / 12`; пол: `sex = '1'` - мужчины,
`'0'` - женщины. Итоги по колонкам «Кол-во» (`SetColSumTotal` после
них), средний возраст не суммируется.

Параметр - месяц (в оригинале дата, пустая - прошлый месяц; здесь месяц
выбирается в форме). Дата в названии - первое число месяца
(`to_char(p_RepMonth, 'dd.mm.yyyy')`). `<div>`, `<font>`, `<br>` оригинала
не переносятся.
"""
from db.connect import LOADER_PROFILE
from util.period import first_date_label
from util.xlsx_report import build_report, Col, Group

report_code = '708'
report_name = ('Средний возраст получателей социальных выплат по потере '
               'трудоспособности\nна {period}')

COLUMNS = [
    Col('Коэффициент утраты трудоспособности', 'kut', 'center', 22),
    Group('Мужчины', [
        Col('Кол-во', 'cnt_m', 'int', 14),
        Col('Средний возраст', 'age_m', 'money', 16, total=False),
    ]),
    Group('Женщины', [
        Col('Кол-во', 'cnt_f', 'int', 14),
        Col('Средний возраст', 'age_f', 'money', 16, total=False),
    ]),
]

# :d_from - первое число месяца (act_month - месячная дата).
STMT = """
select to_char(decode(substr(ph.rfpm_id, -1), '1', 0.7, '2', 0.5, '3', 0.3), 'FM0D0') kut,
       sum(decode(pr.sex, '1', 1)) cnt_m,
       avg(decode(pr.sex, '1', months_between(ph.act_month, pr.birthdate))) / 12 age_m,
       sum(decode(pr.sex, '0', 1)) cnt_f,
       avg(decode(pr.sex, '0', months_between(ph.act_month, pr.birthdate))) / 12 age_f
  from payment_history ph, person pr
 where act_month = :d_from
   and rfpm_id like '0702%'
   and pncd_id = sicid
 group by substr(ph.rfpm_id, -1)
 order by substr(ph.rfpm_id, -1)
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True,
    period_label=first_date_label,
)
