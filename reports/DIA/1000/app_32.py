# -*- coding: utf-8 -*-
"""Приложение 32. Оперативная отчётность по количеству получателей и суммам СВ.

Перенос REP_STAT_EXTEND.app_32_spool + Rep_app_32 (pck_utf8.sql, 1975-2481).
Реестр: группа 1320, вызов app_32_1m('m').

Отличия от оригинала, оба сознательные (см. docs/migration-plan.md):
  - итог по колонкам среднего считается из сумм и количеств, а не сложением
    средних, как делал Rep.SetColSumTotal (строки 2436-2439);
  - доступны все типы периода, а не только месячный: в PL/SQL была всего одна
    обёртка app_32_1m, это недоработка старой реализации.
Ветка шапки 'f' ("Форма № 4") не переносится: в реестре все вызовы идут с 'm'.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.32'
# Тексты дословно из исходника (cSPTitle - строка 2334, p_PageHead - 2419-2422):
# это официальная отчётность, формулировки согласованы и меняться не должны,
# включая написание без "ё". {period} подставляется как "Август месяц 2026 года" -
# в PL/SQL период был частью названия.
report_name = ('Оперативная отчетность по количеству получателей и суммам '
               'социальных выплат из ГФСС по состоянию на {period}')

# В оригинале подзаголовок всегда "в отчетном месяце": других периодов у отчёта
# не было. Слово согласуется с выбранным периодом - "в отчетном квартале" и т.д.
_PERIOD = 'в отчетном {period_word}'
_YEAR = 'с начала года'

COLUMNS = [
    Col('Вид риска', 'pay_name', 'text', 52),
    Group('Количество получателей, которым назначены СВ, чел.', [
        Col(_PERIOD, 'cnt_om', 'int', align='center'),
        Col(_YEAR,   'cnt_by', 'int', align='center'),
    ]),
    # Итог по средним считается как sum(сумма)/sum(количество), а не сложением
    # средних, как это делал Rep.SetColSumTotal. Сложение средних арифметически
    # бессмысленно; расхождение с эталоном в итоговой строке здесь ожидаемо
    # и согласовано 28.09.2026. Строки данных обязаны совпадать точно.
    Group('Средний размер назначенных социальных выплат, тенге', [
        Col(_PERIOD, 'avg_om', 'avg', 18, avg_of=('sum_om', 'cnt_om')),
        Col(_YEAR,   'avg_by', 'avg', 18, avg_of=('sum_by', 'cnt_by')),
    ]),
    Group('Сумма назначенных социальных выплат, тенге', [
        Col(_PERIOD, 'sum_om', 'money', 18),
        Col(_YEAR,   'sum_by', 'money', 18),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная;
# :y_from - начало года, от него считаются колонки "с начала года"
# (в PL/SQL это p_Dat1 := trunc(p_DatE,'YEAR')).
# Порядок строк задан явно через ord: он не алфавитный (rvids, строка 2358).
# 070403 отделяется от 0704, поэтому ветка на 6 символов идёт первой.
#
# pat - шаблон поиска названия в rfpm_payments, он НЕ равен коду группировки:
# в оригинале (rvids, строка 2358) "%" стоит только у 070403, у остальных
# like работает как равенство. Дописать "%" всем нельзя - справочник отдаст
# по нескольку строк на код (0702 -> "(30-60%)", "(60-80%)", ...), и каждая
# строка отчёта размножится с одними и теми же цифрами.
STMT = """
with src as (
    select case
             when substr(s.rfpm_id, 1, 6) = '070403' then '070403'
             when substr(s.rfpm_id, 1, 4) = '0701'   then '0701'
             when substr(s.rfpm_id, 1, 4) = '0702'   then '0702'
             when substr(s.rfpm_id, 1, 4) = '0703'   then '0703'
             when substr(s.rfpm_id, 1, 4) = '0704'   then '0704'
             when substr(s.rfpm_id, 1, 4) = '0705'   then '0705'
           end            rfpm,
           s.date_approve,
           s.sum_all
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) in ('0701','0702','0703','0704','0705')
       and s.date_approve >= :y_from
       and s.date_approve <  :d_to
),
agg as (
    select rfpm,
           count(case when date_approve >= :d_from then 1 end)     cnt_om,
           count(*)                                                cnt_by,
           sum(case when date_approve >= :d_from then sum_all end) sum_om,
           sum(sum_all)                                            sum_by
      from src
     group by rfpm
)
select p.name                                   pay_name,
       nvl(a.cnt_om, 0)                         cnt_om,
       nvl(a.cnt_by, 0)                         cnt_by,
       nvl(a.sum_om, 0)                         sum_om,
       nvl(a.sum_by, 0)                         sum_by,
       case when nvl(a.cnt_om, 0) > 0
            then a.sum_om / a.cnt_om else 0 end avg_om,
       case when nvl(a.cnt_by, 0) > 0
            then a.sum_by / a.cnt_by else 0 end avg_by
  from (select '0702'   rfpm, '0702'   pat, 1 ord from dual union all
        select '0701',         '0701',      2 from dual union all
        select '0703',         '0703',      3 from dual union all
        select '0704',         '0704',      4 from dual union all
        select '070403',       '070403%',   5 from dual union all
        select '0705',         '0705',      6 from dual) v,
       agg a,
       rfpm_payments p
 where a.rfpm(+) = v.rfpm
   and p.rfpm_id like v.pat
 order by v.ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
)
