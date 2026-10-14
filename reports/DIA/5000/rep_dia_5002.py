# -*- coding: utf-8 -*-
"""5002. Социальная напряженность, регионы (свод по районам).

Перенос SOCIAL_TENSION.report_2 (AIS 5002 «Свод по районам»). Расчёт - в
`util/social_tension.py`. То же, что 5001, но строка - область и район
(отделение ГФСС), а не область: `group by name, reg`, где
`reg = rfbn_id || ' - ' || short_name`.

Код района - `cato_branch.rfbn_id` организации (решение Шамиля 13.10.2026),
наименование отделения - `branch.short_name` по этому коду: в КАТО у организации
запись на уровне населённого пункта, а в отчёте нужна сводка по отделению. Если
отделения нет в `branch`, показывается один код (в оригинале такие плательщики
выпадали из внутреннего соединения - здесь итог 5002 всегда равен итогу 5001).

Отличия от оригинала:
  - период выбирается в форме (см. 5001);
  - заголовок первых двух колонок - «Регион» и «Район», как в шапке
    `SetPageHead` (в `AddCol` они названы «Обл» и «Регион»);
  - названия областей - из КАТО (см. 5001), порядок строк - по коду области и
    района (в оригинале `order by 1, 2` по названиям);
  - «допустивших  снижение» (двойной пробел) в заголовке - один пробел;
  - итог по «Доле» не считается (в оригинале сумма процентов по строкам);
  - подписи под таблицей не переносятся (дата формирования - в шапке листа).
"""
from db.connect import LOADER_PROFILE
from util.social_tension import base_for, BANDS, UNKNOWN_NAME, UNKNOWN_RC, band_columns, band_sql, check_params
from util.xlsx_report import build_report, Col, Group

report_code = '5002'
report_name = 'Социальная напряженность, Регионы. На период с {date_from} по {date_to}'

COLUMNS = [
    Col('Регион', 'obl_name', 'text', 36),
    Col('Район', 'reg', 'text', 36),
    Group('Кол-во плательщиков, уплачивающих СО', [
        Col('Всего', 'cnt_all', 'int', 12),
        Col('В том числе со снижением', 'cnt_dis', 'int', 14),
    ]),
    Group('Кол-во плательщиков допустивших снижение участников СОСС', band_columns()),
    Col('Кол-во плательщиков уплачивающих СО, допустивших снижение '
        'участников СОСС от 50% и более (единиц)', 'cnt50', 'int', 20),
    Col('Доля плательщиков уплачивающих СО, допустивших снижение, к общему '
        'количеству плательщиков уплачивающих СО в регионе, %', 'dolya',
        'money', 20, total=False),
]

def STMT(params):
    base = base_for(params, with_sect=False)
    return f"""
with {base.lstrip()},
agg as (
    select c.obl, c.rc,
           count(*) cnt_all,
           count(case when c.perc > 0 then 1 end) cnt_dis,
           {band_sql('c')},
           count(case when c.perc >= 50 then 1 end) cnt50
      from calc c
     group by c.obl, c.rc
)
select nvl(ob.name, '{UNKNOWN_NAME}') obl_name,
       case when a.rc = '{UNKNOWN_RC}' then '{UNKNOWN_NAME}'
            else a.rc || nvl2(br.short_name, ' - ' || trim(br.short_name), '') end reg,
       a.cnt_all, a.cnt_dis,
       {', '.join(f'a.b{i}' for i in range(len(BANDS)))},
       a.cnt50,
       round(a.cnt50 / a.cnt_all * 100, 2) dolya
  from agg a, branch ob, branch br
 where ob.rfbn_id(+) = a.obl || '00'
   and br.rfbn_id(+) = a.rc
 order by a.obl, a.rc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
    totals=True,
)
