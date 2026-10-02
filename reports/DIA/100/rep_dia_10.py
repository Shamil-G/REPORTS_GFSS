# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 10 (процедура rep_nnn_10).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

«Еженедельные» оперативные сведения о социальных выплатах по случаю потери
работы (0703), назначенных за период: по областям число лиц и общая сумма
вновь назначенных - за отчётный период, за предыдущие 7 суток и с начала
года по конец периода.

Источник - `sipr_maket_first_approve` (макеты первого назначения),
`date_approve`, сумма - `sum_all`, число - `count(unique sicp_id)`.
Предыдущий период: `[date_first - 7, date_first)`, с начала года:
`[1 января, date_second]`. Закомментированный в оригинале вариант по макетам
двух поколений не переносится.

Проверка как в оригинале: обе даты в одном календарном году, иначе
«Указанные даты периода находятся в разных календарных годах!».
Название дословно, но лишняя кавычка после «г.» и двойной пробел в «случаю
потери работы» исправлены; `<br>`, `<font>`, `<center>` не переносятся. Область -
функция схемы SSWH `s_region_name`; итоговая строка - «Всего».

`sipr_maket_first_approve` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group, parse_date

report_code = '10'
report_name = ('«Еженедельные» оперативные сведения о социальных выплатах из '
               'АО «ГФСС» по случаю потери работы назначенных с {date_from} '
               'по {date_to} по состоянию на {date_to} г.')


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
    Group('Вновь назначено', [
        _trio('За отчетный период', 1),
        _trio('В предыдущем периоде', 2),
        _trio('С начала года', 3),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная; :y_from - 1 января.
STMT = """
select case when reg is null then 'Всего' else s_region_name(reg) end name,
       cnt1, summa1, cnt2, summa2, cnt3, summa3
  from (select substr(d.rfbn_id, 1, 2) reg,
               count(unique d.sipt1) cnt1, sum(d.sum_pay1) summa1,
               count(unique d.sipt2) cnt2, sum(d.sum_pay2) summa2,
               count(unique d.sipt3) cnt3, sum(d.sum_pay3) summa3
          from (select /*+ first_rows */
                       fl.rfbn_id, fl.sicp_id sipt1, fl.sum_all sum_pay1,
                       null sipt2, 0 sum_pay2, null sipt3, 0 sum_pay3
                  from sipr_maket_first_approve fl
                 where fl.date_approve >= :d_from
                   and fl.date_approve <  :d_to
                   and fl.rfpm_id like '0703%'
                union all
                select /*+ first_rows */
                       fl.rfbn_id, null sipt1, 0 sum_pay1,
                       fl.sicp_id sipt2, fl.sum_all sum_pay2, null sipt3, 0 sum_pay3
                  from sipr_maket_first_approve fl
                 where fl.date_approve >= :d_from - 7
                   and fl.date_approve <  :d_from
                   and fl.rfpm_id like '0703%'
                union all
                select /*+ first_rows */
                       fl.rfbn_id, null sipt1, 0 sum_pay1, null sipt2, 0 sum_pay2,
                       fl.sicp_id sipt3, fl.sum_all sum_pay3
                  from sipr_maket_first_approve fl
                 where fl.date_approve >= :y_from
                   and fl.date_approve <  :d_to
                   and fl.rfpm_id like '0703%') d
         group by grouping sets (1, (substr(d.rfbn_id, 1, 2))))
 order by reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=_check,
)
