# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ЕСП», отчёт 3504 (процедура REP_R_3504).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о частоте уплаты ЕСП за период: сколько участников платили ЕСП
столько-то месяцев; из них - уплатившие платёж, соответствующий столице,
городам республиканского и областного значения, и платёж «других населённых
пунктов».

Источник - `si_member_2`, плательщик ЕСП, поступление в ГФСС в периоде.
По (участник, размер платежа) считается число разных месяцев платежей;
далее по числу месяцев - число участников и число тех, у кого платёж
в узком диапазоне размера: 612.4-612.8 (столица, города республиканского и
областного значения) и 306.1-306.5 (другие населённые пункты). Диапазоны
взяты из действующей версии оригинала (ранние значения 583-584 и 291-292 в
нём закомментированы). Это прямо зашитые в процедуру размеры платежа (50% и
25% МЗП соответствующего года), при смене МЗП их придётся править.

Итог печатается только по колонке «Всего кол-во участников»
(`SetColSumTotal(2)` в оригинале). Тип плательщика ЕСП - латинская «E»
вместо кириллической «Е» исходника (так он хранится в `si_member_2`, см.
коммит f54ac2e). Название дословно, но «с» перед датой кириллическая (в оригинале латинская «c»).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3504'
report_name = 'Сведения о частоте уплаты ЕСП за период с {period} года'

COLUMNS = [
    Col('Кол-во месяцев', 'cnt_mnth', 'center', 14),
    Col('Всего кол-во участников, чел.', 'cnt_sic', 'int', 20),
    Group('В том числе', [
        Col('В столице, городах республиканского и областного значения',
            'cnt_1', 'int', 30, total=False),
        Col('В других населенных пунктах', 'cnt_2', 'int', 22, total=False),
    ]),
]

# :d_from / :d_to - период из формы по pay_date_gfss, :d_to исключительная.
STMT = """
select cnt_mnth,
       count(unique sicid) cnt_sic,
       count(unique case when sum_pay between 612.4 and 612.8 then sicid else null end) cnt_1,
       count(unique case when sum_pay between 306.1 and 306.5 then sicid else null end) cnt_2
  from (select count(unique v.pay_month) cnt_mnth, v.sicid, v.sum_pay
          from si_member_2 v
         where v.pay_date_gfss >= :d_from
           and v.pay_date_gfss <  :d_to
           and v.type_payer = 'E'
         group by v.sicid, v.sum_pay)
 group by cnt_mnth
 order by 1
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
