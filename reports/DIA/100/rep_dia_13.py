# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 13 (процедура rep_r_13).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о назначенных социальных выплатах из АО «ГФСС» по случаю потери
работы (0703) по состоянию на месяц: по областям численность получателей,
которым назначена выплата в текущем месяце и с начала года, и из них - по
стажу участия (числу отчислений `count_donation`) в разбивке «в отчётном
месяце» / «с начала года».

Источник - `sipr_maket_first_approve`, дата назначения - `trunc(date_approve)`
(поле `appoint_date` внутреннего запроса), от 1 января до конца месяца.
Стаж: 6-11 отчислений - от 6 до 12 месяцев (право выплаты 1 месяц), 12-23, 24-35,
36 и больше. Последняя группа делится по виду: `07030106` - с правом выплаты 6
месяцев, остальные - 4 месяца (`rfpm_id != '07030106'`).

ОБРАТИТЕ ВНИМАНИЕ (как в оригинале): внешнее условие `count_donation >= 6`
отсекает людей со стажем менее 6 отчислений уже до подсчёта, поэтому в
«Численность получателей ... в текущем месяце» и «... с начала года»
попадают только они, а не все назначенные. Итоговая строка - «Всего»; область -
функция схемы SSWH `s_region_name`.

Название дословно; лишняя кавычка после «г.» и двойной пробел убраны, `<br>`
заменены пробелами.
Подпись «по состоянию на» - первое число месяца (параметр-дата оригинала).
Закомментированный в оригинале вариант по макетам двух поколений не
переносится.

`sipr_maket_first_approve` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import first_date_label
from util.xlsx_report import build_report, Col, Group

report_code = '13'
report_name = ('СВЕДЕНИЯ о назначенных социальных выплатах из АО «ГФСС» по '
               'случаю потери работы по состоянию на {period} г.')


def _gr(title, n):
    return Group(title, [Col('в отчетном месяце', f'gr{n}', 'int', 14),
                         Col('с начала года', f'gr{n}_1', 'int', 14)])


COLUMNS = [
    Col('Наименование областей', 'reg_n', 'text', 36),
    Col('Численность получателей, которым назначена социальная выплата в '
        'текущем месяце', 'cnt1', 'int', 22),
    Col('Численность получателей, которым назначена социальная выплата с '
        'начала года', 'cnt2', 'int', 22),
    Group('Из них со стажем участия:', [
        _gr('от 6 до 12 месяцев (с правом выплаты 1 месяц)', 1),
        _gr('от 12 до 24 месяцев (с правом выплаты 2 месяца)', 2),
        _gr('от 24 до 36 месяцев (с правом выплаты 3 месяца)', 3),
        _gr('свыше 36 месяцев (с правом выплаты 4 месяца)', 4),
        _gr('свыше 36 месяцев (с правом выплаты 6 месяцев)', 5),
    ]),
]


def _cnt(cond, in_month):
    """count(unique sicp_id) по условию; in_month - только отчётный месяц.
    cond=None - без условия по стажу (все, прошедшие внешний отбор >= 6)."""
    parts = [cond] if cond else []
    if in_month:
        parts.append('appoint_date >= :d_from and appoint_date < :d_to')
    if not parts:
        return 'count(unique sicp_id)'
    return ('count(unique (case when ' + ' and '.join(parts)
            + ' then sicp_id else null end))')


_ALL = None
_G1 = 'count_donation between 6 and 11'
_G2 = 'count_donation between 12 and 23'
_G3 = 'count_donation between 24 and 35'
_G4 = "count_donation >= 36 and rfpm_id != '07030106'"
_G5 = "count_donation >= 36 and rfpm_id = '07030106'"

_COLS = ',\n       '.join([
    f'{_cnt(_ALL, True)} cnt1',
    f'{_cnt(_ALL, False)} cnt2',
    f'{_cnt(_G1, True)} gr1', f'{_cnt(_G1, False)} gr1_1',
    f'{_cnt(_G2, True)} gr2', f'{_cnt(_G2, False)} gr2_1',
    f'{_cnt(_G3, True)} gr3', f'{_cnt(_G3, False)} gr3_1',
    f'{_cnt(_G4, True)} gr4', f'{_cnt(_G4, False)} gr4_1',
    f'{_cnt(_G5, True)} gr5', f'{_cnt(_G5, False)} gr5_1',
])

# :d_from / :d_to - границы месяца, :y_from - начало года.
STMT = f"""
select case when reg_n is null then 'Всего' else reg_n end reg_n,
       cnt1, cnt2, gr1, gr1_1, gr2, gr2_1, gr3, gr3_1, gr4, gr4_1, gr5, gr5_1
  from (select /*+ first_rows */
               substr(rfbn_id, 1, 2) reg,
               s_region_name(substr(rfbn_id, 1, 2)) reg_n,
       {_COLS}
          from (select /*+ first_rows */
                       f.rfbn_id, trunc(f.date_approve) appoint_date,
                       f.count_donation, f.sicp_id, f.rfpm_id
                  from sipr_maket_first_approve f
                 where f.date_approve >= :y_from
                   and f.date_approve <  :d_to
                   and f.rfpm_id like '0703%')
         where count_donation >= 6
         group by grouping sets (1, (substr(rfbn_id, 1, 2),
                                     s_region_name(substr(rfbn_id, 1, 2)))))
 order by reg nulls last
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=first_date_label,
)
