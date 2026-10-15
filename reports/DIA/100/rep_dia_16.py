# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 16 (процедура REP_R_16).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатели СВпр (0703) с переплатой (`siop_overpay`): отделение, ФИО, ИИН,
дата рождения, дата назначения, размер ежемесячной выплаты, число месяцев, на
которые назначена выплата (последняя цифра кода вида), дата снятия с учёта в
качестве безработного, число месяцев, в течение которых должна
осуществляться выплата, фактически выплаченная сумма, сумма, которая должна
была выплачиваться, и излишне перечисленные суммы (на счёт получателя и ОПВ
в НПФ: ОПВ - `ceil(0,1 * переплата)`). Итоги - по денежным колонкам.

Процедура - `Pkg_OverPay.Rep_OverPay` (остальные процедуры пакета правят
данные и в отчёт не входят). Параметр: область (в оригинале код отделения; код
`XX00` брал первые две цифры, `00..` - всю республику; здесь список областей,
пусто - вся республика). Название - код и название области (`branch.name`,
в оригинале `branch_name`).

Причина невалидности процедуры в боевой БД - `ORA-00904: "PR.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `pr.iin`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `siop_overpay`, `sipr_payer` лежат в SSWH, reports_test их не видит: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '16'
report_name = 'Информация об излишне выплаченных суммах СВпр\nиз Государственного фонда социального страхования\nпо «{region}»'

TITLE_SQL = """
select nvl((select b.rfbn_id || ' - ' || b.name from branch b
             where b.rfbn_id = :rfbn_id || '00'), 'вся республика') region
  from dual
"""

COLUMNS = [
    Col('Отделение', 'rfbn', 'text', 30),
    Col('Ф.И.О.', 'fio', 'text', 36),
    Col('ИИН', 'iin', 'center', 16),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Дата назначения СВпр', 'appoint_date', 'date', 14),
    Col('Размер ежемесячной назначенной СВпр', 'sum_all', 'money', 18),
    Col('Кол-во месяцев, на которые назначена СВпр', 'gr_id', 'center', 14),
    Col('Дата снятия с учета в качестве безработного', 'unreg_date', 'date', 14),
    Col('Кол-во месяцев, в теч. которых должна осуществляться СВпр', 'cnt_mnt', 'int', 16, total=False),
    Col('Фактически выплаченная сумма СВпр, с учетом ОПВ (тенге)', 'sum_payed', 'money', 18),
    Col('Сумма СВпр, которая должна была выплачиваться, с учетом ОПВ (тенге)', 'sum_need', 'money', 18),
    Col('Сумма СВпр, излишне перечисленная на банковский счет получателя (тенге)', 'sum_over_wo_opv', 'money', 18),
    Col('Сумма ОПВ, излишне перечисленная в НПФ получателя (тенге)', 'sum_over_opv', 'money', 18),
]

# :rfbn_id - две цифры области (пусто - вся республика).
STMT = """
select p.rfbn_id || ' - ' || b.name rfbn,
       trim(pr.lastname || ' ' || pr.firstname || ' ' || pr.middlename) fio,
       pr.iin, pr.birthdate, p.appoint_date, p.sum_all,
       substr(p.rfpm_id, -1) gr_id, op.unreg_date, op.cnt_mnt, op.sum_payed,
       op.cnt_mnt * p.sum_all sum_need,
       op.sum_over - ceil(0.1 * op.sum_over) sum_over_wo_opv,
       ceil(0.1 * op.sum_over) sum_over_opv
  from sipr_payer p, siop_overpay op, person pr, branch b
 where p.rfbn_id like :rfbn_id || '%'
   and p.rfpm_id like '0703%'
   and p.sipr_id = op.sipr_id
   and p.sicp_id = pr.sicid
   and b.rfbn_id(+) = p.rfbn_id
 order by p.rfbn_id, pr.lastname, pr.firstname, pr.middlename
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, totals=True, title_sql=TITLE_SQL, title_params=(),
)
