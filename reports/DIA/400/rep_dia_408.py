# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты для программы по возвратам», отчёт 408
(процедура Rep_nnn_408).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Отчёт по возвращённым суммам плательщикам за период: по платёжным поручениям
ГФСС о возврате - плательщик, сумма и распоряжение ГЦВП.

Источник - `gfss_pay_doc` (платёжные поручения ГФСС в состояниях 3, 6, 7, 10),
`gfss_journal` (реквизиты распоряжения ГЦВП), связка с получателем по
`mhmh_gfss_gcvp` -> `sior_order_ret_orig` и суммы возврата по
`gfss_order_ret_list`. Строка - поручение и плательщик; сумма -
`sum(l.sum_gfss)`. Дата платёжного поручения в периоде.

«№ и дата плат. поручения ГФСС» - «№<номер> от <дата>»; «№ и дата распоряжения
ГЦВП» - «№<номер> от <дата>» из журнала; если номера нет, печатается только
«от <дата>» (так же, как `Trim` в оригинале). Итог - по колонке «Сумма (тенге)»
(`SetColSumTotal` стоит сразу за ней). Закомментированные варианты запроса
не переносятся.

Заголовок «Отчёт по возвращённым суммам плательщикам с ... по ...» в оригинале
был надгруппой над шапкой таблицы (в `SetPageHead`), здесь это название отчёта;
«возвращённым» с «ё» - как в оригинале.

Таблицы `gfss_*`, `mhmh_gfss_gcvp`, `sior_order_ret_orig` лежат в схеме SSWH
боевой БД, в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '408'
report_name = ('Отчёт по возвращённым суммам плательщикам\n'
               'с {date_from} по {date_to}')

COLUMNS = [
    Col('№ и дата плат. поручения ГФСС', 'pay_doc', 'text', 30),
    Col('Сумма (тенге)', 'pay_sum', 'money', 20),
    Col('Наименование плательщика', 'r_name', 'text', 50),
    Col('№ и дата распоряжения ГЦВП', 'ord', 'text', 28),
]

# :d_from / :d_to - период из формы по pay_date, :d_to исключительная.
STMT = """
select '№' || d.doc_nmb || ' от ' || to_char(d.pay_date, 'dd.mm.yyyy') pay_doc,
       sum(l.sum_gfss) pay_sum,
       o.p_name r_name,
       trim(case when j.gcvp_order_nom is not null then '№' || j.gcvp_order_nom end
            || case when j.gcvp_order_date is not null
                    then ' от ' || to_char(j.gcvp_order_date, 'dd.mm.yyyy') end) ord
  from gfss_pay_doc d, gfss_journal j, mhmh_gfss_gcvp m,
       sior_order_ret_orig o, gfss_order_ret_list l
 where d.pay_date >= :d_from
   and d.pay_date <  :d_to
   and d.state in (3, 6, 7, 10)
   and d.id_journ = j.id
   and d.mhmh_id = m.mhmh_id
   and m.sior_id = o.sior_id
   and d.mhmh_id = l.mhmh_id
   and o.sior_id = l.sior_id
 group by d.pay_date, o.p_name, d.doc_nmb, o.p_rnn, j.gcvp_order_nom,
          j.gcvp_order_date
 order by d.pay_date, d.doc_nmb
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
