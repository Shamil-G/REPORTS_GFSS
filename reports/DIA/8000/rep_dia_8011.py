# -*- coding: utf-8 -*-
"""8011. Сведения по Единому платежу по полу и возрасту.

Перенос WEB_REP_R_8011 (AIS 8011, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8011_01_01_2026-30_09_2026.xlsx`
(с 01.01.2026 по 30.09.2026).

Период - две даты, как параметры оригинала. Берутся платежи социальных
отчислений (`type_payment = 'O'`, КНП 012) с датой поступления в ГФСС
(`pay_date_gfss`) в периоде и датой платежа (`pay_date`) не раньше чем за 14
дней до начала периода. Возраст - полных лет на дату «по» (`person.birthdate`),
группы по 5 лет от 20: все моложе 20 лет попадают в «15 - 19», старше 64 -
в «65 - 69» и далее (как `width_bucket(возраст, 20, 65, 9)` в оригинале).
Пол - `person.sex` (0 - женщины, 1 - мужчины). «Количество участников» - число
различных `sicid`, «Сумма» - сумма `sum_pay`; последняя строка (без названия,
как в оригинале) - итог по всем возрастам, численность в ней - различные
участники, а не сумма по группам.

Отличие от оригинала: начало периода в SQL было зашито (01.01.2025), параметр
«с» не использовался; здесь используется. Поэтому образец (в его заголовке
«с 01.01.2026», а цифры - с 01.01.2025: женщин 48 685, а не 32 507) воспроизводится
только при дате «с» 01.01.2025 - так сверено, все строки совпали до копейки.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '8011'
report_name = ('Сведения по Единому платежу\nс {date_from} по {date_to} года\n'
               'По полу и возрасту (8011, составлен без технического задания)')

_CNT = 'Количество участников*, человек'
_SUM = 'Сумма (тенге)'

COLUMNS = [
    Col('Возраст', 'age', 'text', 14),
    Group('Женщины', [
        Col(_CNT, 'cnt_0', 'int', 20),
        Col(_SUM, 'sm_0', 'money', 22),
    ]),
    Group('Мужчины', [
        Col(_CNT, 'cnt_1', 'int', 20),
        Col(_SUM, 'sm_1', 'money', 22),
    ]),
]

STMT = """
with g as (
    select /*+parallel(4)*/
           trunc(months_between(:d_to - 1, p.birthdate) / 12) let,
           p.sex, si.sum_pay, p.sicid
      from si_member_2 si, person p
     where si.sicid = p.sicid
       and si.type_payment = 'O'
       and si.knp = '012'
       and si.pay_date_gfss >= :d_from
       and si.pay_date_gfss <  :d_to
       and si.pay_date >= :d_from - 14
       and si.pay_date <  :d_to
),
b as (
    select g.*, width_bucket(g.let, 20, 65, 9) w from g
)
select age, cnt_0, sm_0, cnt_1, sm_1, bold
  from (
    select to_char(20 + 5 * (w - 1)) || ' - ' || to_char(19 + 5 * w) age,
           20 + 5 * (w - 1) ord,
           count(distinct case when sex = 0 then sicid end) cnt_0,
           sum(case when sex = 0 then sum_pay else 0 end) sm_0,
           count(distinct case when sex = 1 then sicid end) cnt_1,
           sum(case when sex = 1 then sum_pay else 0 end) sm_1,
           0 bold
      from b
     group by w
    union all
    select null, 9999,
           count(distinct case when sex = 0 then sicid end),
           sum(case when sex = 0 then sum_pay else 0 end),
           count(distinct case when sex = 1 then sicid end),
           sum(case when sex = 1 then sum_pay else 0 end),
           1
      from b
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, bold_key='bold',
)
