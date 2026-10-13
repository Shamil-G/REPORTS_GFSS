# -*- coding: utf-8 -*-
"""3191 - Получатели СВ по потере кормильца, утрате трудоспособности и потере работы.

Объединяет бывшие 3191 (утрата трудоспособности, 0702), 3192 (потеря кормильца,
0701) и 3193 (потеря работы, 0703): запросы совпадали построчно и отличались
только префиксом кода выплаты, а разрез внутри вида (степень утраты, число
иждивенцев, число месяцев) целиком сидит в 8-значном коде выплаты
(`rfpm_id`: 07020101..03, 07010101..04, 07030101..06; наименования -
`rfpm_payments`). Поэтому вместо трёх широких таблиц с разной шапкой - одна
длинная: строка на область и код выплаты, код и наименование выплаты -
отдельные колонки. Колонки «Всего» (по области, по всем кодам вида)
в длинной форме - сумма строк области; отдельными строками не выводятся.

Запрос оригинала не менялся по смыслу: за период берутся документы выплат
(`pnpd_document`), область и код выплаты - по самому свежему документу
получателя (`first_value ... order by pncp_date desc`), на него же относятся
суммы всех его документов за период. Вид выплаты (0701/0702/0703) входит в
`partition by`: раньше это обеспечивали три отдельных отчёта, и получатель,
у которого за период были документы двух видов, считался в каждом виде по
его последнему документу этого вида. Мужчины - sex = 1, женщины - sex = 0.

Период - произвольные даты «с .. по» (как у прежних отчётов), `pncp_date` без
времени, поэтому прежнее `<= :dt_to` равно `< :d_to`.
"""
from db.connect import LOADER_PROFILE
from util.branch_kind import branch_kind
from util.xlsx_report import build_report, Col

report_code = '3191'
report_name = ('Получатели социальных выплат по случаю потери кормильца, утраты '
               'трудоспособности и потери работы за период с {period}')

# Виды выплат (первые 4 знака rfpm_id): 0701 потеря кормильца,
# 0702 утрата трудоспособности, 0703 потеря работы.
_KINDS = ('0701', '0702', '0703')

COLUMNS = [
    Col('Код региона', 'rfbn', 'center', 10),
    Col('Наименование региона', 'reg_name', 'text', 60),
    Col('Город/село', 'kind', 'center', 14),
    Col('Код выплаты', 'rfpm', 'center', 12),
    Col('Наименование выплаты', 'pm_name', 'text', 48),
    Col('Мужчины', 'cnt_m', 'int', 10),
    Col('Сумма, мужчинам', 'sum_m', 'money', 20),
    Col('Женщины', 'cnt_w', 'int', 10),
    Col('Сумма, женщинам', 'sum_w', 'money', 20),
]

_KIND, _KIND_FROM, _KIND_WHERE, _KIND_GROUP = branch_kind()
_KINDS_IN = ', '.join(f"'{k}'" for k in _KINDS)

# :d_from / :d_to - границы периода по pncp_date, :d_to исключительная.
STMT = f"""
with src as (
    select /*+ parallel(4) */
           d.pncd_id,
           d.pay_sum + d.sum_debt sm,
           first_value(substr(d.rfbn_id, 1, 4)) over (
               partition by d.pncd_id, substr(d.rfpm_id, 1, 4)
               order by d.pncp_date desc) rfbn,
           first_value(d.rfpm_id) over (
               partition by d.pncd_id, substr(d.rfpm_id, 1, 4)
               order by d.pncp_date desc) rfpm,
           p.sex
      from pnpd_document d, person p
     where d.pncd_id = p.sicid
       and d.pncp_date >= :d_from
       and d.pncp_date <  :d_to
       and substr(d.rfpm_id, 1, 4) in ({_KINDS_IN})
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
)
select t.rfbn,
       br.name reg_name,
       {_KIND} kind,
       t.rfpm,
       pm.name pm_name,
       count(distinct case when t.sex = 1 then t.pncd_id end)  cnt_m,
       sum(case when t.sex = 1 then t.sm else 0 end)           sum_m,
       count(distinct case when t.sex = 0 then t.pncd_id end)  cnt_w,
       sum(case when t.sex = 0 then t.sm else 0 end)           sum_w
  from src t, rfbn_branch br, rfpm_payments pm, {_KIND_FROM}
 where t.rfbn = br.rfbn_id
   and pm.rfpm_id(+) = t.rfpm
   and {_KIND_WHERE}
 group by t.rfbn, br.name, {_KIND_GROUP}, t.rfpm, pm.name
 order by t.rfbn, t.rfpm
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
