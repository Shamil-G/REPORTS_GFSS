# -*- coding: utf-8 -*-
"""3194 - Получатели СВ по беременности и родам.

Перенос на общий рендерер (`util/xlsx_report.py`) в стиле группы 1000.
Запрос и шапка - из прежней версии; формулы колонок повторялись по 5 раз
вручную, теперь собираются циклом.

Группы колонок (набор кодов `rfpm_id`, как в оригинале):
  1. 07040101                         - по беременности и родам;
  2. 07040102, 07040103..05           - в оригинале под заголовком «Доплата за
                                        осложненные роды» (включая 07040102,
                                        «на 2 и более детей»; заголовок сохранён);
  3. 07040201                         - по беременности и родам (СИЯП);
  4. 07040202..05                     - доплата (СИЯП);
  5. 07040301                         - усыновление (удочерение).

Исправлено против прежней версии:
  - «Средний размер». Было `сумма / получатели / месяцев_между + 1` - единица
    прибавлялась к результату, а не к числу месяцев. Теперь
    `сумма / получатели / (месяцев_между + 1)`, то есть деление на число
    календарных месяцев периода включительно. Нулевое число получателей даёт
    пустую ячейку (раньше - ORA-01476 на всём отчёте).
  - Итоги: прежний код оставлял пустыми колонки сумм, а складывал средние
    (сдвиг на одну колонку). Теперь суммируются получатели и суммы, средние
    не суммируются.
"""
from db.connect import LOADER_PROFILE
from util.branch_kind import branch_kind
from util.xlsx_report import build_report, Col, Group

report_code = '3194'
report_name = ('Получатели социальных выплат по беременности и родам и '
               'усыновлению (удочерению) за период с {period}')

# (ключ, заголовок, коды rfpm_id)
_GROUPS = [
    ('01', 'По беременности и родам', ('07040101',)),
    ('02', 'Доплата за осложненные роды',
     ('07040102', '07040103', '07040104', '07040105')),
    ('03', 'По беременности и родам (СИЯП)', ('07040201',)),
    ('04', 'Доплата за осложненные роды (СИЯП)',
     ('07040202', '07040203', '07040204', '07040205')),
    ('05', 'Усыновление (удочерение) ребенка', ('07040301',)),
]


def _block(key):
    return [
        Col('Количество, человек', f'cnt{key}', 'int', 13),
        Col('Сумма, тенге', f'sum{key}', 'money', 20),
        # средние не суммируются
        Col('Средний размер, тенге', f'avg{key}', 'money', 17, total=False),
    ]


COLUMNS = [
    Col('Код региона', 'rfbn', 'center', 10),
    Col('Наименование региона', 'reg_name', 'text', 60),
    Col('Город/село', 'kind', 'center', 14),
    Group('Виды выплат (СВбр)', [Group(title, _block(key))
                                 for key, title, _ in _GROUPS]),
    Group('Всего', _block('a')),
]

# число календарных месяцев периода включительно; :d_to исключительная
_MONTHS = "(months_between(trunc(:d_to - 1, 'MM'), trunc(:d_from, 'MM')) + 1)"


def _agg(key, cond):
    cnt = f"count(distinct {'case when ' + cond + ' then pncd_id end' if cond else 'pncd_id'})"
    sm = f"sum({'case when ' + cond + ' then sm end' if cond else 'sm'})"
    return (f"       {cnt} cnt{key},\n"
            f"       {sm} sum{key},\n"
            f"       round({sm} / nullif({cnt}, 0) / {_MONTHS}) avg{key}")


_SELECT = ',\n'.join(
    [_agg(key, 'rfpm_id in (' + ', '.join(f"'{c}'" for c in codes) + ')')
     for key, _, codes in _GROUPS] + [_agg('a', None)])

_KIND, _KIND_FROM, _KIND_WHERE, _KIND_GROUP = branch_kind()

# :d_from / :d_to - границы периода по pncp_date, :d_to исключительная.
STMT = f"""
select t.rfbn_id rfbn,
       br.name reg_name,
       {_KIND} kind,
{_SELECT}
  from (select /*+ parallel(4) */
               d.pncd_id,
               substr(d.rfbn_id, 1, 4) rfbn_id,
               d.rfpm_id,
               d.pay_sum + d.sum_debt sm
          from pnpd_document d
         where d.pncp_date >= :d_from
           and d.pncp_date <  :d_to
           and d.rfpm_id like '0704%'
           and d.ridt_id in (4, 6, 7, 8)
           and d.status in (0, 1, 2, 3, 5, 7)
           and d.pnsp_id > 0) t, rfbn_branch br, {_KIND_FROM}
 where t.rfbn_id = br.rfbn_id
   and {_KIND_WHERE}
 group by t.rfbn_id, br.name, {_KIND_GROUP}
 order by t.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
