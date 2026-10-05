# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДСР», отчёт 3401 (процедура REP_R_3401).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о составе участников СОСС, за которых уплачивались СО от нескольких
работодателей: по регионам число участников и сумма отчислений в зависимости
от числа работодателей (1, 2, 3, 4, 5, 6 и более).

Источник - `si_member_2` (КНП 012, окна дат как в F3 REP_MINTRUD:
`pay_date_gfss` в периоде, `pay_date` на месяц шире слева). Работодатель -
`p_rnn`; число работодателей участника - `count(unique p_rnn)`. Регион
участника - по организации (`rfrr_id_region`) его ПОСЛЕДНЕГО по дате
поступления работодателя: справочник читается по типу `R` (последний платёж
до 01.01.2013) или `I` и по `last_rnn`; «00» и не найденное -> «ZZ»
(«Не определена»). Название региона - `rfbn_branch`.

В `sum(case ... end)` по числу участников нет `else 0` (в оригинале):
регион без участников данной группы даёт пустую ячейку, итог при этом
суммирует как ноль. Опечатка оригинала `else 0end` исправлена на `else 0 end`
(тот же смысл).

Название дословно, но «с» перед датой кириллическая (в оригинале латинская «c»). Итоги по всем колонкам
(`SetColSumTotal(3..14)`).

`rfrr_id_region` в тестовой reports_test недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3401'
report_name = ('Сведения о составе участников СОСС, за которых уплачивались '
               'СО от нескольких работодателей с {period} года')


def _pair(title, n):
    return Group(title, [Col('Количество участников', f'c{n}', 'int', 16),
                         Col('Сумма', f's{n}', 'money', 20)])


COLUMNS = [
    Col('Регион', 'name', 'text', 36),
    _pair('От 1 работодателя', 1),
    _pair('От 2 работодателей', 2),
    _pair('От 3 работодателей', 3),
    _pair('От 4 работодателей', 4),
    _pair('От 5 работодателей', 5),
    _pair('От 6 работодателей и более', 6),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
select /*+parallel(4)*/
       nvl(br.rfbn_id, 'ZZ') rfbn_id,
       nvl(br.name, 'Не определена') name,
       sum(case when c = 1 then 1 end) c1,
       sum(case when c = 1 then sm else 0 end) s1,
       sum(case when c = 2 then 1 end) c2,
       sum(case when c = 2 then sm else 0 end) s2,
       sum(case when c = 3 then 1 end) c3,
       sum(case when c = 3 then sm else 0 end) s3,
       sum(case when c = 4 then 1 end) c4,
       sum(case when c = 4 then sm else 0 end) s4,
       sum(case when c = 5 then 1 end) c5,
       sum(case when c = 5 then sm else 0 end) s5,
       sum(case when c >= 6 then 1 end) c6,
       sum(case when c >= 6 then sm else 0 end) s6
  from (select nvl(nullif(r.rfrg_id, '00'), 'ZZ') rfbn_id,
               s.sicid,
               count(unique s.p_rnn) c,
               sum(s.sum_pay) sm
          from (select sm.sicid,
                       sm.sum_pay,
                       sm.p_rnn,
                       first_value(sm.p_rnn) over (
                           partition by sm.sicid order by sm.pay_date_gfss desc
                           rows between unbounded preceding and unbounded following) last_rnn,
                       first_value(sm.pay_date_gfss) over (
                           partition by sm.sicid order by sm.pay_date_gfss desc
                           rows between unbounded preceding and unbounded following) last_date
                  from si_member_2 sm
                 where sm.pay_date_gfss >= :d_from
                   and sm.pay_date_gfss <  :d_to
                   and sm.pay_date      >= add_months(:d_from, -1)
                   and sm.pay_date      <  :d_to
                   and sm.knp = '012') s,
               rfrr_id_region r
         where (case when s.last_date < date '2013-01-01' then 'R' else 'I' end) = r.typ(+)
           and s.last_rnn = r.id(+)
         group by nvl(nullif(r.rfrg_id, '00'), 'ZZ'), s.sicid) t,
       rfbn_branch br
 where t.rfbn_id || '00' = br.rfbn_id(+)
 group by br.rfbn_id, br.name
 order by br.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
