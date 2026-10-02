# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ЕСП», отчёт 3505 (процедура REP_R_3505).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Участники системы социального страхования, одновременно уплачивающие ЕСП,
за период: для каждого человека, за которого платили ЕСП (платёж с признаком
`*ESP*`), - суммы ЕСП и суммы обычных социальных отчислений за те же периоды
(месяцы) от работодателей.

В оригинале процедура строила три рабочие таблицы (`drop table` / `create
table as select` / `create index` / `analyze index`, ошибки глотались) и
читала их. Приложение отчётов только читает БД, поэтому цепочка таблиц
заменена цепочкой `with`, выборка каждой - та же:
  esp - платёжные документы ЕСП: КНП 012, `tmst_id = 5`, признак
        `substr(doc_assign, 1, 5) = '*ESP*'`, `pay_date` в периоде и не
        раньше 01.01.2019 (`pmpd_pay_doc_esp_tmp`);
  e   - строки списков этих платежей по людям (`pmdl_doc_list_s`,
        `pmdl_doc_list_esp_tmp`);
  so  - платежи тех же людей за те же периоды, не из ЕСП-документов
        (`pmdl_doc_list_s` + `pmpd_pay_doc_s`, КНП 012, `tmst_id = 5`; период
        строки - свой либо документа, `pmdl_doc_list_from_esp_tmp`).
Итоговая выборка: сумма СО по (человек, период, БИН работодателя) против суммы
ЕСП по (человек, период); регион и отделение - по `person.branchid`
и справочнику `branch`. Сортировка по периоду и ФИО.

Опечатка оригинала в заголовке «намиенование» исправлена на «наименование». Итоги по колонкам «Сумма ЕСП»
и «Сумма СО» (`SetColSumTotal(8, 9)`). Название дословно.

Таблицы `pmdl_doc_list_s`, `pmpd_pay_doc_s` лежат в схеме SSWH боевой БД, в
тестовой reports_test недоступны: на данных отчёт не сверен. Эта выборка
может быть тяжёлой (в оригинале для неё строились индексы); при проблемах
со временем её надо переносить на материализованную промежуточную таблицу.

Связь с `person` - по `person.iin`: в оригинале `c.iin = p.rn`, но в `person` сейчас
колонка `iin` (подтверждено Шамилем 02.10.2026). Оригинал с `rn` давно не
выполняется (запрос динамический, ошибка глоталась): отчёт мог не использоваться
год-два, стоит подтвердить, нужен ли он.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3505'
report_name = ('Участники системы социального страхования и одновременно '
               'уплачивающие ЕСП за период с {period} года')

COLUMNS = [
    Col('Код региона', 'branchid', 'center', 10),
    Col('Регион', 'short_name', 'text', 30),
    Col('Фамилия', 'lastname', 'text', 22),
    Col('Имя', 'firstname', 'text', 20),
    Col('Отчество', 'middlename', 'text', 22),
    Col('ИИН', 'iin', 'center', 16),
    Col('Период', 'period', 'center', 10),
    Col('Сумма ЕСП', 'sum_pay_esp', 'money', 16),
    Col('Сумма СО', 'sum_pay_so', 'money', 16),
    Col('БИН СО', 'bin', 'center', 16),
    Col('наименование', 'p_name', 'text', 40),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
with esp as (
    select pd.mhmh_id, pd.p_rnn, pd.pay_sum, pd.period, pd.p_name
      from pmpd_pay_doc pd
     where pd.pay_date >= date '2019-01-01'
       and pd.pay_date >= :d_from
       and pd.pay_date <  :d_to
       and substr(pd.doc_assign, 1, 5) = '*ESP*'
       and pd.cipher_id_knp = '012'
       and pd.tmst_id = 5
),
e as (
    select dl.mhmh_id, dl.rnn, dl.pay_sum, dl.period
      from esp, pmdl_doc_list_s dl
     where dl.mhmh_id = esp.mhmh_id
       and dl.pay_date >= date '2019-01-01'
),
so as (
    select dl2.mhmh_id, dl2.rnn,
           case when dl2.period is not null then dl2.period else pd2.period end period,
           dl2.pay_sum, pd2.p_rnn bin
      from e, pmdl_doc_list_s dl2, pmpd_pay_doc_s pd2
     where dl2.pay_date >= date '2019-01-01'
       and e.period = case when dl2.period is not null then dl2.period else pd2.period end
       and dl2.pay_date >= :d_from
       and dl2.pay_date <  :d_to
       and dl2.mhmh_id not in (select mhmh_id from esp)
       and dl2.rnn = e.rnn
       and pd2.mhmh_id = dl2.mhmh_id
       and pd2.cipher_id_knp = '012'
       and pd2.tmst_id = 5
)
select p.branchid,
       b.short_name,
       p.lastname,
       p.firstname,
       p.middlename,
       c.iin,
       c.period,
       c.sum_pay_esp,
       c.sum_pay_so,
       c.bin,
       c.p_name
  from (select b2.iin, b2.period, b2.sum_pay_esp, a.sum_pay_so, a.bin, a.p_name
          from (select so.bin,
                       so.rnn,
                       pd.p_name,
                       so.period,
                       sum(so.pay_sum) as sum_pay_so
                  from so, pmpd_pay_doc pd
                 where pd.mhmh_id = so.mhmh_id
                   and pd.pay_date >= :d_from
                   and pd.pay_date <  :d_to
                 group by so.rnn, so.period, so.bin, pd.p_name) a,
               (select e.period,
                       e.rnn iin,
                       sum(e.pay_sum) as sum_pay_esp
                  from e
                 group by e.rnn, e.period) b2
         where a.rnn = b2.iin
           and a.period = b2.period) c,
       branch b, person p
 where c.iin = p.iin
   and p.branchid = b.rfbn_id
 order by c.period, p.lastname, p.firstname, p.middlename
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
    # итоги только по двум денежным колонкам (SetColSumTotal(8), (9))
    totals=True,
)
