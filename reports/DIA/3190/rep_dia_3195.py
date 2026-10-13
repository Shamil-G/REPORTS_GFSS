# -*- coding: utf-8 -*-
"""3195 - Получатели СВ по уходу за ребенком.

Перенос на общий рендерер (`util/xlsx_report.py`) в стиле группы 1000.
Вид выплаты 0705; номер ребёнка - последние два знака `rfpm_id` (01..04),
так что «до года» (070500NN) и «до полутора лет» (070501NN) попадают в одну
колонку, как и раньше. Область - по самому свежему документу получателя,
суммы всех его документов за период относятся на неё и на его последний код.
Мужчины - sex = 1, женщины - sex = 0.

Исправлено против прежней версии (формулы писались вручную по 20 раз):
  - у третьего ребёнка женщины считались по `rfpm = '03'` вместо
    `substr(rfpm, 7) = '03'` - всегда ноль;
  - у четвёртого ребёнка суммы мужчин и женщин были поменяны местами.
Теперь все колонки собираются циклом из одного шаблона.

Период - произвольные даты «с .. по»; `pncp_date` без времени, поэтому прежнее
`<= :dt_to` равно `< :d_to`.
"""
from db.connect import LOADER_PROFILE
from util.branch_kind import branch_kind
from util.xlsx_report import build_report, Col, Group

report_code = '3195'
report_name = ('Получатели социальных выплат по уходу за ребенком за период '
               'с {period}')

# (ключ = последние два знака rfpm_id, заголовок группы)
_CHILDREN = [
    ('01', 'Первым ребенком'),
    ('02', 'Вторым ребенком'),
    ('03', 'Третьим ребенком'),
    ('04', 'Четвертым и более ребенком'),
]


def _block(key):
    return [
        Col('Мужчины', f'cnt{key}_m', 'int', 10),
        Col('Сумма, мужчинам', f'sum{key}_m', 'money', 20),
        Col('Женщины', f'cnt{key}_w', 'int', 10),
        Col('Сумма, женщинам', f'sum{key}_w', 'money', 20),
    ]


COLUMNS = [
    Col('Код региона', 'rfbn', 'center', 10),
    Col('Наименование региона', 'reg_name', 'text', 60),
    Col('Город/село', 'kind', 'center', 14),
    Group('По уходу за', [Group(title, _block(key))
                          for key, title in _CHILDREN]),
    Group('Всего', _block('a')),
]


def _agg(key, cond):
    out = []
    for suffix, sex in (('m', 1), ('w', 0)):
        c = f"substr(rfpm, 7) = '{key}' and " if cond else ''
        out.append(f"       count(distinct case when {c}sex = {sex} then pncd_id end) cnt{key}_{suffix},\n"
                   f"       sum(case when {c}sex = {sex} then sm else 0 end) sum{key}_{suffix}")
    return ',\n'.join(out)


_SELECT = ',\n'.join([_agg(key, True) for key, _ in _CHILDREN] + [_agg('a', False)])

_KIND, _KIND_FROM, _KIND_WHERE, _KIND_GROUP = branch_kind()

# :d_from / :d_to - границы периода по pncp_date, :d_to исключительная.
STMT = f"""
select t.rfbn,
       br.name reg_name,
       {_KIND} kind,
{_SELECT}
  from (select /*+ parallel(4) */
               d.pncd_id,
               d.pay_sum + d.sum_debt sm,
               first_value(substr(d.rfbn_id, 1, 4)) over (
                   partition by d.pncd_id order by d.pncp_date desc) rfbn,
               first_value(d.rfpm_id) over (
                   partition by d.pncd_id order by d.pncp_date desc) rfpm,
               p.sex
          from pnpd_document d, person p
         where d.pncd_id = p.sicid
           and d.pncp_date >= :d_from
           and d.pncp_date <  :d_to
           and d.rfpm_id like '0705%'
           and d.ridt_id in (4, 6, 7, 8)
           and d.status in (0, 1, 2, 3, 5, 7)
           and d.pnsp_id > 0) t, rfbn_branch br, {_KIND_FROM}
 where t.rfbn = br.rfbn_id
   and {_KIND_WHERE}
 group by t.rfbn, br.name, {_KIND_GROUP}
 order by t.rfbn
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
