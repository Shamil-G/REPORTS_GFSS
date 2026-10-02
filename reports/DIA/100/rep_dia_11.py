# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 11 (процедура rep_nnn_11).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

«Еженедельные» оперативные сведения об обратившихся за назначением
социальных выплат по случаю потери работы (0703): по областям число лиц и
сумма (`sum_pay` файла) - за отчётный период, за предыдущие 7 суток и с начала
года по конец периода.

Источник - макеты двух поколений, `union all`: `sipr_payer_maket` +
`sifl_file_maket` (макеты не в состоянии 0) и `sipr_payer` + `sifl_file`
(состояния 12 и 13); дата обращения `date_address`. Число лиц -
`count(unique sifl_id)`. Предыдущий период: `[date_first - 7, date_first)`.

Проверка как в оригинале: обе даты в одном календарном году. Название
дословно, но лишняя кавычка после «г.» и двойной пробел в «случаю
потери работы» исправлены. Область - функция схемы SSWH `s_region_name`; итог - «Всего».

Таблицы `sipr_payer_maket`, `sifl_file_maket`, `sipr_payer`, `sifl_file` лежат в
схеме SSWH боевой БД, в тестовой reports_test недоступны: на данных отчёт не
сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group, parse_date

report_code = '11'
report_name = ('«Еженедельные» оперативные сведения об обратившихся с '
               '{date_from} по {date_to} за назначением социальных выплат из '
               'АО «ГФСС» по случаю потери работы по состоянию на '
               '{date_to} г.')


def _check(params):
    if (parse_date(params['date_first']).year
            != parse_date(params['date_second']).year):
        raise ValueError('Указанные даты периода находятся в разных '
                         'календарных годах!')


def _trio(title, n):
    return Group(title, [Col('Количество', f'cnt{n}', 'int', 14),
                         Col('Сумма', f'summa{n}', 'money', 20)])


COLUMNS = [
    Col('Наименование областей', 'name', 'text', 36),
    Group('Обратившиеся за назначением социальных выплат', [
        _trio('За отчетный период', 1),
        _trio('В предыдущем периоде', 2),
        _trio('С начала года', 3),
    ]),
]


def _src(sipr, sifl, state, n):
    """Один отбор макетов; n - номер периода (1 - отчётный, 2 - 7 суток до,
    3 - с начала года), state - условие на состояние."""
    cols = {1: ('sn.sifl_id sipt1, sn.sum_pay sum_pay1, null sipt2, 0 sum_pay2,'
                ' null sipt3, 0 sum_pay3'),
            2: ('null sipt1, 0 sum_pay1, sn.sifl_id sipt2, sn.sum_pay sum_pay2,'
                ' null sipt3, 0 sum_pay3'),
            3: ('null sipt1, 0 sum_pay1, null sipt2, 0 sum_pay2,'
                ' sn.sifl_id sipt3, sn.sum_pay sum_pay3')}[n]
    window = {1: 'fl.date_address >= :d_from and fl.date_address < :d_to',
              2: 'fl.date_address >= :d_from - 7 and fl.date_address < :d_from',
              3: 'fl.date_address >= :y_from and fl.date_address < :d_to'}[n]
    return (f"select /*+ first_rows */\n"
            f"       sn.rfbn_id, {cols}\n"
            f"  from {sipr} fl, {sifl} sn\n"
            f" where fl.sipr_id = sn.sipr_id\n"
            f"   and {window}\n"
            f"   and {state}\n"
            f"   and fl.rfpm_id like '0703%'")


_UNION = '\nunion all\n'.join(
    _src(sipr, sifl, state, n)
    for n in (1, 2, 3)
    for sipr, sifl, state in (
        ('sipr_payer_maket', 'sifl_file_maket', 'fl.state not in (0)'),
        ('sipr_payer', 'sifl_file', 'fl.state in (12, 13)')))

# :d_from / :d_to - период из формы, :d_to исключительная; :y_from - 1 января.
STMT = f"""
select case when reg is null then 'Всего' else s_region_name(reg) end name,
       cnt1, summa1, cnt2, summa2, cnt3, summa3
  from (select substr(d.rfbn_id, 1, 2) reg,
               count(unique d.sipt1) cnt1, sum(d.sum_pay1) summa1,
               count(unique d.sipt2) cnt2, sum(d.sum_pay2) summa2,
               count(unique d.sipt3) cnt3, sum(d.sum_pay3) summa3
          from ({_UNION}) d
         group by grouping sets (1, (substr(d.rfbn_id, 1, 2))))
 order by reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=_check,
)
