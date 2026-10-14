# -*- coding: utf-8 -*-
"""8001. Сведения о получателях и суммах социальных выплат из АО «ГФСС».

Перенос WEB_REP_R_8001 (AIS 8001, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец формы - Excel `docs/8000/Rep__8001_2026-09.xlsx`
(период с начала года по сентябрь 2026).

Период - с начала года по выбранный месяц (тип 7, как у app_33): процедура
принимала год и месяц и всегда считала с 1 января.

Что считается. Берутся платёжные документы `pnpd_document` за период
(`ridt_id in (4, 6, 7, 8)`, `status in (0, 1, 2, 3, 5, 7)`, `pnsp_id > 0`) пяти
видов выплат: 0702 (утрата трудоспособности), 0701 (потеря кормильца), 0703
(потеря работы), 0704 (беременность и роды, усыновление), 0705 (уход за
ребенком). Получатель - `pncd_id`; его подвид определяется последним по
`pncp_date` кодом выплаты (`rfpm_id`) среди его документов того же вида
(`first_value ... over (partition by pncd_id)`), а сумма - по всем документам
периода. Колонки:
  - «Численность получателей» - число различных `pncd_id`;
  - «Средний размер» - среднее `payment_history.sum_pay` по документам
    (в заголовке оригинала написано «(гр,5)/(гр,3)», но это не деление суммы на
    численность: 45 271 479 195 / 97 557 дало бы 464 058, а в образце 55 488,39);
  - «Сумма выплат» - `pay_sum + sum_debt`;
  - «Доля к общей сумме» - у раздела к «Общему итогу», у подвида к своему
    разделу (в образце формулы Excel `=E4/$E28` и `=E5/E4`).

Как в оригинале: названия подвидов 1.x, 2.x, 3.x берутся из `rfpm_payments`, и
получатель, чей код выплаты в справочнике не найден, в разделы 3, 4, 5 и в их
подвиды 1-4 не попадает (в разделах 1 и 2 - попадает, там справочник не
соединялся). «Общий итог» - сумма разделов; оригинал считал `sum(...)/2` по всем
строкам, что то же самое, пока разделы равны сумме своих подвидов. Один человек
может получать выплаты разных видов, поэтому численность итога - сумма по
разделам, а не число различных людей.

Отличия от оригинала:
  - расчёт не пишется в таблицу `rep_8001` и не кэшируется в ней: оригинал при
    первом запросе месяца делал `insert`, и повторный запуск возвращал
    замороженные цифры. Здесь отчёт каждый раз считается по данным, а готовый
    файл хранится как у остальных отчётов;
  - `pnpt_payment` в соединение не берётся: оригинал соединял её, но ни одной
    колонки не использовал (`pnpt_id` уникален, строк не размножает);
  - в подвидах 4.2 и 5.x исправлены написание и регистр («Усыновление
    (удочерение) ребенка», «За первым ребенком»; в оригинале «Усыновление(удочерение)»
    и «за первым», но «За вторым»);
  - 8001 создаётся единым запросом вместо двадцати копий подзапроса.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '8001'
report_name = ('Сведения о получателях и суммах социальных выплат из АО "ГФСС" '
               '{period}\nпо состоянию на {today} г. '
               '(8001, составлен без технического задания)')

_period_label = make_period_label({7: 'за {year} год'})

COLUMNS = [
    Col('Показатели', 'name', 'text', 60),
    Group('с {date_from} по {date_to} года', [
        Col('Численность получателей', 'cnt', 'int', 16, align='center'),
        Col('Средний размер тенге (гр,5)/(гр,3)\n(округленное среднее значение '
            'по суммам выплаты из списочной части)', 'avg_ps', 'money', 30),
        Col('Сумма выплат', 'sm', 'money', 22),
        Col('Доля к общей сумме, %', 'pct', 'pct', 16),
    ]),
]

# n - номер раздела, sub - подвида (0 - сам раздел). Порядок разделов в форме:
# 0702, 0701, 0703, 0704, 0705.
#
# lst0: рядом с каждым документом - последний код выплаты получателя в рамках
# его вида (partition by pncd_id, grp). lst: справочник кодов, внешне - у
# документа без записи в справочнике rp_id пустой.
#
# child: подвид для 0701-0703 - сам код выплаты (название из справочника); для
# 0704 - усыновление (07040301) и остальные; для 0705 - номер ребенка, коды
# 0001-0004 (старые) и 0101-0104 сводятся в один подвид. Подвиды 0705 в
# оригинале справочник не соединяли, поэтому rp_id для них не проверяется.
STMT = """
with src as (
    select /*+parallel(4)*/
           substr(d.rfpm_id, 1, 4) grp, d.rfpm_id, d.pncd_id, d.pncp_date,
           d.pay_sum + d.sum_debt sum_pay, ph.sum_pay ps
      from pnpd_document d, payment_history ph
     where d.pnpd_id = ph.pnpd_id(+)
       and d.pncp_date >= :y_from
       and d.pncp_date <  :d_to
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
),
lst0 as (
    select s.grp, s.pncd_id, s.sum_pay, s.ps,
           first_value(s.rfpm_id) over (partition by s.pncd_id, s.grp
                                        order by s.pncp_date desc) rfpm
      from src s
),
lst as (
    select l.grp, l.pncd_id, l.sum_pay, l.ps, l.rfpm,
           decode(l.grp, '0702', 1, '0701', 2, '0703', 3, '0704', 4, 5) n,
           rp.rfpm_id rp_id, rp.name rp_name
      from lst0 l, rfpm_payments rp
     where rp.rfpm_id(+) = l.rfpm
),
parent as (
    select l.n, 0 sub, to_char(l.n) num,
           decode(l.n, 1, 'Социальная выплата на случай утраты трудоспособности',
                       2, 'Социальная выплата на случай потери кормильца',
                       3, 'Социальная выплата на случай потери работы',
                       4, 'Социальная выплата на случай потери дохода в связи с беременностью и родами, усыновлением (удочерением) ребенка (детей)',
                       5, 'Социальная выплата на случай потери дохода в связи с уходом за ребенком по достижении им возраста полутора лет') name,
           count(distinct l.pncd_id) cnt,
           round(avg(l.ps), 2) avg_ps,
           sum(l.sum_pay) sm
      from lst l
     where l.n in (1, 2) or l.rp_id is not null
     group by l.n
),
leaf as (
    select l.n, l.rfpm, l.rp_name, l.pncd_id, l.sum_pay, l.ps,
           case when l.n <= 3 then to_number(substr(l.rfpm, 8, 1))
                when l.n = 4 then decode(l.rfpm, '07040301', 2, 1)
                else decode(l.rfpm, '07050001', 1, '07050101', 1,
                                    '07050002', 2, '07050102', 2,
                                    '07050003', 3, '07050103', 3,
                                    '07050004', 4, '07050104', 4)
           end sub,
           case when l.n <= 3 then l.rp_name
                when l.n = 4 then decode(l.rfpm, '07040301',
                                         'Усыновление (удочерение) ребенка',
                                         'По беременности и родам')
                else decode(l.rfpm, '07050001', 'За первым ребенком', '07050101', 'За первым ребенком',
                                    '07050002', 'За вторым ребенком', '07050102', 'За вторым ребенком',
                                    '07050003', 'За третьим ребенком', '07050103', 'За третьим ребенком',
                                    '07050004', 'За четвертым ребенком', '07050104', 'За четвертым ребенком')
           end name
      from lst l
     where l.rp_id is not null or l.n = 5
),
child as (
    select f.n, f.sub, f.n || '.' || f.sub num, f.name,
           count(distinct f.pncd_id) cnt,
           round(avg(f.ps), 2) avg_ps,
           sum(f.sum_pay) sm
      from leaf f
     where f.sub is not null
     group by f.n, f.sub, case when f.n <= 3 then f.rfpm end, f.name
),
rws as (
    select n, sub, num, name, cnt, avg_ps, sm from parent
    union all
    select n, sub, num, name, cnt, avg_ps, sm from child
),
tot as (
    select sum(cnt) cnt, sum(sm) sm from parent
)
select num, name, cnt, avg_ps, sm, pct, bold
  from (
    select r.n * 100 + r.sub ord, r.num, r.name, r.cnt, r.avg_ps, r.sm,
           r.sm / nullif(decode(r.sub, 0, t.sm, p.sm), 0) pct,
           decode(r.sub, 0, 1, 0) bold
      from rws r, parent p, tot t
     where p.n = r.n
    union all
    select 9999, null, 'Общий итог', t.cnt, null, t.sm, 1, 1
      from tot t
  )
 order by ord, name
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    num_key='num', bold_key='bold',
)
