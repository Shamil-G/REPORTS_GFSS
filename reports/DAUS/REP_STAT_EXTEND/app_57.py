# -*- coding: utf-8 -*-
"""Приложение 57. Динамика изменения количества иждивенцев получателей
социальных выплат на случай потери кормильца (0701).

Перенос REP_STAT_EXTEND.app_57_spool + Rep_app_57 (pck_utf8.sql, 12234-12515).
Протокол: 4 запуска, последний 04.2023. Вызов в вебе: группа 1570, id 1571
(только месячный). Источник оригинала - rptb_dinamika_detail_ext, замёрзшая на
01.12.2021.

Перестроено так же, как app_56 (подробности и обоснование - в его docstring и
dyn_matrix.py): строка - число иждивенцев на начало месяца, столбцы - в
какое число иждивенцев перешли, прибыло / убыло / на конец периода. Группа
получателя - последний символ rfpm_id (1, 2, 3, 4 и более). Требуется
подтверждение определений Шамилем и проверка формата rfpm_id.
Ветка шапки 'f' ("Форма № 28") не переносится.
"""
from db.connect import LOADER_PROFILE
from reports.DAUS.REP_STAT_EXTEND.dyn_matrix import matrix_stmt
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.57'
# cSPTitle || PH_per (строки 12368, 12510)
report_name = ('Динамика изменения количества иждивенцев получателей '
               'социальных выплат на случай потери кормильца, {period}')
_period_label = make_period_label({1: 'за {Month} {year} года '})

_ROWS = ['1 иждивенец', '2 иждивенца', '3 иждивенца', '4 и более иждивенца']

COLUMNS = [
    Col('Имеющееся количество иждивенцев', 'kat', 'text', 26),
    Col('Количество получателей СВпк на начало отчетного периода, человек',
        'cnt_old', 'int', 20),
    Group('Количество* получателей СВпк, человек', [
        Col(name, f'gr{k}', 'int', 14) for k, name in enumerate(_ROWS, start=1)
    ]),
    Col('Всего прибыло, человек', 'cnt_in', 'int', 14),
    Col('Всего убыло, человек', 'cnt_out', 'int', 14),
    Col('Количество получателей СВпк на конец отчетного периода, человек',
        'cnt_now', 'int', 20),
]

FOOTNOTE = ('* - численность получателей, у которых изменилось количество '
            'иждивенцев в отчетном  периоде.')

STMT = matrix_stmt('0701', _ROWS)

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
