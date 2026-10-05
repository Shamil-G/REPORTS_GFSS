# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 710 (процедура Rep_Actuar_10).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средневзвешенные коэффициенты стажа участия (КСУ) по видам выплат (потеря
кормильца 0701, утрата трудоспособности 0702, потеря работы 0703): для «новых»
получателей (расчёт назначения в периоде) и для «всех» получателей на
конец периода.

Источник - архив макетов `sipr_payer_arc` по состоянию на месяц конца
периода (`sihs_history`: `act_month = trunc(конец, 'month')`, `file_type = 'D'`,
состояния 12 и 13). Дата расчёта назначения `in_date` - скалярный подзапрос по
протоколу `siap_action_protocol` (как в оригинале, с `rownum = 1`). «Новый» -
`in_date` в `[начало, конец + 1)`. Вид выплаты печатается как «код - название»
(`payment_name` - функция схемы SSWH). Итоги по колонкам «Кол-во».

В оригинале пустые даты заменялись умолчаниями (конец - сегодня, начало -
год назад); здесь обе даты задаются в форме. Названия дословно, в
кавычках - как в оригинале: Для "новых" получателей / Для "всех"
получателей. Подсказки оптимизатору `index (p xp_sipr_payer_arc)` в
запросе оставлены.

Таблицы `sihs_history`, `sipr_payer_arc`, `siap_action_protocol` лежат в схеме
SSWH боевой БД, в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '710'
report_name = ('Средневзвешенные коэффициенты стажа участия\n'
               'за период с {date_from} по {date_to}')

COLUMNS = [
    Col('Вид выплаты', 'rfpm', 'text', 44),
    Group('Для "новых" получателей', [
        Col('Кол-во', 'cnt_new', 'int', 14),
        Col('КСУ', 'avg_new', 'money', 14, total=False),
    ]),
    Group('Для "всех" получателей', [
        Col('Кол-во', 'cnt_all', 'int', 14),
        Col('КСУ', 'avg_all', 'money', 14, total=False),
    ]),
]

# :d_from / :d_to - период из формы, :d_to исключительная (конец + 1 сутки).
STMT = """
select rfpm || ' - ' || payment_name(rfpm) rfpm,
       count(case when in_date >= :d_from and in_date < :d_to then 1 end) cnt_new,
       avg(case when in_date >= :d_from and in_date < :d_to then ksu end) avg_new,
       count(1) cnt_all, avg(ksu) avg_all
  from (select /*+index (p xp_sipr_payer_arc)*/
               substr(p.rfpm_id, 1, 4) rfpm, p.ksu,
               (select /*+index (pa xp_sipr_payer_arc)*/ ap.date_calc
                  from sipr_payer_arc pa, siap_action_protocol ap
                 where pa.sipr_id = p.sipr_id
                   and p.actp_id = ap.actp_id
                   and rownum = 1) in_date
          from sihs_history h, sipr_payer_arc p
         where h.act_month = trunc(:d_to - 1, 'month')
           and h.file_type = 'D'
           and h.sipr_id = p.sipr_id
           and h.actp_sipr = p.actp_id
           and p.state in (12, 13))
 where rfpm in ('0701', '0702', '0703')
 group by rfpm
 order by rfpm
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
