# -*- coding: utf-8 -*-
"""5005. Плательщики со снижением числа работников в 2 и более раза - по регионам и ВЭД.

Перенос SOCIAL_TENSION.report_5 (AIS 5005 «По регионам и ВЭД - предприятия со
снижением числа работников более 2 раз»). Расчёт - в `util/social_tension.py`.

Строка - область; в ней только плательщики со снижением на 50 % и более
(`perc >= 50`). «Всего»: число предприятий, численность в последнем месяце
(`sum(cnt05)`), СМЗ - средняя заработная плата по предприятиям с ненулевой
(`avg(zp05)` при `zp05 != 0`). Затем те же три показателя по каждой из 22
секций ОКЭД (A..U и ZZ «Без секции»). Область, где нет ни одного такого
плательщика, в отчёт не попадает.

Отличия от оригинала:
  - период выбирается в форме (см. 5001);
  - секция определяется по ОКЭД организации, а не по `OKED1510544`;
  - СМЗ по секции без предприятий в оригинале была 0 для A..S и пустой для
    T, U, ZZ (`nvl` стоял не везде); здесь везде 0;
  - название секции и её буква склеены в один заголовок «A. Сельское, ...»
    (в оригинале вложенные заголовки «A» -> «Сельское, ...» -> три колонки);
  - итогов нет (в оригинале `SetColSumTotal` закомментированы);
  - в оригинале в шапке `AddCol` не совпадала с данными (71 колонка заготовлена
    по другому отчёту) - использован состав колонок `SetPageHead` и курсора;
  - «Информация о количестве предприятий,  допустивших» - один пробел;
  - подписи под таблицей не переносятся (дата формирования - в шапке листа).
"""
from db.connect import LOADER_PROFILE
from util.social_tension import base_for, OBL_JOIN, OBL_NAME, SECTIONS, check_params
from util.xlsx_report import build_report, Col, Group

report_code = '5005'
report_name = ('Информация о количестве предприятий, допустивших снижение '
               'численности работников в 2 и более раза. III. В разрезе '
               'регионов и ВЭД за период с {date_from} по {date_to}')


def _cols(p):
    return [
        Col('кол-во пред. ед.', f'cnt_{p}', 'int', 11),
        Col('числ. чел.', f'sum_{p}', 'int', 11),
        Col('СМЗ (тенге)', f'avg_{p}', 'money', 14),
    ]


COLUMNS = [
    Col('Регионы', 'reg', 'text', 36),
    Group('Всего', _cols('all')),
    Group('в том числе:', [
        Group(f'{s}. {name}', _cols(s.lower())) for s, name in SECTIONS
    ]),
]


def _sect_sql(s):
    p = s.lower()
    return (f"count(case when c.sect = '{s}' then 1 end) cnt_{p},\n"
            f"           nvl(sum(case when c.sect = '{s}' then c.cnt05 end), 0) sum_{p},\n"
            f"           nvl(avg(case when c.sect = '{s}' and c.zp05 != 0 then c.zp05 end), 0) avg_{p}")


_SECT_SQL = ',\n           '.join(_sect_sql(s) for s, _ in SECTIONS)

def STMT(params):
    base = base_for(params, with_sect=True)
    return f"""
with {base.lstrip()},
agg as (
    select c.obl,
           count(*)     cnt_all,
           sum(c.cnt05) sum_all,
           avg(case when c.zp05 != 0 then c.zp05 end) avg_all,
           {_SECT_SQL}
      from calc c
     where c.perc >= 50
     group by c.obl
)
select {OBL_NAME} reg, a.cnt_all, a.sum_all, a.avg_all,
       {', '.join(f'a.cnt_{s.lower()}, a.sum_{s.lower()}, a.avg_{s.lower()}' for s, _ in SECTIONS)}
  from agg a, branch b
 where {OBL_JOIN}
 order by a.obl
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
)
