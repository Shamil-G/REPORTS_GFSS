# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Обороты и назначения», отчёт 6, часть 2 «Обороты»
(процедура P_ALL_INFO).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Вторая таблица `p_all_info`: «Информация участнику системы обязательного
социального страхования о состоянии и движении социальных отчислений».
Первая - назначения - в `rep_dia_6_1.py`; параметр, замена `rn` на `iin` и
правила доступа те же.

Отбор. Оригинал читал вьюшку `v_persdata13`, которая берёт человека из
`V_SICUnion` - а та из пакетной переменной `GetData.CurrSic`, заданной
вызовом `Getdata.Set_Sic` в начале процедуры. Пакетная переменная живёт в
одном сеансе БД и в веб-приложении, где соединения общие, ненадёжна, поэтому
выборка вьюшки (три `union all`) перенесена сюда, а `V_SICUnion` заменена
подзапросом: СИК человека и СИК, у которых он указан главным
(`p10_card.sicid_head`). Ветки:
  1. платежи КНП 012, 017 по 30.06.2006, состояния документа до 6;
  2. то же после 01.07.2006, все состояния кроме 103 (доставленные),
     сторнированные строки списка (`rfem_id`) - состояние 6
     «СТОРНИРОВАННЫЕ»;
  3. возвраты КНП 026, 094 в состоянии 103 (сумма в итог со знаком минус,
     «Пенсионный фонд» - получатель `r_name`).
Сортировка - по дате поступления.

Итог. Оригинал суммировал «Сумму платежа» для обработанных документов
(состояние 5, КНП не 032) и печатал в конце «Всего обработанных:». Здесь это
отдельная колонка «Из них обработанные» (сумма платежа для таких строк, иначе
0) с итогом внизу; жирный шрифт обработанных строк оригинала не повторяется.
`pf_name` пусто - «Гос.фонд социального страхования», как в оригинале.
Заголовки: «Рнн» -> «РНН».

Таблицы reports_test не все видит (часть в SSWH): проверено запуском на
данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '6-2'
report_name = ('Информация участнику системы обязательного социального '
               'страхования о состоянии и движении социальных отчислений\n'
               'ФИО: {fio}\n'
               'ИИН: {iin}')


def _check(params):
    if len(str(params.get('iin') or '').strip()) != 12:
        raise ValueError('Неверно указан ИИН!')


COLUMNS = [
    Col('Дата поступления', 'in_date', 'date', 14),
    Col('Дата отправки', 'out_date', 'date', 14),
    Col('№', 'doc_nmb', 'center', 12),
    Col('Дата документа', 'doc_date', 'date', 14),
    Col('КНП', 'knp', 'center', 8),
    Col('Отправитель', 'company', 'text', 36),
    Col('РНН', 'rnn', 'center', 16),
    Col('Пенсионный фонд', 'pf_name', 'text', 32),
    Col('Сумма', 'sum_doc', 'money', 16, total=False),
    Col('Сумма платежа', 'pay_sum', 'money', 16, total=False),
    Col('Статус', 'name', 'center', 18),
    Col('Период', 'period', 'center', 10),
    Col('Из них обработанные', 'sum_processed', 'money', 18),
]

TITLE_SQL = """
select initcap(p.lastname || ' ' || p.firstname || ' ' || p.middlename) fio
  from person p
 where p.iin = trim(:iin)
   and not exists (select 1 from notobor n where n.sicid = p.sicid)
"""

# :iin - ИИН человека.
STMT = """
with sics as (
    select c.sicid from p10_card c
     where c.sicid = (select sicid from person where iin = trim(:iin))
    union all
    select c.sicid from p10_card c
     where c.sicid_head = (select sicid from person where iin = trim(:iin))
),
l as (
    select p.sicid, p.pay_sum, p.mhmh_id, p.period, p.rfem_id
      from sics v, pmdl_doc_list p
     where p.sicid = v.sicid
),
t as (
    select d.pay_date in_date, d.pay_date out_date, d.doc_nmb, d.doc_date,
           d.cipher_id_knp knp, d.p_name company, d.p_rnn rnn,
           null pf_name, d.pay_sum sum_doc, l.pay_sum, d.tmst_id,
           s.name, d.period
      from l, pmpd_pay_doc d, tmst_state s
     where d.mhmh_id = l.mhmh_id
       and s.tmst_id < 7
       and d.tmst_id = s.tmst_id
       and d.cipher_id_knp in ('012', '017')
       and d.pay_date < date '2006-07-01'
    union all
    select d.pay_date, d.pay_date, d.doc_nmb, d.doc_date, d.cipher_id_knp,
           d.p_name, d.p_rnn, null, d.pay_sum, l.pay_sum,
           case when l.rfem_id is null then d.tmst_id else 6 end,
           case when l.rfem_id is null then s.name else 'СТОРНИРОВАННЫЕ' end,
           nvl(d.period, l.period)
      from l, pmpd_pay_doc d, tmst_state s
     where d.mhmh_id = l.mhmh_id
       and s.tmst_id <> 103
       and d.tmst_id = s.tmst_id(+)
       and d.cipher_id_knp in ('012', '017')
       and d.pay_date > date '2006-07-01'
    union all
    select d.pay_date, d.pay_date, d.doc_nmb, d.doc_date, d.cipher_id_knp,
           d.p_name, d.p_rnn, d.r_name, d.pay_sum, l.pay_sum, d.tmst_id,
           s.name, nvl(d.period, l.period)
      from l, pmpd_pay_doc d, tmst_state s
     where d.mhmh_id = l.mhmh_id
       and s.tmst_id = 103
       and d.tmst_id = s.tmst_id
       and d.cipher_id_knp in ('026', '094')
)
select in_date, out_date, doc_nmb, doc_date, knp, company, rnn,
       nvl(pf_name, 'Гос.фонд социального страхования') pf_name, sum_doc,
       pay_sum, lower(rtrim(name)) name, period,
       case when tmst_id = 5 and knp <> '032' then pay_sum else 0 end sum_processed
  from t
 order by in_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('iin',),
    title_sql=TITLE_SQL, totals=True,
    title_not_found='Участник не найден или доступ запрещён!',
)
