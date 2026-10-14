# -*- coding: utf-8 -*-
"""8009. Динамика численности участников СОСС и сумм социальных отчислений за
все годы.

Перенос WEB_REP_R_8009 (AIS 8009, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8009.xlsx` (2005-2025).

Строка - год: число различных участников с КНП 012 (`sicid`), сумма
социальных отчислений (КНП 012), пеня (КНП 017) и их сумма. Платёж относится к
году по дате поступления в ГФСС (`pay_date_gfss`); берутся платежи, сделанные
с декабря предыдущего года (`pay_date >= add_months(начало года, -1)`), как в
оригинале. Последний год обрезается по выбранному периоду.

Отличие от оригинала: прошлые годы (до 2025) оригинал не считал, а брал из
таблицы `report_8009`, заполненной вручную неизвестно когда; здесь все годы
считаются одним запросом по `si_member_2` теми же условиями, что давал
живой запрос 2025 года. Итог по колонке численности не считается (в оригинале
пусто: люди повторяются из года в год).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '8009'
report_name = ('Динамика численности участников СОСС и сумм социальных '
               'отчислений {period} (8009, составлен без технического задания)')

_period_label = make_period_label({7: 'за 2005-{year} годы'})

COLUMNS = [
    Col('период', 'p', 'center', 12),
    Col('количество участников*, человек', 'cnt', 'int', 20, total=False),
    Col('сумма СО', 'sm012', 'money', 22),
    Col('пеня', 'sm017', 'money', 20),
    Col('сумма СО + пеня', 'sm', 'money', 22),
]

# Один проход по si_member_2 (около 1,4 млрд строк), год - по pay_date_gfss.
# Условие по pay_date - как в оригинале: с декабря предыдущего года до конца года
# (последний год - до конца периода).
STMT = """
with g as (
    select /*+parallel(8)*/
           to_char(m.pay_date_gfss, 'yyyy') p,
           count(distinct case when m.knp = '012' then m.sicid end) cnt,
           sum(case when m.knp = '012' then m.sum_pay else 0 end) sm012,
           sum(case when m.knp = '017' then m.sum_pay else 0 end) sm017,
           sum(m.sum_pay) sm
      from si_member_2 m
     where m.pay_date_gfss >= date '2005-01-01'
       and m.pay_date_gfss <  :d_to
       and m.pay_date >= add_months(trunc(m.pay_date_gfss, 'YYYY'), -1)
       and m.pay_date <  least(add_months(trunc(m.pay_date_gfss, 'YYYY'), 12), :d_to)
     group by to_char(m.pay_date_gfss, 'yyyy')
)
select p, cnt, sm012, sm017, sm, bold
  from (
    select p ord, p, cnt, sm012, sm017, sm, 0 bold from g
    union all
    select 'zzzz', null, null, sum(sm012), sum(sm017), sum(sm), 1 from g
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    bold_key='bold',
)
