# -*- coding: utf-8 -*-
"""8015. Сведения о средних размерах социальных выплат.

Перенос WEB_REP_R_8015 (AIS 8015, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8015.xlsx`.

Оригинал читал таблицу `rep_8015`, заполненную вручную (готовые строки вида
«7 284», «115,9%»). Таблицы больше нет: размер считается из данных. Сверка с
таблицей: средний размер выплаты - среднее `payment_history.sum_pay` по
платёжным документам `pnpd_document` вида (`ridt_id in (4, 6, 7, 8)`,
`status in (0, 1, 2, 3, 5, 7)`, `pnsp_id > 0`, как в 8001): за январь-июль
2025 0701 = 48 662, 0702 = 47 505, 0703 = 98 353; за 2024 год 0701 = 44 139,
0702 = 42 929 - все совпали с таблицей.

Только 2024 год и позже: `payment_history` хранит платежи с 2024 года, а
значения таблицы за 2012-2023 получены другим способом, которого в БД нет и
который не восстанавливается (среднее по документам даёт за 2012 год 3 790, по
человеко-месяцам 7 496 вместо 7 284 в таблице). Поэтому годы до 2024 в отчёте
не показываются, а темп роста первого года (2024) не считается.

Раскладка отличается от образца: в образце годы шли колонками, виды выплат -
строками (размер и темп роста попарно). Колонок в рендерере фиксированное
число, а набор лет зависит от выбранного года, поэтому здесь наоборот: строка
- период, у каждого вида две колонки (размер, темп роста). Строки: годы с 2024
по предпоследний, «N мес. <прошлый год>», прошлый год целиком, «N мес.
<выбранный год>», где N - месяц периода. Темп роста - отношение к предыдущему
году, для «N мес.» выбранного года - к тем же N месяцам прошлого года, для
«N мес.» прошлого года не считается (как в образце).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '8015'
report_name = ('Сведения о средних размерах*** социальных выплат {period} '
               '(8015, составлен без технического задания)')


def _label(rep_year, date_type, date_start=None):
    last = int(rep_year) - 1
    return 'за 2024 год' if last <= 2024 else f'за 2024-{last} годы'


# (код вида, подпись) в порядке образца
_TYPES = [
    ('0702', 'на случай утраты трудоспособности'),
    ('0701', 'на случай потери кормильца'),
    ('0703', 'на случай потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, с '
             'усыновлением (удочерением) новорожденного'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1,5 лет'),
]

COLUMNS = [Col('Период', 'label', 'text', 18)]
for code, title in _TYPES:
    COLUMNS.append(Group(title, [
        Col('Средний размер* социальных выплат**', f'a_{code}', 'money', 16),
        Col('темп роста, %', f'g_{code}', 'pct', 12),
    ]))

_COLS = ',\n'.join(
    f"       max(case when r = '{c}' then a end) a_{c},\n"
    f"       max(case when r = '{c}' then g end) g_{c}"
    for c, _ in _TYPES)

# y: полные годы с 2024 (с этого года есть payment_history);
# ytd: те же месяцы периода в прошлом (k = 0) и выбранном (k = 1) году.
STMT = f"""
with y as (
    select /*+parallel(8)*/
           extract(year from d.pncp_date) yr, substr(d.rfpm_id, 1, 4) r,
           avg(ph.sum_pay) a
      from pnpd_document d, payment_history ph
     where d.pnpd_id = ph.pnpd_id(+)
       and d.pncp_date >= date '2024-01-01'
       and d.pncp_date <  :y_from
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
     group by extract(year from d.pncp_date), substr(d.rfpm_id, 1, 4)
),
ytd as (
    select /*+parallel(8)*/
           x.k, x.r, avg(x.ph) a
      from (select case when d.pncp_date < :y_from then 0 else 1 end k,
                   substr(d.rfpm_id, 1, 4) r, ph.sum_pay ph
              from pnpd_document d, payment_history ph
             where d.pnpd_id = ph.pnpd_id(+)
               and ((d.pncp_date >= add_months(:y_from, -12)
                     and d.pncp_date <  add_months(:d_to, -12))
                 or (d.pncp_date >= :y_from and d.pncp_date < :d_to))
               and d.ridt_id in (4, 6, 7, 8)
               and d.status in (0, 1, 2, 3, 5, 7)
               and d.pnsp_id > 0
               and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')) x
     group by x.k, x.r
),
yg as (
    select yr, r, a, a / nullif(lag(a) over (partition by r order by yr), 0) g
      from y
),
v as (
    select yr * 10 ord, to_char(yr) label, r, a, g
      from yg
    union all
    select (extract(year from :y_from) - 1) * 10 - 5,
           months_between(:d_to, :y_from) || ' мес. ' || (extract(year from :y_from) - 1),
           r, a, null
      from ytd where k = 0
    union all
    select extract(year from :y_from) * 10,
           months_between(:d_to, :y_from) || ' мес. ' || extract(year from :y_from),
           c.r, c.a, c.a / nullif(p.a, 0)
      from ytd c, ytd p
     where c.k = 1 and p.k = 0 and p.r = c.r
)
select label,
{_COLS}
  from v
 group by ord, label
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_label,
)
