# -*- coding: utf-8 -*-
"""Форма 3 (внутренний код app_f3). Получатели и суммы СВур (уход за
ребёнком до 1 года, СВ 0705) в разрезе очерёдности детей.

Перенос REP_STAT_EXTEND.app_f3_spool + Rep_app_f3 (pck_utf8.sql,
13817-14064). Реестр: группа 2030, вызов app_f3_1m и аналоги по типам
периода 1-5 (без второго аргумента 'm'/'f' - у этого отчёта нет варианта
шапки вообще, Rep_app_f3 не принимает irepTp).

Устройство - как у app_32 (пилот): колонки "в отчетном периоде"/"с начала
года", срез по группе (здесь - очерёдность ребёнка 1-4, а не вид риска).
Источник и границы периода (:y_from/:d_to) - тот же приём, что в app_32.

Найденная и НЕ воспроизведённая ошибка оригинала: в Begin-блоке Rep_app_f3
(строки 14047-14059) для типа периода 1 заголовок ДОПИСЫВАЕТСЯ к
накопленному '{' || cSPTitle || ' ' (строка 14048), а для типов 2-5 -
ПЕРЕЗАПИСЫВАЕТСЯ целиком (':=' вместо 'p_PageHead || ...'), из-за чего для
квартала/полугодия/9 месяцев/года заголовок отчёта фактически ТЕРЯЕТ
название и открывающую фигурную скобку - остаётся только фраза с периодом.
Это похоже на настоящий баг вёрстки (не просто "неряшливый, но
воспроизводимый" текст), а не сознательную особенность, и воспроизводить
исчезновение названия для 4 из 5 типов периода означало бы намеренно
ломать отчёт. Заголовок здесь показывается всегда полностью, слова самой
подписи периода (кроме этого) скопированы дословно, включая двойной
пробел у "9 месяцев".

Строки фиксированы (1-4, "на N ребенка"/"на 4 и более ребенка") - не через
справочник, а как в оригинале, литералами (строки 14023-14028).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'F.3'
# cSPTitle дословно (строка 13921-13922).
report_name = ('Оперативная отчетность по количеству получателей и суммам '
               'СВур из ГФСС в разрезе очередности детей по состоянию на '
               '{period}')

# Период (Begin блок, строки 14049-14058): тип 1 без ", за" (как в
# default-шаблоне app_32), типы 2-5 - с ", за" и двойным пробелом у "9
# месяцев" (та же исходная конкатенация null/строк, что и в других
# семействах).
_period_label = make_period_label({
    1: '{Month} месяц {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за  9 месяцев {year} года ',
    5: ', за {year} год ',
})

_PERIOD = 'в отчетном периоде'
_YEAR = 'с начала года'

COLUMNS = [
    Col('№', 'num', 'text', 6),
    Col('Очередность детей', 'gr', 'text', 22),
    Group('Количество получателей, которым назначены СВур, чел.', [
        Col(_PERIOD, 'cnt_om', 'int'),
        Col(_YEAR,   'cnt_by', 'int'),
    ]),
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
# :y_from - начало года (колонки "с начала года").
# gr - последний символ rfpm_id (substr(rfpm_id,-1)) для СВур (0705),
# 1-4 - номер очерёдности ребёнка, "4" уже означает "4 и более" (как и в
# аналогичной кодировке app_39/app_40 - справочник кодов выплат сам
# определяет границу, доп. группировка не нужна). `sum_all > 0` - фильтр
# из оригинала (строка 13856).
STMT = """
with src as (
    select substr(s.rfpm_id, -1) gr,
           s.date_approve,
           s.sum_all
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0705'
       and s.sum_all > 0
       and s.date_approve >= :y_from
       and s.date_approve <  :d_to
),
agg as (
    select gr,
           count(case when date_approve >= :d_from then 1 end)     cnt_om,
           count(*)                                                cnt_by,
           sum(case when date_approve >= :d_from then sum_all end) sum_om,
           sum(sum_all)                                            sum_by
      from src
     group by gr
)
select v.ord                                     num,
       v.label                                   gr,
       nvl(a.cnt_om, 0)                          cnt_om,
       nvl(a.cnt_by, 0)                          cnt_by,
       nvl(a.sum_om, 0)                          sum_om,
       nvl(a.sum_by, 0)                          sum_by,
       case when nvl(a.cnt_om, 0) > 0
            then a.sum_om / a.cnt_om else 0 end   avg_om,
       case when nvl(a.cnt_by, 0) > 0
            then a.sum_by / a.cnt_by else 0 end   avg_by
  from (select 1 ord, '1' gr, 'на 1 ребенка'          label from dual union all
        select 2,     '2',   'на 2 ребенка'                 from dual union all
        select 3,     '3',   'на 3 ребенка'                 from dual union all
        select 4,     '4',   'на 4 и более ребенка'         from dual) v,
       agg a
 where a.gr(+) = v.gr
 order by v.ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
)
