# -*- coding: utf-8 -*-
"""3196 - Назначение социальных выплат по всем видам выплат.

Перенос на общий рендерер (`util/xlsx_report.py`) в стиле группы 1000.
Источник - `sipr_maket_first_approve_2` (первое утверждение), вид выплаты -
первые четыре знака `rfpm_id`, область - `rfbn_id`, период - по
`date_approve`. Число - `count(sicp_id)` (страховые случаи, не уникальные
люди), как и раньше. Мужчины - sex = 1, женщины - sex = 0.

Формулы колонок собираются циклом по видам выплат.
"""
from db.connect import LOADER_PROFILE
from util.branch_kind import branch_kind
from util.xlsx_report import build_report, Col, Group

report_code = '3196'
report_name = ('Назначение социальных выплат по всем видам выплат за период '
               'с {period}')

# (ключ, заголовок группы) - порядок видов как в прежней версии
_KINDS = [
    ('01', 'По случаю потери кормильца'),
    ('02', 'По случаю утраты трудоспособности'),
    ('03', 'По случаю потери работы'),
    ('04', 'На случай потери дохода в связи с беременностью и родами, '
           'с усыновлением (удочерением) новорожденного ребенка (детей)'),
    ('05', 'На случай потери дохода в связи с уходом за ребенком '
           'по достижении им возраста 1 года'),
]


def _block(key):
    return [
        Col('Всего получателей, человек', f'cntall{key}', 'int', 14),
        Col('Мужчин', f'cnt{key}m', 'int', 10),
        Col('Женщин', f'cnt{key}w', 'int', 10),
        Col('Всего сумма выплат (тенге)', f'small{key}', 'money', 20),
        Col('Мужчин', f'sm{key}m', 'money', 20),
        Col('Женщин', f'sm{key}w', 'money', 20),
    ]


COLUMNS = [
    Col('Код региона', 'reg_id', 'center', 10),
    Col('Наименование региона', 'reg_name', 'text', 60),
    Col('Город/село', 'kind', 'center', 14),
    *[Group(title, _block(key)) for key, title in _KINDS],
    Group('Число СТРАХОВЫХ СЛУЧАЕВ', [
        Col('Всего получателей, человек', 'cntall', 'int', 14),
        Col('Мужчин', 'cntallm', 'int', 10),
        Col('Женщин', 'cntallw', 'int', 10),
    ]),
    Group('Сумма Выплат (тенге)', [
        Col('Всего сумма выплат (тенге)', 'sum_all', 'money', 20),
        Col('Мужчин', 'smallm', 'money', 20),
        Col('Женщин', 'smallw', 'money', 20),
    ]),
]


def _kind_select(key):
    c = f"rfpm = '07{key}'"
    return (f"       count(case when {c} then sicp_id end) cntall{key},\n"
            f"       count(case when {c} and sex = 1 then sicp_id end) cnt{key}m,\n"
            f"       count(case when {c} and sex = 0 then sicp_id end) cnt{key}w,\n"
            f"       sum(case when {c} then sum_all else 0 end) small{key},\n"
            f"       sum(case when {c} and sex = 1 then sum_all else 0 end) sm{key}m,\n"
            f"       sum(case when {c} and sex = 0 then sum_all else 0 end) sm{key}w")


_SELECT = ',\n'.join(_kind_select(key) for key, _ in _KINDS)

_KIND, _KIND_FROM, _KIND_WHERE, _KIND_GROUP = branch_kind('rb')

# :d_from / :d_to - границы периода по date_approve, :d_to исключительная.
STMT = f"""
select a.reg_id,
       rb.name reg_name,
       {_KIND} kind,
{_SELECT},
       count(sicp_id) cntall,
       count(case when sex = 1 then sicp_id end) cntallm,
       count(case when sex = 0 then sicp_id end) cntallw,
       sum(sum_all) sum_all,
       sum(case when sex = 1 then sum_all else 0 end) smallm,
       sum(case when sex = 0 then sum_all else 0 end) smallw
  from (select /*+ parallel(4) */
               s.sicp_id,
               substr(s.rfbn_id, 1, 4) reg_id,
               substr(s.rfpm_id, 1, 4) rfpm,
               s.sum_all,
               s.sex
          from sipr_maket_first_approve_2 s
         where s.date_approve >= :d_from
           and s.date_approve <  :d_to) a, rfbn_branch rb, {_KIND_FROM}
 where a.reg_id = rb.rfbn_id
   and {_KIND_WHERE}
 group by a.reg_id, rb.name, {_KIND_GROUP}
 order by a.reg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
