# -*- coding: utf-8 -*-
"""Приложение 33. Динамика количества получателей социальных выплат из ГФСС
по месяцам года, по четырём видам выплат.

Перенос REP_STAT_EXTEND.app_33_spool + Rep_app_33 (pck_utf8.sql, 2485-3139).
Протокол: app_33_spool запускается ежемесячно, последний запуск 09.2026.
Вызов в вебе: группа 1330, id 1331 ("За год").

ДИНАМИКА ПЕРЕСТРОЕНА (решение Шамиля, 01.10.2026). Оригинал брал 90 и 92..99 из
rptb_dinamika_ext, которую заполнял пакет REP_STAT_EXTEND_DINAMIKA. Пакет
невалиден (rptb_dinamika_tmp_ext удалена), таблица замёрзла на 01.12.2021 и
с 2022 года app_33 писал в EAV только сумму выплат (91). Здесь все десять
показателей считаются по живым pnpd_document / pnpt_payment / pnap_act_prt_2
ровно так, как их считает Fill_F11 (REP_MINTRUD, f11.py): value_type 90..99
оригинала соответствуют строкам 7..16 формы 18.

    90 численность получателей на начало месяца   <-> F11 строка 7
    91 сумма выплат                                <-> F11 строка 8
    92 назначение                                  <-> F11 строка 9
    93 сумма СВ для назначенных                    <-> F11 строка 10
    94 смертность                                  <-> F11 строка 11
    95 прибывшие (из-за рубежа)                    <-> F11 строка 12
    96 убывшие (за рубеж)                          <-> F11 строка 13
    97 восстановленные                             <-> F11 строка 14
    98 снятые                                      <-> F11 строка 15
    99 численность получателей на конец месяца     <-> F11 строка 16

Сверка с rptb_dinamika_ext за 01.12.2021 (последний месяц, на котором есть
эталон): счётчики расходятся на 0,02-2%, у "смертность" по 0702 - 345 против
216 (docs/STATUS-MIGRATION.md, раздел "Динамика"). Старой логики по
payment_history воспроизвести нельзя: она хранится только с 01.01.2024.
За 2022 год и позже эталона нет.

Что изменилось по смыслу (не по тексту, тексты дословно):
- Строка 93 "сумма социальных выплат для назначенных, тенге". В оригинале в
  неё писалось in_new из rptb_dinamika_ext с row_no = 3, то есть ЧИСЛО
  назначенных с долгом, а не сумма; здесь, как в F11, это сумма выплат
  (pay_sum + sum_debt) по назначенным в месяце. Это согласуется с
  подписью строки, но не с прежними цифрами.
- Показатели больше не накапливаются в EAV помесячно сборщиком: каждый
  запрос пересчитывает все 12 месяцев года по живым данным. Платёжные
  документы могут меняться задним числом, поэтому повторный расчёт
  закрытого месяца способен дать другие цифры, чем раньше (раньше они
  замораживались при сборе в БД, которая чистилась).
- Хранение: отчёт снимается ЕЖЕМЕСЯЧНО (параметры: год и "с начала года по
  месяц"), каждый срез - отдельный xlsx на сервере со сроком жизни 0 (бесконечно,
  решение Шамиля 01.10.2026): срез не пересчитывается и не зависит от
  очистки БД. Малый срок выставляют только для тестов.
- Вид 0704 не считается, как и в оригинале и в F11.
- Нулевая и пустая ячейка печатаются пустыми (оригинал: `if x <> 0 and x is
  not null`), blank_zero=True.

Разбор свёрнутых столбцов (Rep_app_33) сохранён: помесячные столбцы - значение
месяца; накопительные ("за 2 месяца", "за I квартал", ..., "за год") - для
показателя 90 берётся значение ПЕРВОГО месяца периода, для 99 - ПОСЛЕДНЕГО,
для 91..98 - сумма за период. Двойной пробел в "за III  квартал" и "за IV  квартал"
- как в исходнике (строки 2849, 2855 оригинала).

Раскладка: оригинал печатал четыре отдельные таблицы, каждая с заголовком
вида выплаты над столбцами месяцев. Здесь одна таблица, вид выплаты - первый
столбец, печатается в первой строке своего блока.

Ветка шапки 'f' ("Форма № 5") не переносится: вызывался только 'm'.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'APP.33'


# cSPTitle || p_PH_per (строки 2787, 2793): "<br> за 2025 год" - перенос
# строки в HTML, здесь пробел.
report_name = ('Динамика количества* получателей социальных выплат из '
               'Государственного фонда социального страхования, {period}')

# Годовая таблица с данными с начала года по выбранный месяц: отчёт снимается
# каждый месяц и хранится готовым (тип периода 7 = "с начала года по месяц").
_period_label = make_period_label({
    7: 'за {year} год (с начала года по {month})',
})

FOOTNOTE = ('* - участники системы обязательного социального страхования - '
            'лица, за которых в отчетном периоде была произведена уплата '
            'социальных отчислений, учтенные хотя бы 1 раз')

# (код вида, заголовок блока) - порядок p_VIDList '1','2','3','5' (строка
# 2790): тексты дословно из Case оригинала (строки 2819-2828).
_VIDS = [
    ('0701', 'на случай потери кормильца'),
    ('0702', 'на случай утраты трудоспособности'),
    ('0703', 'на случай потери работы'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

# value_type оригинала, текст строки (Case, строки 3088-3100), вид значения.
_ROWS = [
    (90, 'численность получателей на начало месяца, человек', 'int'),
    (91, 'сумма выплат, тенге', 'money'),
    (92, 'назначение, человек', 'int'),
    (93, 'сумма социальных выплат для назначенных, тенге', 'money'),
    (94, 'смертность, человек', 'int'),
    (95, 'прибывшие, человек', 'int'),
    (96, 'убывшие, человек', 'int'),
    (97, 'восстановленные, человек', 'int'),
    (98, 'снятые, человек', 'int'),
    (99, 'численность получателей на конец месяца, человек', 'int'),
]

# (ключ столбца, заголовок, первый месяц, последний месяц) - порядок и тексты
# заголовков как в p_PageHead (строки 2831-2856), включая двойной пробел.
_MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
           'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']
_KEYS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep',
         'oct', 'nov', 'dec']
_PERIODS = [
    ('jan_0', 'январь', 1, 1),
    ('feb_0', 'февраль', 2, 2),
    ('m2_0', 'за 2 месяца', 1, 2),
    ('mar_0', 'март', 3, 3),
    ('q1_0', 'за I квартал', 1, 3),
    ('apr_0', 'апрель', 4, 4),
    ('m4_0', 'за 4 месяца', 1, 4),
    ('may_0', 'май', 5, 5),
    ('m5_0', 'за 5 месяцев', 1, 5),
    ('jun_0', 'июнь', 6, 6),
    ('q2_0', 'за II квартал', 4, 6),
    ('hy1_0', 'за полугодие', 1, 6),
    ('jul_0', 'июль', 7, 7),
    ('m7_0', 'за 7 месяцев', 1, 7),
    ('aug_0', 'август', 8, 8),
    ('m8_0', 'за 8 месяцев', 1, 8),
    ('sep_0', 'сентябрь', 9, 9),
    ('m9_0', 'за 9 месяцев', 1, 9),
    ('q3_0', 'за III  квартал', 7, 9),
    ('oct_0', 'октябрь', 10, 10),
    ('m10_0', 'за 10 месяцев', 1, 10),
    ('nov_0', 'ноябрь', 11, 11),
    ('m11_0', 'за 11 месяцев', 1, 11),
    ('dec_0', 'декабрь', 12, 12),
    ('q4_0', 'за IV  квартал', 10, 12),
    ('h_0', 'за год', 1, 12),
]

COLUMNS = [
    Col('Вид выплаты', 'vid', 'text', 34),
    Col('Наименование', 'name', 'text', 46),
] + [
    # вид значения у строки свой (человеки или тенге) - колонка 'kind'
    Col(title, key, 'int', 12, kind_of='kind')
    for key, title, _a, _b in _PERIODS
]


def _period_expr(first, last):
    """Столбец года: правила Rep_app_33 (строки 3017-3072).

    90 - значение первого месяца периода, 99 - последнего,
    91..98 - сумма за период."""
    if first == last:
        return f'sum(case when v.mn = {first} then v.v end)'
    return (f'sum(case when (v.vt = 90 and v.mn = {first}) '
            f'or (v.vt between 91 and 98 and v.mn between {first} and {last}) '
            f'or (v.vt = 99 and v.mn = {last}) then v.v end)')


_AGG = ',\n       '.join(
    f'{_period_expr(a, b)} {key}' for key, _t, a, b in _PERIODS
)

_PAY_FILTER = """d.ridt_id in (6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0"""

_RFPM_LIST = ", ".join(f"'{r}'" for r, _ in _VIDS)

_UNPIVOT = ', '.join(f'v{vt} as {vt}' for vt, _n, _k in _ROWS)

_SPINE_VID = '\n    union all\n'.join(
    f"    select '{r}' rfpm, '{t}' vid, {i} ord from dual"
    for i, (r, t) in enumerate(_VIDS, start=1)
)
_SPINE_ROW = '\n    union all\n'.join(
    f"    select {vt} vt, '{n}' name, '{k}' kind from dual"
    for vt, n, k in _ROWS
)

# :rep_year - год из формы, :d_from / :d_to - границы "с начала года по месяц",
# _N ниже - число месяцев в них. mon13: mn = 0 - декабрь прошлого года (нужен
# как "предыдущий месяц" для января), 1..N - месяцы отчётного года, дальше
# месяцы не считаются (отчёт - срез на конец выбранного месяца).
#
# rec    - получатели месяца, дословно "c" и "p" из Fill_F11 (документы
#          ridt_id = 6, pncp_date = первое число месяца), но все 13 месяцев
#          одним проходом: прошлый месяц для месяца N - это месяц N-1.
# j      - full outer join текущего и прошлого месяца по source_id, записанный
#          union all (старый синтаксис Oracle full join не умеет): текущие с
#          прошлым через (+) и отдельно прошлые, которых нет в текущем.
#          Строки с source_id = NULL ни с чем не совпадают - как в F11.
# arr/dep- причина прибытия/выбытия: минимальный код операции в
#          pnap_act_prt_2 за месяц, нет акта - 0 (восстановленный/снятый).
# dsum   - выплаты месяца по документам (ridt_id 6/7/8) в разрезе
#          получателя и вида; из них paid (на получателя, для строки 93)
#          и s8 (на вид, для строки 91).
_N = "round(months_between(:d_to, :d_from))"

STMT = f"""
with vid as ({_SPINE_VID}
),
row_t as ({_SPINE_ROW}
),
mon13 as (
    select level - 1 mn,
           add_months(to_date(:rep_year || '0101', 'yyyymmdd'), level - 2) m
      from dual
   connect by level <= {_N} + 1
),
rec as (
    select unique mm.mn, d.source_id, d.pncd_id,
           substr(d.rfpm_id, 1, 4) rfpm, f.pnpt_id source_id_main
      from pnpd_document d, pnpt_payment f, mon13 mm
     where d.pncp_date = mm.m
       and substr(d.rfpm_id, 1, 4) in ({_RFPM_LIST})
       and d.ridt_id = 6
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
       and d.source_id = f.pnpt_id(+)
),
j as (
    select c.mn, c.rfpm,
           c.source_id in_c, p.source_id in_p,
           c.source_id_main in_c_main, p.source_id_main in_p_main,
           nvl(c.pncd_id, p.pncd_id) pncd_id
      from rec c, rec p
     where c.mn >= 1
       and c.source_id = p.source_id(+)
       and p.mn(+) = c.mn - 1
    union all
    select p.mn + 1, p.rfpm,
           null, p.source_id,
           null, p.source_id_main,
           p.pncd_id
      from rec p
     where p.mn <= {_N} - 1
       and not exists (select 1 from rec c
                        where c.source_id = p.source_id
                          and c.mn = p.mn + 1)
),
arr as (
    -- 100 новое назначение, 120/121 прибытие по запросу, 110 из-за рубежа
    select mm.mn, ap.pncd_id,
           min(decode(ap.riac_id, 100, 1, 120, 2, 121, 2, 110, 3)) oper
      from pnap_act_prt_2 ap, mon13 mm
     where mm.mn >= 1
       and ap.act_month >= mm.m
       and ap.act_month <  add_months(mm.m, 1)
       and ap.riac_id in (100, 120, 121, 110)
     group by mm.mn, ap.pncd_id
),
dep as (
    -- 122 смерть, 151/152 выбытие по запросу, 150 выбытие за рубеж
    select mm.mn, ap.pncd_id,
           min(decode(ap.riac_id, 122, 1, 151, 2, 152, 2, 150, 3)) oper
      from pnap_act_prt_2 ap, mon13 mm
     where mm.mn >= 1
       and ap.act_month >= mm.m
       and ap.act_month <  add_months(mm.m, 1)
       and ap.riac_id in (122, 150, 151, 152)
     group by mm.mn, ap.pncd_id
),
dsum as (
    -- 6 выплаты из ГФСС, 7 10% удержания, 8 удержания из соцвыплат
    select mm.mn, d.source_id, substr(d.rfpm_id, 1, 4) rfpm,
           sum(d.pay_sum + d.sum_debt) sm
      from pnpd_document d, mon13 mm
     where mm.mn >= 1
       and d.pncp_date = mm.m
       and {_PAY_FILTER}
     group by mm.mn, d.source_id, substr(d.rfpm_id, 1, 4)
),
paid as (
    select mn, source_id, sum(sm) sm from dsum group by mn, source_id
),
s8 as (
    select mn, rfpm, sum(sm) v91
      from dsum
     where rfpm in ({_RFPM_LIST})
     group by mn, rfpm
),
ev as (
    -- классификация как в цикле Fill_F11: сначала in_p is null (прибывший),
    -- иначе in_c is null (выбывший); нет акта - 0
    select j.mn, j.rfpm, j.in_c_main, j.in_p_main, s.sm,
           case when j.in_p is null then nvl(a.oper, 0) end arr_oper,
           case when j.in_p is not null and j.in_c is null
                then nvl(d.oper, 0) end dep_oper
      from j, arr a, dep d, paid s
     where a.mn(+) = j.mn and a.pncd_id(+) = j.pncd_id
       and d.mn(+) = j.mn and d.pncd_id(+) = j.pncd_id
       and s.mn(+) = j.mn and s.source_id(+) = j.in_c
),
mv0 as (
    select mn, rfpm,
           count(in_p_main)                                v90,
           count(case when arr_oper = 1 then 1 end)        v92,
           nvl(sum(case when arr_oper = 1 then sm end), 0) v93,
           count(case when dep_oper = 1 then 1 end)        v94,
           count(case when arr_oper = 3 then 1 end)        v95,
           count(case when dep_oper = 3 then 1 end)        v96,
           count(case when arr_oper in (0, 2) then 1 end)  v97,
           count(case when dep_oper in (0, 2) then 1 end)  v98,
           count(in_c_main)                                v99
      from ev
     group by mn, rfpm
),
grid as (
    select m.mn, s.rfpm
      from (select level mn from dual connect by level <= {_N}) m, vid s
),
mv as (
    select g.mn, g.rfpm,
           nvl(a.v90, 0) v90, nvl(b.v91, 0) v91, nvl(a.v92, 0) v92,
           nvl(a.v93, 0) v93, nvl(a.v94, 0) v94, nvl(a.v95, 0) v95,
           nvl(a.v96, 0) v96, nvl(a.v97, 0) v97, nvl(a.v98, 0) v98,
           nvl(a.v99, 0) v99
      from grid g, mv0 a, s8 b
     where a.mn(+) = g.mn and a.rfpm(+) = g.rfpm
       and b.mn(+) = g.mn and b.rfpm(+) = g.rfpm
),
vl as (
    select mn, rfpm, vt, v
      from mv
   unpivot (v for vt in ({_UNPIVOT}))
),
select case when t.vt = 90 then s.vid end vid,
       t.name,
       t.kind,
       {_AGG}
  from vid s, row_t t, vl v
 where v.rfpm(+) = s.rfpm
   and v.vt(+)   = t.vt
 group by s.ord, s.rfpm, t.vt, s.vid, t.name, t.kind
 order by s.ord, t.vt
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=True,
    period_label=_period_label, footnote=FOOTNOTE,
    sheet_name='Приложение 33',
)
