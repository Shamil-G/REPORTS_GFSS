# -*- coding: utf-8 -*-
"""============================================================
ДИА, «Консолидированные отчеты»: средние с начала года и за месяц.
Образец данных и запроса - rep_stat_extend/«Средние с начала года и за
месяц.xlsx» (лист SQL Statement), Шамиль, 07.10.2026.
============================================================

Средние социальные отчисления на участника и средний возраст участников.
Четыре строки: с начала выбранного года по выбранный месяц включительно, за
выбранный месяц, и то же за предыдущий год. Каждая строка - селект образца
со своими границами периода (`start_date`, `before_date`), строки склеены
`union all`.

Источник - `si_member_2` (КНП 012) + `person`. Платёж попадает в период, если
в него входят и дата платежа `pay_date`, и период платежа `pay_month`.
По каждому участнику: сумма СО, число разных периодов платежа `cnt_month`,
среднее за период `сумма / cnt_month`, возраст на середину отчётного
периода `months_between(середина, birthdate) / 12`. Колонки:
  - «Среднее по средним СО» - среднее по участникам их средних за период;
  - «Средний возраст» - средний возраст участников;
  - «Усредненное по всем сразу» - вся сумма / сумма cnt_month по всем.
За один месяц у каждого cnt_month = 1, поэтому первая и третья колонки
совпадают (так и в образце).

Отличие от образца: исключение плательщиков ЕСП - латинская «E»
(`type_payer != 'E'`). В образце стоит кириллическая «Е», которая в
`si_member_2` не встречается, поэтому ничего не исключала; в 2025-2026 ЕСП в
`si_member_2` нет вовсе, так что на цифры это не влияет.
Подписи строк - как в образце: «Средние за 8 месяцев 2026», «Средние за
АВГУСТ месяц 2026».
"""
from db.connect import LOADER_PROFILE
from util.period import split_period, period_name
from util.xlsx_report import build_report, Col

report_code = 'AVG-SO'
report_name = 'Средние с начала года и за месяц'

COLUMNS = [
    Col('Период', 'period_name', 'text', 34),
    Col('Среднее по средним СО', 'avg_avg', 'money', 22),
    Col('Средний возраст', 'avg_age', 'money', 16),
    Col('Усредненное по всем сразу', 'avg_all', 'money', 26),
]

# Селект образца. start / before - границы периода (before исключительная).
_SELECT = """
select {n} n, '{label}' period_name,
       sum(avg_sum) / count(sicid) avg_avg,
       sum(age) / count(sicid) avg_age,
       sum(sum_pay) / sum(cnt_month) avg_all
  from (select /*+ parallel(8) */
               sum(si.sum_pay) sum_pay,
               count(unique si.pay_month) cnt_month,
               sum(si.sum_pay) / count(unique si.pay_month) avg_sum,
               si.sicid,
               months_between({start} + ({before} - {start}) / 2, p.birthdate) / 12 age
          from si_member_2 si, person p
         where si.knp = '012'
           and si.pay_date  >= {start}
           and si.pay_date  <  {before}
           and si.pay_month >= {start}
           and si.pay_month <  {before}
           and si.type_payer != 'E'
           and si.sicid = p.sicid
         group by si.sicid, p.birthdate)"""


def _months(n):
    if n == 1:
        return 'месяц'
    return 'месяца' if 2 <= n <= 4 else 'месяцев'


def STMT(params):
    """:y_from - 1 января, :d_from / :d_to - выбранный месяц (:d_to
    исключительная); предыдущий год - те же границы минус 12 месяцев."""
    year = int(params['rep_year'])
    _, month = split_period(params['period'])
    ytd = f'Средние за {month} {_months(month)}'
    mon = f'Средние за {period_name(1, month).upper()} месяц'
    blocks = [
        (f'{ytd} {year}', ':y_from', ':d_to'),
        (f'{mon} {year}', ':d_from', ':d_to'),
        (f'{ytd} {year - 1}', 'add_months(:y_from, -12)', 'add_months(:d_to, -12)'),
        (f'{mon} {year - 1}', 'add_months(:d_from, -12)', 'add_months(:d_to, -12)'),
    ]
    sql = '\nunion all'.join(
        _SELECT.format(n=n, label=label, start=start, before=before)
        for n, (label, start, before) in enumerate(blocks, start=1))
    return sql + '\n order by n\n'


do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True,
)
