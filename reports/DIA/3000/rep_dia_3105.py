# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3105 (процедура REP_R_3105).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Ведомость возвратов излишне (ошибочно) уплаченных социальных отчислений
и пени с даты по дату - по плательщикам, с платёжным поручением Фонда.

ВНИМАНИЕ: оригинал читает таблицы `test_sior_order_ret`,
`test_mhmh_gfss_gcvp`, `test_gfss_pay_doc`, `test_gfss_order_ret_list` -
в боевой схеме они с префиксом test_, как и написано в исходнике. Перенесено
буквально; нужна ли замена на рабочие `sior_order_ret` и т.д., решает
владелец отчёта (ДИА). В тестовой БД reports_test этих таблиц нет, на
данных отчёт не сверен.

Условие `gpd.state in (10, 20)` и `l.sum_gfss > 0` оставлено как в оригинале.
`trunc(gpd.swift_date) between` заменено на полуоткрытый интервал без trunc
(правило проекта): результат тот же, индекс не блокируется.

Ограничение оригинала на период (не больше 366 суток; начальная дата не
позже конечной) сохранено: max_days=366.

Подписи «Руководитель / Исполнитель» под таблицей не переносятся, дата
формирования стоит в шапке листа.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3105'
report_name = ('Ведомость возвратов излишне (ошибочно) уплаченных социальных '
               'отчислений и пени с {period} года')

COLUMNS = [
    Col('БИН', 'p_bin', 'center', 16),
    Col('Наименование плательщика', 'r_name', 'text', 50),
    Col('Сумма(в тенге)', 'pay_sum', 'money', 18),
    Group('Платежное поручение', [
        Col('Номер платежного поручения Фонда', 'doc_nmb', 'center', 22),
        Col('Дата платежного поручения Фонда', 'doc_date', 'date', 22),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select unique
       sor.p_bin,
       sor.p_name r_name,
       sum(l.sum_gfss) pay_sum,
       l.doc_nmb,
       l.doc_date
  from pmpd_pay_doc pd, test_sior_order_ret sor, test_mhmh_gfss_gcvp gg,
       test_gfss_pay_doc gpd, test_gfss_order_ret_list l
 where pd.mhmh_id = sor.mh_in
   and sor.sior_id = l.sior_id
   and sor.sior_id = gg.sior_id(+)
   and gg.mhmh_id = gpd.mhmh_id(+)
   and gpd.state in (10, 20)
   and l.sum_gfss > 0
   and gpd.swift_date >= :d_from
   and gpd.swift_date <  :d_to
 group by sor.p_bin, sor.p_name, l.doc_nmb, l.doc_date
 order by 1
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, max_days=366, totals=True,
)
