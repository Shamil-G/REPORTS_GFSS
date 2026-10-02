# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты для программы по возвратам», отчёт 409
(процедура Rep_nnn_409).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Отчёт по аннулированным платежам за период: исходящий платёж ГФСС и платёж,
которым сумма возвращена.

Источник - `gfss_pay_doc` (исходящие платежи в состояниях 6 и 7) с внешним
соединением к `gfss_annul_plat` (по `mhmh_gfss`) и далее к возвратному платежу
`pmpd_pay_doc` (по `ap.mhmh_021`). Платёж без возврата остаётся в списке с
пустыми колонками возврата. Дата исходящего платежа в периоде.

В оригинале после колонки КНП исходящего платежа стояло `SetColSumTotal`
(без номера колонки - итог по последней добавленной, то есть по тексту КНП),
поэтому итоговой строки с суммами в отчёте не было. Итоги здесь не
печатаются.

Шапка - из `SetPageHead`: группы «Исходящий платеж» и «Возвращено платежом»
по четыре колонки. «аннулированным» и остальные тексты дословно.

Таблицы `gfss_pay_doc`, `gfss_annul_plat` лежат в схеме SSWH боевой БД, в
тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '409'
report_name = ('Отчёт по аннулированным платежам\n'
               'с {date_from} по {date_to}')

COLUMNS = [
    Group('Исходящий платеж', [
        Col('Дата', 'date_out', 'date', 14),
        Col('Номер', 'nmb_out', 'center', 14),
        Col('Сумма', 'sum_out', 'money', 18),
        Col('КНП', 'knp_out', 'center', 8),
    ]),
    Group('Возвращено платежом', [
        Col('Дата', 'date_ret', 'date', 14),
        Col('Номер', 'nmb_ret', 'center', 14),
        Col('Сумма', 'sum_ret', 'money', 18),
        Col('КНП', 'knp_ret', 'center', 8),
    ]),
]

# :d_from / :d_to - период из формы по pay_date, :d_to исключительная.
STMT = """
select pd.pay_date date_out, pd.doc_nmb nmb_out, pd.pay_sum sum_out,
       pd.cipher_id_knp knp_out,
       rd.pay_date date_ret, rd.doc_nmb nmb_ret, rd.pay_sum sum_ret,
       rd.cipher_id_knp knp_ret
  from gfss_pay_doc pd, gfss_annul_plat ap, pmpd_pay_doc rd
 where pd.pay_date >= :d_from
   and pd.pay_date <  :d_to
   and pd.state in (6, 7)
   and pd.mhmh_id = ap.mhmh_gfss(+)
   and ap.mhmh_021 = rd.mhmh_id(+)
 order by pd.pay_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
