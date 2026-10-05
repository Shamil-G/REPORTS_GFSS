# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДАСОРП», отчёт 3201 (процедура social_debt_cur).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Справка о последней дате уплаты СО: платёжные документы работодателя по
КНП 012 (социальные отчисления) и 017 (пеня), по дате платежа, с числом
участников.

Источник - `pmpd_pay_doc` + `pmdl_doc_list` (по `mhmh_id`), отбор по `p_rnn`
из двух параметров формы - РНН и БИН/ИИН (`in (v_BIN_IIN, v_RNN)`): можно
указать любой из них либо оба. Группировка - по КНП, дате платежа, РНН и
названию плательщика: сумма (`sum(pay_sum)`) и число разных `sicid`.
Сортировка по дате платежа, свежие сверху.

Процедура в AIS написана на отдельном пакете `rep_web` (не `rep`) - логика
та же. Название дословно (`<b><h3>` и `<br>` оригинала не переносятся);
подпись «Дата и время создания справки» заменена общей датой формирования
в шапке листа.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3201'
report_name = 'Справка о последней дате уплаты СО'

COLUMNS = [
    Col('Дата последней уплаты', 'last_pay_date', 'date', 18),
    Col('КНП', 'knp', 'center', 8),
    Col('РНН', 'p_rnn', 'center', 16),
    Col('Наименование плательщика', 'p_name', 'text', 50),
    Col('Сумма соц. отчислений', 'doc_sum', 'money', 20),
    Col('Количество участников', 'cnt', 'int', 16),
]

# :rnn и :bin_iin - параметры формы; пустое значение ни с чем не совпадёт.
STMT = """
select last_pay_date,
       knp,
       p_rnn,
       p_name,
       sum(pay_sum) doc_sum,
       count(distinct sicid) cnt
  from (select pd.cipher_id_knp knp, pd.p_name,
               pd.p_rnn, dl.pay_sum,
               dl.sicid, pd.pay_date last_pay_date
          from pmpd_pay_doc pd, pmdl_doc_list dl
         where pd.mhmh_id = dl.mhmh_id
           and pd.p_rnn in (:bin_iin, :rnn)
           and pd.cipher_id_knp in ('012', '017'))
 group by knp, last_pay_date, p_rnn, p_name
 order by last_pay_date desc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE,
)
