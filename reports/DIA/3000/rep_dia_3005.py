# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3005 (процедура REP_MT_ATT_05).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о градации размеров социальных выплат вновь назначенных
получателей (приложение Минтруда №5; в заголовке оригинала «Приложение №5»,
номер бланка не переносится).

Источник - `sipr_maket_first_approve` (макеты первого назначения): отбор по
дате утверждения макета `date_approve` в периоде. Размер выплаты
(`greatest(sum_all, 0)`) раскладывается на корзины шагом 100 тенге через
`width_bucket(sum_all, 100, max_sm, max_sm / 100)`, где `max_sm` - наибольший
размер по данному виду выплаты. По каждой корзине и виду - число получателей
и средний размер.

В оригинале число и среднее по виду доставались скалярными подзапросами
`(select cnt from pp where gr_sm = d.gr_sm and rfpm = ...)`; `pp` сгруппирован
по (корзина, вид), значит строка единственная, и здесь это условная
агрегация по корзине - результат тот же, без риска TOO_MANY_ROWS.

Соответствие видов графам (как в `Rep.td` оригинала, не по порядку кодов):
СВут - 0702, СВпк - 0701, СВпр - 0703, СВбр - 0704, СВур - 0705.
Подпись корзины: `gr_sm || '00' || ' - ' || (gr_sm || '00' + 100 - 1)`.

Заголовки - из `SetPageHead`. Название и подпись периода дословно:
«Период с: ... по: ...» (в оригинале вторая строка более мелким шрифтом).
`trunc(date_approve) between` заменено на полуоткрытый интервал (правило
проекта).

Таблица `sipr_maket_first_approve` лежит в схеме SSWH боевой БД, в тестовой
reports_test её нет: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3005'
report_name = ('Сведения о градации размеров социальных выплат вновь '
               'назначенных получателей\n'
               'Период с: {date_from} по: {date_to}')

_N = 'Всего вновь назначенных получателей {}, человек'
_N2 = 'Всего вновь назначенных получателей {}, человек'
_AVG = 'Средний размер {}, тенге'

COLUMNS = [
    Col('Градация (шаг 100 тг.)', 'gr_sm_text', 'center', 20),
    Col(_N.format('Свут'), 'cnt0702', 'int', 22),
    Col(_AVG.format('СВут'), 'avgsm0702', 'money', 18),
    Col(_N2.format('СВпк'), 'cnt0701', 'int', 22),
    Col(_AVG.format('СВпк'), 'avgsm0701', 'money', 18),
    Col(_N2.format('СВпр'), 'cnt0703', 'int', 22),
    Col(_AVG.format('СВпр'), 'avgsm0703', 'money', 18),
    Col(_N2.format('СВбр'), 'cnt0704', 'int', 22),
    Col(_AVG.format('СВбр'), 'avgsm0704', 'money', 18),
    Col(_N2.format('СВур'), 'cnt0705', 'int', 22),
    Col(_AVG.format('СВур'), 'avgsm0705', 'money', 18),
]

# :d_from / :d_to - период из формы, :d_to исключительная.
STMT = """
with pp as (
    select width_bucket(p.sum_all, 100, max_sm, max_sm / 100) gr_sm,
           rfpm,
           count(sicp_id) cnt,
           round(avg(p.sum_all), 2) sm
      from (select substr(s.rfpm_id, 1, 4) rfpm,
                   greatest(s.sum_all, 0) sum_all,
                   s.sicp_id,
                   first_value(s.sum_all) over (
                       partition by substr(s.rfpm_id, 1, 4)
                       order by s.sum_all)      min_sm,
                   first_value(s.sum_all) over (
                       partition by substr(s.rfpm_id, 1, 4)
                       order by s.sum_all desc) max_sm
              from sipr_maket_first_approve s
             where s.date_approve >= :d_from
               and s.date_approve <  :d_to) p
     group by width_bucket(p.sum_all, 100, max_sm, max_sm / 100), rfpm
)
select d.gr_sm,
       d.gr_sm || '00' || ' - '
           || to_char(to_number(nvl(d.gr_sm, 0) || '00') + 100 - 1) gr_sm_text,
       sum(case when d.rfpm = '0701' then d.cnt else 0 end) cnt0701,
       sum(case when d.rfpm = '0701' then d.sm  else 0 end) avgsm0701,
       sum(case when d.rfpm = '0702' then d.cnt else 0 end) cnt0702,
       sum(case when d.rfpm = '0702' then d.sm  else 0 end) avgsm0702,
       sum(case when d.rfpm = '0703' then d.cnt else 0 end) cnt0703,
       sum(case when d.rfpm = '0703' then d.sm  else 0 end) avgsm0703,
       sum(case when d.rfpm = '0704' then d.cnt else 0 end) cnt0704,
       sum(case when d.rfpm = '0704' then d.sm  else 0 end) avgsm0704,
       sum(case when d.rfpm = '0705' then d.cnt else 0 end) cnt0705,
       sum(case when d.rfpm = '0705' then d.sm  else 0 end) avgsm0705
  from pp d
 group by d.gr_sm
 order by d.gr_sm
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
