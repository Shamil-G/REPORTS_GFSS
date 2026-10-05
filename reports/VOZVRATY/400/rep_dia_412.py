# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты для программы по возвратам», отчёт 412
(процедура Rep_nnn_412).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Реестр платёжных поручений, перечисленных за период (отчёт по возвращённым
суммам «для реестра»): дата и номер поручения, назначение платежа (по КНП),
КНП и сумма.

Источник - `gfss_pay_doc` (поручения в состояниях 1, 5, 8, 9 - см.
`GFSS_ORDER_STATE`) + `gfss_journal`; без отказов (`pay_sum > 0`). Назначение
платежа - «Возврат ошибочно перечисленных соц.отчислений» для КНП 026, иначе
«Возврат ошибочно перечисленной пени». КНП печатается с ведущим апострофом
(`'||knp`), чтобы Excel не превратил его в число - в xlsx это текстовая ячейка
без апострофа.

Отличия от оригинала: сумма в HTML печаталась строкой в формате
`99G999G999G999G990D90` с точкой, здесь это денежная ячейка (отображается с
пробелами и запятой, итог считается по ней: `SetColSumTotal` оригинала
стоит сразу после колонки «Сумма»). Подвал оригинала «Директор Департамента
финансов - Главный бухгалтер ____ Г.Гродер» не переносится: подпись
ставится в отпечатанной форме. Подзапрос `r_name` в оригинале выбирался, но
не выводился - не переносится.

Таблицы `gfss_pay_doc`, `gfss_journal` лежат в схеме SSWH боевой БД, в
тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '412'
report_name = ('Реестр платежных поручений, перечисленных\n'
               'с {date_from} по {date_to}')

COLUMNS = [
    Col('Дата и № платежного поручения', 'doc', 'text', 30),
    Col('Назначение платежа', 'knp_name', 'text', 50),
    Col('КНП', 'knp', 'center', 8),
    Col('Сумма (тенге)', 'pay_sum', 'money', 20),
]

# :d_from / :d_to - период из формы по pay_date, :d_to исключительная.
STMT = """
select '№' || d.doc_nmb || ' от ' || to_char(d.pay_date, 'dd.mm.yyyy') doc,
       case when d.cipher_id_knp = '026'
            then 'Возврат ошибочно перечисленных соц.отчислений'
            else 'Возврат ошибочно перечисленной пени' end knp_name,
       d.cipher_id_knp knp,
       d.pay_sum
  from gfss_pay_doc d, gfss_journal j
 where d.pay_date >= :d_from
   and d.pay_date <  :d_to
   and d.state in (1, 5, 8, 9)
   and d.id_journ = j.id
   and d.pay_sum > 0
 order by d.pay_date, d.doc_nmb
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
