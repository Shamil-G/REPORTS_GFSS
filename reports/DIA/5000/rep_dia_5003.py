# -*- coding: utf-8 -*-
"""5003. Плательщики со снижением числа работников в 2 и более раза - по регионам.

Перенос SOCIAL_TENSION.report_3 (AIS 5003 «По регионам - предприятия со
снижением числа работников более 2 раз»). Расчёт - в `util/social_tension.py`.

Строка - область; в ней только плательщики, допустившие снижение на 50 % и
более (`perc >= 50`): число предприятий, численность работников в базовом
(`cnt04`) и в последнем (`cnt05`) месяце, разница `cnt04 - cnt05` (положительная
- снижение). Те же четыре показателя отдельно для МСБ (численность в базовом
месяце меньше 250) и крупных предприятий (250 и более). Область, где нет ни
одного такого плательщика, в отчёт не попадает (в оригинале `group by` по
отфильтрованным `perc >= 50`); если нет плательщиков одного из классов, суммы и
разница по нему пустые, а число предприятий - 0 (как `select sum(...)` без строк
и `select count(...)` в оригинале).

Отличия от оригинала:
  - период выбирается в форме (см. 5001);
  - названия областей - из КАТО, порядок строк - по коду области;
  - «доспустивших» -> «допустивших», «учатсников» -> «участников»;
  - подписи под таблицей не переносятся (дата формирования - в шапке листа).
"""
from db.connect import LOADER_PROFILE
from util.social_tension import BASE_NO_SECT as BASE, MSB_LIMIT, OBL_JOIN, OBL_NAME, check_params
from util.xlsx_report import build_report, Col, Group

report_code = '5003'
report_name = ('Информация о плательщиках социальных отчислений (со штатной '
               'численностью 50 и более человек), допустивших снижение '
               'количества работников в 2 и более раза с делением на '
               'предприятия малого, среднего и крупного бизнеса за период '
               'с {date_from} по {date_to}')


def _block(p, count_title):
    return [
        Col(count_title, f'{p}_cnt', 'int', 14),
        Col('Численность работников в предыдущ. месяце, чел.', f'{p}_04', 'int', 16),
        Col('Численность работников в отчет. месяце, чел.', f'{p}_05', 'int', 16),
        Col('Разница численности работников, чел.', f'{p}_d', 'int', 16),
    ]


COLUMNS = [
    Col('Наименование региона', 'reg', 'text', 36),
    Group('Кол-во плательщиков СО допустивших снижение численности '
          'участников СОСС от 50% и более', _block('a', 'Кол-во предприятий')),
    Group('в том числе', [
        Group('МСБ (численность работников от 50 до 250 чел.)',
              _block('m', 'Кол-во предприятий, ед.')),
        Group('Крупные предприятия (численность работников от 250 и более чел.)',
              _block('l', 'Кол-во предприятий, ед.')),
    ]),
]


def _cls(p, cond):
    """Четыре показателя по классу предприятий; пустой класс даёт null в суммах."""
    return (f"count(case when {cond} then 1 end) {p}_cnt,\n"
            f"           sum(case when {cond} then c.cnt04 end) {p}_04,\n"
            f"           sum(case when {cond} then c.cnt05 end) {p}_05,\n"
            f"           sum(case when {cond} then c.cnt04 end)"
            f" - sum(case when {cond} then c.cnt05 end) {p}_d")


STMT = f"""
with {BASE.lstrip()},
agg as (
    select c.obl,
           count(*)                    a_cnt,
           sum(c.cnt04)                a_04,
           sum(c.cnt05)                a_05,
           sum(c.cnt04) - sum(c.cnt05) a_d,
           {_cls('m', f'c.cnt04 < {MSB_LIMIT}')},
           {_cls('l', f'c.cnt04 >= {MSB_LIMIT}')}
      from calc c
     where c.perc >= 50
     group by c.obl
)
select {OBL_NAME} reg,
       a.a_cnt, a.a_04, a.a_05, a.a_d,
       a.m_cnt, a.m_04, a.m_05, a.m_d,
       a.l_cnt, a.l_04, a.l_05, a.l_d
  from agg a, branch b
 where {OBL_JOIN}
 order by a.obl
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
    totals=True,
)
