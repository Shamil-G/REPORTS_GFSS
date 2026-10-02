# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 11. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_40_41_spool / Rep_app_40_41, iTypePay='0703' (общая процедура с app_41, он остаётся)
# ============================================================
"""Приложение 40. Коэффициент замещения дохода при потере работы (СВ 0703),
в разрезе регионов и стажа участия в СОСС.

Перенос REP_STAT_EXTEND.app_40_41_spool + Rep_app_40_41(iTypePay='0703')
(pck_utf8.sql, 5746-6272). Реестр: группа 1400, вызов app_40_41_1m('m') и
аналоги; третий параметр формы (Rep.ParAsChar(3)) выбирает 0703/0705 - в
Python это два разных модуля (app_40.py/app_41.py), а не runtime-флаг,
потому что набор колонок и структура итогов разные.

Стаж - 4 группы по коэффициенту `ksu` ("коэффициент стажа участия"):
`decode(ksu, 0.7, 1, 0.75, 2, 0.85, 3, 4)` (строка 5803) - значения 0.7,
0.75, 0.85 дают группы 1-3, всё остальное (в т.ч. отсутствие явного
совпадения) - группа 4. Текстовые названия групп берутся из справочника
`moon` (id_ga/Name_ga, строка 5991) - таблица так называется в самой базе.

ДВА УРОВНЯ ИТОГОВ (сделано по образцу оригинала, по прямому решению
09.2026: не сворачивать до одного итога фреймворка). В PL/SQL после каждой
из 4 групп стажа идёт промежуточная строка "итого:" (сумма по всем
регионам этой группы), а в самом конце - "Всего по республике" (сумма по
всем группам). build_report поддерживает только один общий итог снизу
(totals=True), поэтому здесь totals=False, а обе итоговые строки - обычные
строки данных, дописанные в конец SQL через UNION ALL. Из-за этого они не
получают жирное форматирование, которое даёт framework для totals=True
(это единственное отличие от оригинала - сами числа и их место в таблице
воспроизведены точно).

Формулы итогов - не просто суммы: avg_size/avg_smd/kof на итоговой строке
взвешены количеством получателей, как в оригинале (dkn/dn и т.п., строки
6183-6188). Математически это телескопируется до отношения сумм исходных
величин (см. подробный вывод в app_38.py про avg_of) - поэтому строка
"итого:" по стажу считается из sum(cnt)/sum(sm_all)/sum(sum_avg)/sum(sm_kof)
по всем регионам этой группы, а "Всего по республике" - из тех же сумм по
всем 4 группам сразу, без двойного взвешивания вручную.

СОЗНАТЕЛЬНОЕ ОТСТУПЛЕНИЕ (как в app_38.py): построчные (не итоговые)
avg_size/avg_smd/kof здесь тоже считаются из сумм за весь период целиком, а
не копятся из помесячных значений EAV, как делал оригинал. Для месячного
периода результат идентичен, для остальных периодов - отличается и это
ожидаемо при сверке.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'APP.40'
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай потери работы в разрезе регионов, за '
               '{period}')

# Begin блок Rep_app_40_41 (строки 6259-6271) - текстуально совпадает с
# app_38.py/app_39.py.
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

# Заголовки p_PageHead (строки 6137-6143) в исходнике содержат хвостовые
# "{1}".."{7}" у каждого листа - в дереве Rep.SetPageHead это дало бы лишний
# уровень вложенности, но число колонок (AddCol - 7) сходится только с
# плоским прочтением, поэтому "{N}" здесь не вложенность, а декоративный
# остаток разметки; в Python не переносится. "По потере работы" - заголовок
# НЕ первой колонки, а колонки региона (тот же приём, что и в app_38/39:
# первый лист в p_PageHead относится не к первой AddCol).
COLUMNS = [
    Col('Стаж участия в СОСС', 'staj', 'text', 16),
    Col('По потере работы', 'reg', 'text', 30),
    Col('Кол-во, * (человек)', 'cnt', 'int'),
    Col('Сумма назначенных размеров социальных выплат, (тенге)**',
        'sm_all', 'money', 18),
    Col('Средний размер назначенных соцвыплат, (тенге) *** гр.4/гр3',
        'avg_size', 'money', 18),
    Col('Среднемес. доход, принятый для исчисления выплат (тенге)',
        'avg_smd', 'money', 20),
    Col('К замещения (%)', 'kof', 'money', 14),
]

FOOTNOTE = (
    '* количество - количество человек, которым СВ утверждена '
    'Департаментами по контролю и социальной защите в отчетном периоде\n'
    '**сумма назначенных размеров соцвыплат (СВ)за весь отчетный период\n'
    '***средний размер назначенных соцвыплат - средневзвешенный '
    '(определяется как частное суммы всех назначенных соцвыплат за '
    'отчетный период на количество получателей в отчетном периоде)\n'
    '**** коэффициент (K) замещения - среднее математическое значение '
    'коэффициентов замещения каждого получателя'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# base/agg - как в app_38/39: per (регион, стаж) количество получателей
# (count distinct sipr_id), сумма выплат, сумма дохода и сумма
# индивидуальных отношений (kof_per = sum_all/sum_avg по записи, до
# агрегации - строка 5798, "Avg(kf)" в оригинале эквивалентно sum(kf)/cnt).
# `sum_all > 0` - фильтр из оригинала (строка 5822: "избавиться от
# отрицательных сумм").
#
# detail - плоские строки регион x стаж (4 группы x 17 регионов), с
# фиксированным набором через CROSS JOIN, а не из данных - иначе регионы
# без назначений исчезли бы из отчёта.
#
# staj_totals - промежуточный итог "итого:" по стажу (сумма по регионам).
# grand_total - "Всего по республике" (сумма по всем стажам).
# grp/sub - служебные колонки только для сортировки (стаж 1..4, детали
# раньше "итого:", "Всего по республике" - последней записью с grp=5).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2)               reg_id,
           decode(s.ksu, 0.7, 1, 0.75, 2, 0.85, 3, 4) staj,
           s.sipr_id,
           s.sum_all,
           s.sum_avg,
           s.sum_all / nullif(s.sum_avg, 0)       kof_per
      from sipr_maket_first_approve_2 s
     where substr(s.rfpm_id, 1, 4) = '0703'
       and s.sum_all > 0
       and trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
),
agg as (
    select reg_id, staj,
           count(distinct sipr_id) cnt,
           sum(sum_all)            sm_all,
           sum(sum_avg)            sm_avg,
           sum(kof_per)            sm_kof
      from base
     group by reg_id, staj
),
stajs as (
    select level staj from dual connect by level <= 4
),
staj_agg as (
    select staj,
           sum(cnt)    cnt,
           sum(sm_all) sm_all,
           sum(sm_avg) sm_avg,
           sum(sm_kof) sm_kof
      from agg
     group by staj
),
detail as (
    select v.staj                                                  staj_n,
           m.name_ga                                                staj,
           rr.name                                                  reg,
           v.staj                                                   grp,
           0                                                        sub,
           rr.rfrg_id                                                ord,
           nvl(a.cnt, 0)                                             cnt,
           nvl(a.sm_all, 0)                                          sm_all,
           case when nvl(a.cnt, 0) > 0
                then a.sm_all / a.cnt else 0 end                     avg_size,
           case when nvl(a.cnt, 0) > 0
                then a.sm_avg / a.cnt else 0 end                     avg_smd,
           case when nvl(a.cnt, 0) > 0
                then (a.sm_kof / a.cnt) * 100 else 0 end             kof
      from stajs v, RFRG_REGION rr, moon m, agg a
     where m.id_ga(+)  = v.staj
       and a.reg_id(+) = rr.rfrg_id
       and a.staj(+)   = v.staj
),
staj_totals as (
    select null                                                     staj,
           'итого:'                                                 reg,
           t.staj                                                   grp,
           1                                                        sub,
           null                                                     ord,
           nvl(t.cnt, 0)                                             cnt,
           nvl(t.sm_all, 0)                                          sm_all,
           case when nvl(t.cnt, 0) > 0
                then t.sm_all / t.cnt else 0 end                     avg_size,
           case when nvl(t.cnt, 0) > 0
                then t.sm_avg / t.cnt else 0 end                     avg_smd,
           case when nvl(t.cnt, 0) > 0
                then (t.sm_kof / t.cnt) * 100 else 0 end             kof
      from stajs v, staj_agg t
     where t.staj(+) = v.staj
       and t.staj = v.staj
),
grand_total as (
    select null                                                     staj,
           'Всего по республике'                                    reg,
           5                                                         grp,
           0                                                         sub,
           null                                                      ord,
           nvl(sum(cnt), 0)                                          cnt,
           nvl(sum(sm_all), 0)                                       sm_all,
           case when nvl(sum(cnt), 0) > 0
                then sum(sm_all) / sum(cnt) else 0 end                avg_size,
           case when nvl(sum(cnt), 0) > 0
                then sum(sm_avg) / sum(cnt) else 0 end                avg_smd,
           case when nvl(sum(cnt), 0) > 0
                then (sum(sm_kof) / sum(cnt)) * 100 else 0 end        kof
      from staj_agg
)
select staj, reg, cnt, sm_all, avg_size, avg_smd, kof
  from (
    select staj, reg, grp, sub, ord, cnt, sm_all, avg_size, avg_smd, kof
      from detail
    union all
    select staj, reg, grp, sub, ord, cnt, sm_all, avg_size, avg_smd, kof
      from staj_totals
    union all
    select staj, reg, grp, sub, ord, cnt, sm_all, avg_size, avg_smd, kof
      from grand_total
  )
 order by grp, sub, ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=True,
    period_label=_period_label, footnote=FOOTNOTE,
)
