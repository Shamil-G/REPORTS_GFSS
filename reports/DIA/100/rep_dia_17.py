# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 17 «100-9 По регионам»
(процедура rep_r_9_list).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

То же, что отчёт 9 (rep_r_9) - сведения о назначенных социальных выплатах
по случаю потери работы (0703) за отчётный месяц, предыдущий месяц и тот же
месяц прошлого года, - но в разрезе отделений-регионов `rfbn_branch`
(наименование отделения вместо названия области). Расчёт и источник те же:
`sipr_maket_first_approve`, `date_approve`, сумма - `sum_all`, число -
`count(sicp_id)`.

Отличия от rep_r_9: соединение с `rfbn_branch` по `rfbn_id` целиком (код
отделения, а не области), итоговая строка - `grouping sets (1, (rfbn_id,
название))` с пустым названием (строка «Всего» подписью не снабжена, как в
оригинале). Параметр - месяц, подпись - первое число месяца. Название
дословно, как у rep_r_9 (с теми же исправлениями пробелов).

`sipr_maket_first_approve` лежит в схеме SSWH боевой БД, в тестовой
reports_test недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import first_date_label
from util.xlsx_report import build_report, Col, Group

report_code = '17'
report_name = ('Сведения о назначенных социальных выплатах из АО «ГФСС» '
               'по случаю потери работы за {period} г.')

_SUM = 'Общая сумма назначенных социальных выплат, тенге'
_CNT = 'Количество лиц, которым назначена социальная выплата , чел'


def _pair(title, n):
    return Group(title, [Col(_SUM, f'summa{n}', 'money', 22),
                         Col(_CNT, f'cnt{n}', 'int', 22)])


COLUMNS = [
    Col('Наименование областей', 'name', 'text', 36),
    _pair('За отчетный месяц', 1),
    _pair('в предыдущем месяце', 2),
    _pair('в соответствующем месяце прошлого года', 3),
]

# :d_from / :d_to - границы выбранного месяца, :d_to исключительная.
STMT = """
select name, summa1, cnt1, summa2, cnt2, summa3, cnt3
  from (select d.rfbn_id reg, br.name,
               sum(d.sum_pay1) summa1, count(d.sipt1) cnt1,
               sum(d.sum_pay2) summa2, count(d.sipt2) cnt2,
               sum(d.sum_pay3) summa3, count(d.sipt3) cnt3
          from (select /*+ first_rows */
                       f.rfbn_id, f.sicp_id sipt1, f.sum_all sum_pay1,
                       null sipt2, 0 sum_pay2, null sipt3, 0 sum_pay3
                  from sipr_maket_first_approve f
                 where f.date_approve >= :d_from
                   and f.date_approve <  :d_to
                   and f.rfpm_id like '0703%'
                union all
                select /*+ first_rows */
                       f1.rfbn_id, null sipt1, 0 sum_pay1,
                       f1.sicp_id sipt2, f1.sum_all sum_pay2, null sipt3, 0 sum_pay3
                  from sipr_maket_first_approve f1
                 where f1.date_approve >= add_months(:d_from, -1)
                   and f1.date_approve <  :d_from
                   and f1.rfpm_id like '0703%'
                union all
                select /*+ first_rows */
                       f2.rfbn_id, null sipt1, 0 sum_pay1, null sipt2, 0 sum_pay2,
                       f2.sicp_id sipt3, f2.sum_all sum_pay3
                  from sipr_maket_first_approve f2
                 where f2.date_approve >= add_months(:d_from, -12)
                   and f2.date_approve <  add_months(:d_to, -12)
                   and f2.rfpm_id like '0703%') d,
               rfbn_branch br
         where d.rfbn_id = br.rfbn_id
         group by grouping sets (1, (d.rfbn_id, br.name)))
 order by reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=first_date_label,
)
