# -*- coding: utf-8 -*-
"""5006. Списочная часть предприятий (социальная напряженность).

Перенос SOCIAL_TENSION.report_6 (AIS 5006 «Список предприятий»). Расчёт - в
`util/social_tension.py`. Строка - плательщик (БИН/ИИН), все, у кого в базовом
месяце КНП 012 уплачен не менее чем за 50 участников (не только допустившие
снижение на 50 % и более): область, район (отделение), наименование,
среднее число работников, средняя заработная плата и сумма отчислений за
базовый (предыдущий) и последний (отчётный) месяцы, разница численности
(`cnt05 - cnt04`, отрицательная - снижение), процент снижения, секция и вид
экономической деятельности.

Район - `cato_branch.rfbn_id` организации и `branch.short_name` (см. 5002).
Секция - по ОКЭД организации, наименование - `s_oked_sect` («Без секции» при
отсутствии ОКЭД). Наименование плательщика - `rfon_organization.nm_ru`
(оригинал - `nk_minfin_iin`, мёртвый справочник).

Отличия от оригинала:
  - период выбирается в форме (см. 5001);
  - порядок строк - область, район, БИН (оригинал `order by a.name` - строки
    внутри области шли в произвольном порядке);
  - заголовок суммы отчислений - «5 % СО» из `AddCol` (в `SetPageHead` стоит
    устаревшее «3,5 %»); итоги не считаются (в оригинале `SetColSumTotal`
    закомментированы);
  - лишние пробелы в «Сумма перечисленных                3,5 % СО» убраны;
  - подписи под таблицей не переносятся (дата формирования - в шапке листа).
"""
from db.connect import LOADER_PROFILE
from util.social_tension import BASE, UNKNOWN_NAME, UNKNOWN_RC, check_params
from util.xlsx_report import build_report, Col, Group

report_code = '5006'
report_name = 'Списочная часть предприятий на период с {date_from} по {date_to}'


def _month(p):
    return [
        Col('кол-во раб. (чел)', f'cnt{p}', 'int', 12),
        Col('среднемесячная заработная плата', f'zp{p}', 'money', 16),
        Col('Сумма перечисленных 5 % СО', f'sm{p}', 'money', 16),
    ]


COLUMNS = [
    Col('Область', 'obl_name', 'text', 32),
    Col('Район', 'reg', 'text', 32),
    Col('БИН/ИИН', 'p_rnn', 'center', 16),
    Col('Наименование предприятия', 'nm', 'text', 60),
    Group('Среднее кол-во чел. за предыдущий месяц', _month('04')),
    Group('Среднее кол-во чел. за отчетный месяц', _month('05')),
    Col('Разница', 'razn', 'int', 11),
    Col('Процент', 'perc', 'money', 11),
    Col('Сектор', 'sect', 'center', 9),
    Col('Вид экономической деятельности', 'name_sect', 'text', 50),
]

STMT = f"""
with {BASE.lstrip()}
select nvl(ob.name, '{UNKNOWN_NAME}') obl_name,
       case when c.rc = '{UNKNOWN_RC}' then '{UNKNOWN_NAME}'
            else c.rc || nvl2(br.short_name, ' - ' || trim(br.short_name), '') end reg,
       c.p_rnn, c.nm,
       c.cnt04, c.zp04, c.sm04,
       c.cnt05, c.zp05, c.sm05,
       c.razn, c.perc, c.sect,
       nvl(trim(regexp_replace(so.name, '\\s+', ' ')), 'Без секции') name_sect
  from calc c, branch ob, branch br, s_oked_sect so
 where ob.rfbn_id(+) = c.obl || '00'
   and br.rfbn_id(+) = c.rc
   and so.sect(+) = c.sect
 order by c.obl, c.rc, c.p_rnn
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
)
