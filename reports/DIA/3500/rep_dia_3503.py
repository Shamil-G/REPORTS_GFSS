# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ЕСП», отчёт 3503 (процедура REP_R_3503).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Отчёт о сторнированных суммах единого совокупного платежа (ЕСП) в разрезе
видов ошибок: число платежей, число человек и сумма по коду ошибки.

Источник - `pmpd_pay_doc`: платёжные документы со статусом сторно
(`tmst_id = '6'`) и КНП 183 за период по `pay_date`. В оригинале по каждому
платежу число людей берётся скалярным подзапросом по `pmdl_doc_list_s`
(`count(unique l.sicid)` по `mhmh_id`), затем всё группируется по коду ошибки.
Подзапрос оставлен скалярным: он возвращает одну строку на платёж, а
соединение с таблицей людей размножило бы суммы платежа.

`tmst_id = '6'` сравнивается со строкой, как в оригинале. Подсказка
`use_nl (pd m)` ссылается на несуществующий псевдоним `m` и Oracle её
игнорирует - не переносится. Название дословно.

Таблицы `pmdl_doc_list_s` и `pmpd_pay_doc` (боевые схемы) в тестовой reports_test
доступны не все: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3503'
report_name = ('Отчет о сторнированных суммах единого совокупного платежа в '
               'разрезе видов ошибок с {period} года')

COLUMNS = [
    Col('Код ошибки', 'rfem_id', 'center', 14),
    Col('Наименование ошибки', 'doc_err', 'text', 50),
    Col('Количество платежей', 'cnt_plat', 'int', 16),
    Col('Количество человек', 'cnt_chel', 'int', 16),
    Col('Сумма, тенге', 'sm', 'money', 20),
]

# :d_from / :d_to - период из формы по pay_date, :d_to исключительная.
STMT = """
select rfem_id, doc_err, count(mhmh_id) cnt_plat, sum(cnt_chel) cnt_chel,
       sum(sm) sm
  from (select pd.rfem_id,
               pd.doc_err,
               pd.mhmh_id,
               (select count(unique l.sicid)
                  from pmdl_doc_list_s l
                 where l.mhmh_id = pd.mhmh_id) cnt_chel,
               sum(pd.pay_sum) sm
          from pmpd_pay_doc pd
         where pd.pay_date >= :d_from
           and pd.pay_date <  :d_to
           and pd.tmst_id = '6'
           and pd.cipher_id_knp = '183'
         group by pd.rfem_id, pd.doc_err, pd.mhmh_id)
 group by rfem_id, doc_err
 order by 1
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
