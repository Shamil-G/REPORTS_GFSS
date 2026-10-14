# -*- coding: utf-8 -*-
"""8014. Динамика численности получателей и сумм социальных выплат в разрезе
рисков.

Перенос WEB_REP_R_8014 (AIS 8014, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8014.xlsx` (2005-2025).

Строка - год платёжного документа (`pnpd_document.pncp_date`) от 2005 до
выбранного периода (в оригинале зашит 01.08.2025). Для каждого вида выплат -
число различных получателей (`pncd_id`) и сумма `pay_sum + sum_debt`:
0702 утрата трудоспособности, 0701 потеря кормильца, 0703 потеря работы,
0704 по беременности и родам, 0705 уход за ребенком, 0706 на период ЧП,
0707 работникам организаций здравоохранения в случае заражения, 0708 в случае
смерти, 0709 на период ввода ограничительных мероприятий; «Всего» - по всем
документам. Условия те же, что в 8001 (`ridt_id in (4, 6, 7, 8)`,
`status in (0, 1, 2, 3, 5, 7)`, `pnsp_id > 0`). Последняя строка - только суммы,
как в оригинале (численность по годам не складывается: люди повторяются).

Ошибки оригинала, исправленные при переносе (образец их воспроизводит):
  - число получателей в каждом из девяти блоков считалось по виду 0701
    (`case when ... = '0701'` скопирован во все `cnt`), поэтому в образце одно
    и то же число (2025: 65 398) стоит во всех блоках. Здесь - по своему виду;
  - суммы 0701 и 0702 в образце стоят под обратными заголовками: под «утратой
    трудоспособности» (0702) лежала сумма потери кормильца (0701). Сверено с 8001
    и 8007: 0702 за январь-июль 2025 - 30 093 872 097,78, 0701 - 22 181 397 864.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '8014'
report_name = ('Динамика численности получателей и сумм социальных выплат в '
               'разрезе рисков\nпо состоянию на {today}г. '
               '(8014, составлен без технического задания)')

_CNT = 'Число получателей (человек)'
_SUM = 'Сумма выплат (тенге)'

_TYPES = [
    ('0702', 'утрата трудоспособности'),
    ('0701', 'потеря кормильца'),
    ('0703', 'потеря работы'),
    ('0704', 'по беременности и родам'),
    ('0705', 'уход за ребенком'),
    ('0706', 'на период ЧП'),
    ('0707', 'работникам организаций здравоохранения, в случае заражения'),
    ('0708', 'работникам организаций здравоохранения, в случае смерти'),
    ('0709', 'на период ввода ограничительных мероприятий'),
]

COLUMNS = [
    Col('Период', 'p', 'text', 12),
    Group('Всего', [
        Col(_CNT, 'cnt', 'int', 14, align='center', total=False),
        Col(_SUM, 'sm', 'money', 22),
    ]),
]
for code, title in _TYPES:
    COLUMNS.append(Group(title, [
        Col(_CNT, f'cnt_{code}', 'int', 14, align='center', total=False),
        Col(_SUM, f'sm_{code}', 'money', 22),
    ]))

_AGG = ',\n'.join(
    f"           count(distinct case when substr(d.rfpm_id, 1, 4) = '{code}' then d.pncd_id end) cnt_{code},\n"
    f"           sum(case when substr(d.rfpm_id, 1, 4) = '{code}' then d.pay_sum + d.sum_debt else 0 end) sm_{code}"
    for code, _ in _TYPES)
_SEL = ', '.join(f'cnt_{c}, sm_{c}' for c, _ in _TYPES)
_TOT = ', '.join(f'null, sum(sm_{c})' for c, _ in _TYPES)

STMT = f"""
with g as (
    select /*+parallel(8)*/
           to_char(d.pncp_date, 'yyyy') p,
           count(distinct d.pncd_id) cnt,
           sum(d.pay_sum + d.sum_debt) sm,
{_AGG}
      from pnpd_document d
     where d.pncp_date >= date '2005-01-01'
       and d.pncp_date <  :d_to
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
     group by to_char(d.pncp_date, 'yyyy')
)
select p, cnt, sm, {_SEL}, bold
  from (
    select p ord, p, cnt, sm, {_SEL}, 0 bold from g
    union all
    select 'zzzz', null, null, sum(sm), {_TOT}, 1 from g
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, bold_key='bold',
)
