# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3324 (процедура org_list_0706).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Список получателей выплат на период ЧП и на период карантина (виды 0706 и
0709) по работодателю: все выплаты тех работников, за кого организация (БИН)
платила в последние 13 месяцев.

В оригинале процедура сначала пересоздавала рабочую таблицу
`sicid_0706` (`drop table` + `create table as select unique dl.sicid ...`),
ошибки глотала (`when others then null`), и уже затем читала её. Отчёты
приложения читают БД только на чтение, а общая таблица на двоих
одновременно запущенных отчётов ещё и перетиралась бы, поэтому список
работников здесь - подзапрос `s` с тем же отбором:
`pmpd_pay_doc` + `pmdl_doc_list` по `p_rnn = :bin` за период от первого числа
месяца 13 месяцев назад до вчерашнего дня включительно.

Проверка БИНа как в оригинале: ровно 12 знаков, иначе «Введен неправильный
БИН!». Название дословно (`<br><br>` оригинала - пустая строка). Закомментированный
в оригинале вариант запроса не переносится.

Колонки - из `SetPageHead`. В `pnpd_document` ФИО и ИИН хранятся в самих
документах (`lastname`, `firstname`, `middlename`, `rnn`).

Таблицы `pmdl_doc_list`, `rfds_doc_status` и т.д. в тестовой reports_test
частично недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3324'
report_name = ('Список получателей выплат на период ЧП и на период '
               'карантина\n\nБИН: {bin}')

COLUMNS = [
    Col('Код района', 'rfbn_id', 'center', 10),
    Col('ФИО', 'fio', 'text', 40),
    Col('ИИН', 'rnn', 'center', 16),
    Col('КНП', 'knp', 'center', 8),
    Col('Сумма', 'all_sum', 'money', 16),
    Col('Дата назначения выплаты', 'appointdate', 'date', 14),
    Col('Дата утверждения', 'approvedate', 'date', 14),
    Col('Дата окончания выплаты', 'stopdate', 'date', 14),
    Col('Месяц выплаты', 'pncp_date', 'date', 14),
    Col('Статус', 'status', 'text', 36),
]


def _check(params):
    if len(str(params.get('bin') or '').strip()) != 12:
        raise ValueError('Введен неправильный БИН!')


STMT = """
with s as (
    select unique dl.sicid
      from pmpd_pay_doc pd, pmdl_doc_list dl
     where pd.p_rnn = trim(:bin)
       and pd.mhmh_id = dl.mhmh_id
       and pd.pay_date >= add_months(trunc(sysdate, 'MONTH'), -13)
       and pd.pay_date <  trunc(sysdate)
)
select d.rfbn_id,
       d.lastname || ' ' || d.firstname || ' ' || d.middlename fio,
       d.rnn,
       d.knp,
       d.pay_sum + d.sum_debt all_sum,
       pp.appointdate,
       pp.approvedate,
       pp.stopdate,
       d.pncp_date,
       d.status || ' - ' || st.name as status
  from s, pnpd_document d, pnpt_payment pp, rfds_doc_status st
 where d.pncd_id = s.sicid
   and d.source_id = pp.pnpt_id(+)
   and substr(d.rfpm_id, 1, 4) in ('0706', '0709')
   and st.status = d.status
 order by d.pncp_date, d.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('bin',),
)
