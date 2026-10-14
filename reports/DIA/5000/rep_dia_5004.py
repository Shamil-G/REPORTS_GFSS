# -*- coding: utf-8 -*-
"""5004. Плательщики со снижением числа работников в 2 и более раза - по секциям ОКЭД.

Перенос SOCIAL_TENSION.report_4 (AIS 5004 «По секторам - предприятия со
снижением числа работников более 2 раз»). Расчёт - в `util/social_tension.py`.

То же, что 5003, но строка - секция ОКЭД (A..U, ZZ «Без секции»), а не
область; добавлено число предприятий «Всего». Секция - по первым двум знакам
`rfon_organization.oked` (см. util/social_tension.py), наименование - из
`s_oked_sect`. Секция, где нет ни одного плательщика со снижением на 50 % и
более, в отчёт не попадает (как в оригинале).

Отличия от оригинала:
  - период выбирается в форме (см. 5001);
  - секция определяется по ОКЭД организации, а не по `OKED1510544`;
  - в `AddCol` оригинала колонка «крупные предприятия разница, чел.» выведена
    дважды (11 и 12), в данных она одна; здесь одна, как в шапке `SetPageHead`;
  - «доспустивших» -> «допустивших», «предедущ.» -> «предыдущ.»;
  - подписи под таблицей не переносятся (дата формирования - в шапке листа).
"""
from db.connect import LOADER_PROFILE
from util.social_tension import base_for, MSB_LIMIT, check_params, normalize_params
from util.xlsx_report import build_report, Col, Group

report_code = '5004'
report_name = ('Информация о плательщиках социальных отчислений (со штатной '
               'численностью 50 и более человек), допустивших снижение '
               'количества работников в 2 и более раза по видам экономической '
               'деятельности за период с {date_from} по {date_to}')


def _block(p):
    return [
        Col('Кол-во пред. (ед.)', f'{p}_cnt', 'int', 14),
        Col('Численность работников в предыдущ. месяце, чел.', f'{p}_04', 'int', 16),
        Col('Численность работников в отчет. месяце, чел.', f'{p}_05', 'int', 16),
        Col('Разница численности работников, чел.', f'{p}_d', 'int', 16),
    ]


COLUMNS = [
    Col('Секция', 'sect', 'center', 9),
    Col('Наименование', 'name', 'text', 60),
    Group('Всего', [Col('Кол-во пред. (ед.)', 'a_cnt', 'int', 14)]),
    Group('в том числе', [
        Group('МСБ (численность работников от 50 до 250 чел.)', _block('m')),
        Group('Крупные предприятия (численность работников от 250 и более чел.)',
              _block('l')),
    ]),
]


def _cls(p, cond):
    return (f"count(case when {cond} then 1 end) {p}_cnt,\n"
            f"           sum(case when {cond} then c.cnt04 end) {p}_04,\n"
            f"           sum(case when {cond} then c.cnt05 end) {p}_05,\n"
            f"           sum(case when {cond} then c.cnt04 end)"
            f" - sum(case when {cond} then c.cnt05 end) {p}_d")


# Наименование секции - из s_oked_sect; пробелы схлопнуты (у D двойной, у N хвост CRLF).
def STMT(params):
    base = base_for(params, with_sect=True)
    return f"""
with {base.lstrip()},
agg as (
    select c.sect,
           count(*) a_cnt,
           {_cls('m', f'c.cnt04 < {MSB_LIMIT}')},
           {_cls('l', f'c.cnt04 >= {MSB_LIMIT}')}
      from calc c
     where c.perc >= 50
     group by c.sect
)
select a.sect,
       trim(regexp_replace(so.name, '\\s+', ' ')) name,
       a.a_cnt,
       a.m_cnt, a.m_04, a.m_05, a.m_d,
       a.l_cnt, a.l_04, a.l_05, a.l_d
  from agg a, s_oked_sect so
 where so.sect = a.sect
 order by a.sect
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
    totals=True,
)
