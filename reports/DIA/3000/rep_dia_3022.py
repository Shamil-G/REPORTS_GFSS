# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3022 (процедура REP_R_3022).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Аналитический отчёт: стаж участия в СОСС в разрезе возраста.

Источник - `si_member_2` + `person`, только КНП 012. На каждого участника
(`sicid`) считаются сумма взносов за период и число месяцев, в которых были
взносы (`count(distinct pay_month)`); возраст - полных лет на дату поступления
в ГФСС (`months_between(pay_date_gfss, birthdate) / 12`). Затем участники
раскладываются по возрасту и полу: число, сумма и колонки «1 месяц ... 12
месяцев» (последняя - «12 и более») отдельно по числу участников и по сумме.

Окна дат как в оригинале: `pay_date_gfss` в периоде, `pay_date` - на месяц
шире слева (`add_months(:d_from, -1)`). Названия колонок - из `SetPageHead`:
в оригинале это «кол-во N месяц» и «Сумма N месяц», с этими опечатками
в падеже они и печатались. Итоговая строка суммирует колонки 4-29
(`SetColSumTotal(4..29)`), то есть всё, кроме возраста и пола.

Название дословно: «за период с ... по ...». Оригинал запускал запрос
динамическим SQL с датами литералами; здесь это обычные бинды.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3022'
report_name = 'Стаж участия в СОСС в разрезе возраста за период с {period}'

COLUMNS = (
    [Col('Возраст', 'age', 'center', 10),
     Col('Пол', 'sex', 'center', 6),
     Col('Кол-во участников', 'cnt', 'int', 14),
     Col('Сумма взносов', 'sum_all', 'money', 20)]
    + [Col(f'кол-во {n} месяц', f'cnt_mth_{n}', 'int', 12)
       for n in range(1, 13)]
    + [Col(f'Сумма {n} месяц', f'sum_mth_{n}', 'money', 18)
       for n in range(1, 13)]
)

# Строка колонок месяцев: cm = число месяцев со взносами, 12 и больше
# попадают в последнюю колонку.
_CNT = ',\n'.join(
    f"       sum(case when cm {'>=' if n == 12 else '='} {n} then 1 else 0 end) "
    f"cnt_mth_{n}" for n in range(1, 13))
_SUM = ',\n'.join(
    f"       sum(case when cm {'>=' if n == 12 else '='} {n} then pay_sum "
    f"else 0 end) sum_mth_{n}" for n in range(1, 13))

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = f"""
select /*+ parallel(8)*/
       age,
       case when sex = 1 then 'М' else 'Ж' end sex,
       count(unique sicid) cnt,
       sum(pay_sum) sum_all,
{_CNT},
{_SUM}
  from (select s.sicid,
               trunc(months_between(s.pay_date_gfss, p.birthdate) / 12) age,
               p.sex,
               sum(s.sum_pay) pay_sum,
               count(distinct s.pay_month) cm
          from si_member_2 s, person p
         where s.pay_date_gfss >= :d_from
           and s.pay_date_gfss <  :d_to
           and s.pay_date      >= add_months(:d_from, -1)
           and s.pay_date      <  :d_to
           and s.sicid = p.sicid
           and s.knp = '012'
         group by s.sicid,
                  trunc(months_between(s.pay_date_gfss, p.birthdate) / 12),
                  p.sex)
 group by age, sex
 order by age
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
