# -*- coding: utf-8 -*-
"""8002. Назначение социальных выплат из АО «ГФСС».

Перенос WEB_REP_R_8002 (AIS 8002, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец формы - `docs/8000/Rep__8002_2026-09.xlsx`.
Период - с начала года по выбранный месяц, как у 8001.

Берутся первые назначения `sipr_maket_first_approve_2` с `date_approve` за
период (по человеку: `person.sicid = sicp_id`) пяти видов 0702, 0701, 0703,
0704, 0705; строки и разделы те же, что у 8001. Колонки:
  - «Численность назначенных СВ» - число назначений (`count(iin)`), не людей;
  - «Средний размер» - среднее `sum_all`; «Сумма» - сумма `sum_all`;
  - «СМД» - среднее `sum_avg`;
  - «Коэффициент замещения» - 100 * (средний размер) / СМД по округлённым
    значениям, как в оригинале.

Как в оригинале: названия подвидов 1.x, 2.x, 3.x - из `rfpm_payments`; справочник
соединялся внешним образом только у раздела 1 (назначения с неизвестным кодом
попадают в 1 и 1.x, а в 2-5 нет). Последняя строка без названия - сумма
разделов (оригинал считал `sum(...)/2` по всем строкам). Численность итога -
сумма назначений по разделам.

Отличия от оригинала: расчёт не пишется в таблицу `rep_8002` (оригинал при
первом запросе месяца делал `insert` и дальше возвращал замороженные цифры);
в подвиде 4.2 добавлен пробел перед скобкой («Усыновление (удочерение)
ребенка»).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '8002'
report_name = ('Назначение социальных выплат из АО "ГФСС" {period}\n'
               'по состоянию на {today} г. '
               '(8002, составлен без технического задания)')

_period_label = make_period_label({7: 'за {year} год'})

COLUMNS = [
    Col('Показатели', 'name', 'text', 60),
    Group('с {date_from} по {date_to} года', [
        Col('Численность назначенных СВ, человек', 'cnt', 'int', 16,
            align='center'),
        Col('Средний размер назначенных СВ, тенге', 'avg_sum', 'money', 20),
        Col('Сумма назначенных социальных выплат в месяц (кроме СВбр)', 'sm',
            'money', 24),
        Col('СМД, принятый для исчисления социальной выплаты', 'smd', 'money',
            20),
        Col('Коэффициент замещения утраченного дохода', 'kzud', 'money', 18),
    ]),
]

# n - раздел (1: 0702, 2: 0701, 3: 0703, 4: 0704, 5: 0705), sub - подвид
# (0 - сам раздел). Подвиды 5.x: коды 0001-0004 и 0101-0104 в один подвид.
STMT = """
with src as (
    select /*+parallel(4)*/
           s.rfpm_id, s.iin, s.sum_all, s.sum_avg,
           decode(substr(s.rfpm_id, 1, 4), '0702', 1, '0701', 2, '0703', 3,
                  '0704', 4, 5) n,
           rp.rfpm_id rp_id, rp.name rp_name
      from sipr_maket_first_approve_2 s, person p, rfpm_payments rp
     where s.sicp_id = p.sicid
       and s.date_approve >= :y_from
       and s.date_approve <  :d_to
       and substr(s.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
       and rp.rfpm_id(+) = s.rfpm_id
),
parent as (
    select r.n, 0 sub, to_char(r.n) num,
           decode(r.n, 1, 'Социальная выплата на случай утраты трудоспособности',
                       2, 'Социальная выплата на случай потери кормильца',
                       3, 'Социальная выплата на случай потери работы',
                       4, 'Социальная выплата на случай потери дохода в связи с беременностью и родами, усыновлением (удочерением) ребенка (детей)',
                       5, 'Социальная выплата на случай потери дохода в связи с уходом за ребенком по достижении им возраста полутора лет') name,
           count(r.iin) cnt,
           round(avg(r.sum_all), 2) avg_sum,
           sum(r.sum_all) sm,
           round(avg(r.sum_avg), 2) smd
      from src r
     where r.n = 1 or r.rp_id is not null
     group by r.n
),
leaf as (
    select r.n, r.rfpm_id, r.rp_name, r.iin, r.sum_all, r.sum_avg,
           case when r.n <= 3 then to_number(substr(r.rfpm_id, 8, 1))
                when r.n = 4 then decode(substr(r.rfpm_id, 1, 6), '070403', 2, 1)
                else decode(r.rfpm_id, '07050001', 1, '07050101', 1,
                                       '07050002', 2, '07050102', 2,
                                       '07050003', 3, '07050103', 3,
                                       '07050004', 4, '07050104', 4)
           end sub,
           case when r.n <= 3 then r.rp_name
                when r.n = 4 then decode(substr(r.rfpm_id, 1, 6), '070403',
                                         'Усыновление (удочерение) ребенка',
                                         'По беременности и родам')
                else decode(r.rfpm_id, '07050001', 'за первым ребенком', '07050101', 'за первым ребенком',
                                       '07050002', 'за вторым ребенком', '07050102', 'за вторым ребенком',
                                       '07050003', 'за третьим ребенком', '07050103', 'за третьим ребенком',
                                       '07050004', 'за четвертым ребенком', '07050104', 'за четвертым ребенком')
           end name
      from src r
     where r.n = 1 or r.rp_id is not null
),
child as (
    select f.n, f.sub, f.n || '.' || f.sub num, f.name,
           count(f.iin) cnt,
           round(avg(f.sum_all), 2) avg_sum,
           sum(f.sum_all) sm,
           round(avg(f.sum_avg), 2) smd
      from leaf f
     where f.sub is not null
     group by f.n, f.sub, case when f.n <= 3 then f.rfpm_id end, f.name
),
tot as (
    select sum(cnt) cnt, sum(sm) sm from parent
)
select num, name, cnt, avg_sum, sm, smd, kzud, bold
  from (
    select r.n * 100 + r.sub ord, r.num, r.name, r.cnt, r.avg_sum, r.sm, r.smd,
           100 * r.avg_sum / nullif(r.smd, 0) kzud,
           decode(r.sub, 0, 1, 0) bold
      from (select n, sub, num, name, cnt, avg_sum, sm, smd from parent
            union all
            select n, sub, num, name, cnt, avg_sum, sm, smd from child) r
    union all
    select 9999, null, null, t.cnt, null, t.sm, null, null, 1
      from tot t
  )
 order by ord, name
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    num_key='num', bold_key='bold',
)
