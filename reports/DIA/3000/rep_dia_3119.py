# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3119 (процедура REP_R_3119).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о количестве участников СОСС из числа иностранных граждан и сумме
социальных отчислений, пени, поступивших в АО "ГФСС", по регионам.

Источник - `si_member_2` + `person`, иностранец - `citizenship_id <> 105`.
Регион - первые два знака `person.branchid`, название - `rfbn_branch`
(`reg || '00' = rfbn_id`). Количество - уникальные `sicid` отдельно по
КНП 012 (социальные отчисления) и 017 (пеня), сумма - по тем же КНП.

Отклонение от оригинала в названии: в процедуре заголовок печатал
`to_char(pMonth, 'month yyyy')`, а переменная pMonth нигде не заполнялась
(присвоение закомментировано), поэтому период в названии выходил пустым:
«..., года». Параметры отчёта - две даты, и подпись строится по ним:
«..., с 01.09.2026 по 30.09.2026 года». Остальной текст дословно.

Окна дат как в оригинале: `pay_date_gfss` в периоде, `pay_date` - на месяц
шире слева (`add_months(:d_from, -1)`).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3119'
report_name = ('Сведения о количестве участников СОСС из числа иностранных '
               'граждан и сумме социальных отчислений, пени, поступивших в '
               'АО "ГФСС" в разрезе регионов, с {period} года')

COLUMNS = [
    Col('Код', 'reg', 'center', 8),
    Col('Регион', 'name', 'text', 34),
    Group('Социальные отчисления', [
        Col('Количество, человек', 'c012', 'int', 16),
        Col('Сумма, тенге', 's012', 'money', 20),
    ]),
    Group('Пеня за несвоевременное перечисление социальных отчислений', [
        Col('Количество, человек', 'c017', 'int', 16),
        Col('Сумма, тенге', 's017', 'money', 20),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select /*+parallel(4)*/ t.reg,
       br.name,
       count(distinct case when knp = '012' then sicid else null end) c012,
       sum(case when knp = '012' then sp else 0 end)                  s012,
       count(distinct case when knp = '017' then sicid else null end) c017,
       sum(case when knp = '017' then sp else 0 end)                  s017
  from (select substr(p.branchid, 1, 2) reg,
               p.sicid,
               sim.knp,
               sum(sim.sum_pay) sp
          from si_member_2 sim, person p
         where sim.pay_date_gfss >= :d_from
           and sim.pay_date_gfss <  :d_to
           and sim.pay_date      >= add_months(:d_from, -1)
           and sim.pay_date      <  :d_to
           and sim.sicid = p.sicid
           and p.citizenship_id <> 105
         group by substr(p.branchid, 1, 2), p.sicid, sim.knp) t,
       rfbn_branch br
 where t.reg || '00' = br.rfbn_id
 group by t.reg, br.name
 order by t.reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
