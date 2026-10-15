# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 601 (процедура rep_r_601).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Справка о произведенных выплатах по получателю: все документы выплаты человека
(по `pnpd_document`) с платёжным поручением, банком, счётом и типом
финансирования.

Параметр. В AIS получатель выбирался в окне поиска по картотеке и в процедуру
уходил внутренний номер `sicid`. Пользователю отчётов `sicid` неизвестен,
поэтому форма принимает ИИН (`person.iin`; в оригинале `rn`, такой колонки сейчас нет - оригинал давно не выполняется, отчёт мог не использоваться), номер человека берётся из `person`.
Если по ИИНу нет ровно одного человека - ошибка, как у `select ... into` оригинала.

Источник: `pnpd_document` + `pmpd_pay_doc` (внешнее соединение по `mhmh_id`) +
`rfds_doc_status` (название состояния). Сумма «Удержания по заявлению» -
подзапрос по истории удержаний (`pndh_deduct_history`, `pndp_deductpay_arc`,
`pndn_deduction_arc`, вид удержания 5). Тип выплаты, вид и банк - функции схемы
SSWH `ridt_name`, `payment_name`, `recipient_name` (как в оригинале). «Тип
финансирования» - по состоянию документа (список состояний и формулировки
дословно: «Чистое финансирование», «Ошибочное финансирование» и т.д.; для
состояний 9, 11-16, 18, 22-26 - название из `rfds_doc_status`). Итоги по колонкам «Сумма к
выплате», «Сумма 1 раздела», «Удержания по заявлению» (`SetColSumTotal` на
6-8-й колонках). Подсказка `rule` оптимизатору не переносится.

Шапка - из `SetPageHead`. В нём «(Платежка {Номер}{Дата}{Сумма}}» написано с
опечаткой (круглая скобка вместо фигурной); по смыслу это группа «Платежка»
из трёх колонок, так и выведено. В названии оригинала первой строкой шло
наименование филиала пользователя (`setup.branchname`); у веб-отчётов
филиала пользователя нет, строка не выводится. `&nbsp;` перед КНП и счётом
(защита от превращения в число) заменён текстовым форматом ячейки.

`pmpd_pay_doc`, `pndh_deduct_history`, `rfds_doc_status` и функции схемы SSWH в
тестовой reports_test недоступны не все: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '601'
report_name = ('СПРАВКА о произведенных выплатах по получателю\n'
               'Выдана на: {fio}')

COLUMNS = [
    Col('Код района', 'rfbn_id', 'center', 10),
    Col('Месяц выплаты', 'pncp_date', 'date', 14),
    Col('Тип выплаты', 'ridt_type', 'text', 22),
    Col('Вид выплаты', 'rfpm', 'text', 40),
    Col('Сумма к выплате', 'pay_sum', 'money', 16),
    Col('Сумма 1 раздела', 'sum_debt', 'money', 16),
    Col('Удержания по заявлению', 'sum_deduct_5', 'money', 16),
    Col('День выплаты', 'pay_date', 'date', 14),
    Col('Референс платежа', 'refer', 'center', 18),
    Col('КНП', 'knp', 'center', 8),
    Col('Наименование банка', 'co_name', 'text', 30),
    Col('Счет получателя', 'l_account', 'center', 24),
    Group('Платежка', [
        Col('Номер', 'doc_nmb', 'center', 14),
        Col('Дата', 'doc_date', 'date', 14),
        Col('Сумма', 'doc_pay_sum', 'money', 16, total=False),
    ]),
    Col('Тип финансирования', 'type_pay', 'text', 40),
]

# Реквизит в названии: ФИО и дата рождения получателя (обращение по ИИН).
TITLE_SQL = """
select lastname || ' ' || firstname || ' ' || middlename || ' '
       || to_char(birthdate, 'dd-mm-yyyy') fio
  from person
 where iin = :iin
"""

# :iin - ИИН получателя (форма); sicid находится в person.
STMT = """
select d.rfbn_id,
       d.pncp_date,
       ridt_name(d.ridt_id) ridt_type,
       (d.rfpm_id || '-' || payment_name(d.rfpm_id)) rfpm,
       d.pay_sum,
       nvl(d.sum_debt, 0) sum_debt,
       nvl((select sum(dp.sum_deduct)
              from pndh_deduct_history dh, pndp_deductpay_arc dp, pndn_deduction_arc dn
             where dh.act_month = d.pncp_date
               and dh.pnpt_id = d.source_id
               and d.ridt_id in (1, 6)
               and dh.pndp_id = dp.pndp_id and dh.pndp_actp = dp.actp_id
               and dh.pndn_id = dn.pndn_id and dh.pndn_actp = dn.actp_id
               and dn.rfdd_id = 5), 0) sum_deduct_5,
       p.pay_date,
       p.refer,
       d.knp,
       (case when d.ridt_id = 7 then 'НПФ согласно единого списка'
             else recipient_name(d.rfrc_id) end) co_name,
       d.l_account,
       p.doc_nmb,
       p.doc_date,
       p.pay_sum doc_pay_sum,
       (case when d.status in (6) then 'Выплачено повторно (через возврат) '
             when d.status in (1, 2) then 'Чистое финансирование '
             when d.status in (5) then 'На выплату сформировано распоряжение на возврат'
             when d.status in (4) then 'Профинансированный возврат'
             when d.status in (9, 11, 12, 13, 14, 15, 16, 18, 22, 23, 24, 25, 26) then ds.name
             when d.status in (3) then 'Ошибочное финансирование'
             else ' Чистое финансирование' end) type_pay
  from pnpd_document d, pmpd_pay_doc p, rfds_doc_status ds
 where d.status in (0, 1, 2, 3, 5, 4, 6, 7, 9, 11, 12, 13, 14, 15, 16, 18, 22, 23, 24, 25, 26)
   and d.mhmh_id = p.mhmh_id(+)
   and d.status = ds.status
   and d.pncd_id = (select p2.sicid from person p2 where p2.iin = :iin)
 order by d.pncp_date, p.pay_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, totals=True,
    title_sql=TITLE_SQL, title_not_found='Получатель не выбран!',
)
