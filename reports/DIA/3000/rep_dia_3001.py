# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3001 (процедура refund_3001).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Ведомость возвратов излишне (ошибочно) уплаченных социальных отчислений
и пени за период с даты по дату.

Источник - `pmpd_pay_doc` (платёжные документы), в отборе только
доставленные (`tmst_id = 103`) по КНП 026 и 094 (`cipher_id_knp`).
Один документ - одна строка, группировки в оригинале нет.

Название - дословно из refund_3001 (теги `<b><h3>` не переносятся, их роль
берёт на себя фреймворк). Латинская «c» перед датой - как в оригинале.
Колонка «№ п/п» оригинала - сквозной номер, его печатает фреймворк.
Подписи «Руководитель / Исполнитель / дата и время создания» под таблицей
оригинала не переносятся: дата формирования стоит в шапке листа.

Граница периода: оригинал сравнивал `pay_date between v_first_date and
v_last_date`, то есть последние сутки периода попадали только по полуночи.
Здесь, как во всех переносимых отчётах, `>= :d_from and < :d_to`, где
:d_to - сутки после последней даты периода.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3001'
report_name = ('Ведомость возвратов излишне (ошибочно) уплаченных '
               'социальных отчислений и пени с {period} года')

COLUMNS = [
    Col('Наименование получателя', 'r_name', 'text', 50),
    Col('Сумма (в тенге)', 'pay_sum', 'money', 18),
    Group('Платежное поручение', [
        Col('Номер платежного поручения', 'doc_nmb', 'center', 20),
        Col('Дата платежного поручения', 'pay_date', 'date', 20),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select pd.r_name,
       pd.pay_sum,
       pd.doc_nmb,
       pd.pay_date
  from pmpd_pay_doc pd
 where pd.tmst_id = 103
   and pd.cipher_id_knp in ('026', '094')
   and pd.pay_date >= :d_from
   and pd.pay_date <  :d_to
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
