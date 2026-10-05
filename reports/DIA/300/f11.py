# -*- coding: utf-8 -*-
# ============================================================
# ЗАМЕНЁН (дублируется) - по сообщению Заказчика (02.10.2026).
# Заменяющий отчёт: консолидированные, dynamic.
# Закомментирован в model/list_reports.py (группа «Согласно Приказа Минтруда (REP_MINTRUD)»), ключ 04. Код не удалён - для итоговой сверки.
# Oracle: REP_MINTRUD.Fill_F11, Rep_11
# ============================================================
"""============================================================
REP_MINTRUD (Rep_Mintrud.pck) - см. заглавие f3.py про разделение с
REP_STAT_EXTEND.
============================================================

Приложение 18 (Rep_Mintrud.Fill_F11 + Rep_11). Динамика численности
получателей социальных выплат за месяц по одному виду выплаты: на начало
месяца, назначено, умерло, прибыло, убыло, восстановлено, снято, на конец.

Перенос Rep_Mintrud.pck (строки 1066-1288 - Fill_F11, 1290-1373 - Rep_11).
Протокол: 49 запусков (0 ошибок), последний 04.09.2026, ~20 минут каждый.

Оригинал - цикл по строкам с двумя select into на каждого прибывшего и
выбывшего. Здесь то же самое одним запросом:

- `c` / `p` - получатели текущего и прошлого месяца (документы ridt_id = 6
  за pncp_date = начало месяца), дословно с `unique` оригинала.
- `j` - full outer join c и p по source_id. Старым синтаксисом Oracle full
  join не пишется, поэтому это union all: c с прошлым месяцем через (+) и
  отдельно p, которых нет в c. Строки те же, что у full join, включая
  source_id = NULL (они не совпадают ни с чем и попадают в обе половины
  как несовпавшие).
- Классификация как в цикле: сначала `in_p is null` (прибывший), иначе
  `in_c is null` (выбывший). Причина - минимальный код операции в
  pnap_act_prt_2 за месяц (`order by 1 ... rownum = 1`), нет акта -
  восстановленный / снятый (ветка no_data_found).
- Сумма назначенным (строка 10) - по документам с source_id прибывшего,
  ridt_id 6/7/8, без фильтра по виду выплаты, как в оригинале.

Вид выплаты фильтруется после соединения, по nvl(c.rfpm, p.rfpm), как его
определял цикл: если у source_id сменился вид, совпадение месяцев не
теряется. Сами c и p, как и в оригинале, берутся по всем четырём видам.

Строки 0704 нет: Rep_11 её не знает (Case без ветки, при 0704 падал с
CASE_NOT_FOUND), Fill_F11 её не считает. Список видов - свой, не LIST_RFPM.

ОТЛИЧИЯ ОТ ОРИГИНАЛА:
- Форма Rep_11 печатала один вид выплаты за запуск (форма 8-N). Здесь все
  четыре вида - колонками одного листа, параметр формы - только год и месяц.
- Только месяц. Планировщик запускал Fill_F11 и за квартал (2026,2,2) и за 9
  месяцев (2025,4,4), но Rep_11 читает только date_type = 1, а Fill_F11 при
  любом типе считает первый месяц периода (pncp_date = d_from). Эти запуски
  писали данные, которые никто не читал.
- Строка без данных печатается нулём. Rep_11 печатал только строки, которые
  нашлись в EAV: месяц без смертей давал форму без строки "смертность".
  Здесь все 10 строк всегда (п. 7 чек-листа).
- Акты брались `act_month between d_from and last_day(d_from)`: при времени
  в act_month последний день месяца после полуночи терялся. Здесь
  `>= :d_from and < :d_to`.
- В оригинале при debug > 0 (а он 1) на каждого прибывшего шла запись в
  log_reports автономной транзакцией. Здесь лога по строкам нет.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'MINTRUD.F11'
# p_PageHead Rep_11 (строки 1297-1323): <br> перед "за" схлопнут в пробел.
# "Приложение №18", cOrderName и "Форма №8-N" не переносятся - как в f3.py.
report_name = 'Динамика численности получателей социальных выплат за {period}'

# Case по rep_rfpm_ (строки 1313-1322) дословно, "ребёнком" - через ё, как в
# исходнике. Каждый вид - своя колонка листа, порядок колонок по просьбе
# Заказчика: 0701 перед 0702 (в Case оригинала наоборот).
RFPM_TEXT = {
    '0701': 'потери кормильца',
    '0702': 'утраты трудоспособности',
    '0703': 'потери работы',
    '0705': 'потери дохода в связи с уходом за ребёнком',
}

# to_char(..., 'month') || год - месяц строчными, с пробелом перед годом (to_char без fm дополняет
# месяц пробелами до 9 символов), как в f3.
_period_label = make_period_label({1: '{month} {year} года'})

# (value_type, текст строки, kind) - строки 1342-1363 дословно.
ROWS = [
    (7, 'численность получателей на начало месяца, человек', 'int'),
    (8, 'сумма выплат, тенге', 'money'),
    (9, 'назначение, человек', 'int'),
    (10, 'сумма социальных выплат для назначенных, тенге', 'money'),
    (11, 'смертность, человек', 'int'),
    (12, 'прибывшие, человек', 'int'),
    (13, 'убывшие, человек', 'int'),
    (14, 'восстановленные, человек', 'int'),
    (15, 'снятые, человек', 'int'),
    (16, 'численность получателей на конец месяца, человек', 'int'),
]

COLUMNS = [Col('Наименование', 'name', 'text', 60)] + [
    Col(f'{code} - по случаю {text}', f'val_{code}', 'money', 22, kind_of='kind')
    for code, text in RFPM_TEXT.items()
]

_SPINE = '\n    union all\n'.join(
    f"    select {vt} vt, '{name}' name, '{kind}' kind from dual"
    for vt, name, kind in ROWS
)
_RFPM_LIST = '\n    union all\n'.join(
    f"    select '{code}' rfpm from dual" for code in RFPM_TEXT)
_VALUE = ', '.join(f'{vt}, tt.v{vt:02d}' for vt, _, _ in ROWS)
_PIVOT = ',\n       '.join(
    f"max(decode(tt.rfpm, '{code}', decode(n.vt, {_VALUE}))) val_{code}"
    for code in RFPM_TEXT)

# Документы получателя за месяц: ridt_id = 6 (выплаты из ГФСС), статусы и
# pnsp_id > 0 - дословно из Fill_F11.
_RECIPIENTS = """
    select unique d.source_id, d.pncd_id, substr(d.rfpm_id, 1, 4) rfpm,
           f.pnpt_id source_id_main
      from pnpd_document d, pnpt_payment f
     where d.pncp_date = {month}
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0705')
       and d.ridt_id = 6
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
       and d.source_id = f.pnpt_id(+)"""

# :d_from - первое число месяца, :d_to - первое число следующего.
# Все четыре вида выплат считаются одним запросом: rfpm - ключ группировки
# вместо фильтра :rfpm_id. Вид - по c.rfpm (у выбывших, которых в c нет, - по
# p.rfpm), как фильтровал оригинал.
STMT = f"""
with c as ({_RECIPIENTS.format(month=':d_from')}
),
p as ({_RECIPIENTS.format(month='add_months(:d_from, -1)')}
),
j as (
    select c.rfpm rfpm,
           c.source_id in_c, p.source_id in_p,
           c.source_id_main in_c_main, p.source_id_main in_p_main,
           nvl(c.pncd_id, p.pncd_id) pncd_id
      from c, p
     where c.source_id = p.source_id(+)
    union all
    select p.rfpm, null, p.source_id, null, p.source_id_main, p.pncd_id
      from p
     where not exists (select 1 from c where c.source_id = p.source_id)
),
arr as (
    -- 100 новое назначение, 120/121 прибытие по запросу, 110 из-за рубежа
    select ap.pncd_id,
           min(decode(ap.riac_id, 100, 1, 120, 2, 121, 2, 110, 3)) oper
      from pnap_act_prt_2 ap
     where ap.act_month >= :d_from
       and ap.act_month <  :d_to
       and ap.riac_id in (100, 120, 121, 110)
     group by ap.pncd_id
),
dep as (
    -- 122 смерть, 151/152 выбытие по запросу, 150 выбытие за рубеж
    select ap.pncd_id,
           min(decode(ap.riac_id, 122, 1, 151, 2, 152, 2, 150, 3)) oper
      from pnap_act_prt_2 ap
     where ap.act_month >= :d_from
       and ap.act_month <  :d_to
       and ap.riac_id in (122, 150, 151, 152)
     group by ap.pncd_id
),
paid as (
    -- 6 выплаты из ГФСС, 7 10% удержания, 8 удержания из соцвыплат
    select d.source_id, sum(d.pay_sum + d.sum_debt) sm
      from pnpd_document d
     where d.pncp_date = :d_from
       and d.ridt_id in (6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
     group by d.source_id
),
ev as (
    -- 0 - акта нет: прибывший восстановлен, выбывший снят
    select j.rfpm, j.in_c_main, j.in_p_main, s.sm,
           case when j.in_p is null then nvl(a.oper, 0) end arr_oper,
           case when j.in_p is not null and j.in_c is null
                then nvl(d.oper, 0) end dep_oper
      from j, arr a, dep d, paid s
     where a.pncd_id(+) = j.pncd_id
       and d.pncd_id(+) = j.pncd_id
       and s.source_id(+) = j.in_c
),
rf as ({_RFPM_LIST}
),
t as (
    -- вид без данных даёт строку нулей, как раньше аггрегат без group by
    select rf.rfpm,
           count(ev.in_p_main)                                   v07,
           count(case when ev.arr_oper = 1 then 1 end)           v09,
           nvl(sum(case when ev.arr_oper = 1 then ev.sm end), 0) v10,
           count(case when ev.dep_oper = 1 then 1 end)           v11,
           count(case when ev.arr_oper = 3 then 1 end)           v12,
           count(case when ev.dep_oper = 3 then 1 end)           v13,
           count(case when ev.arr_oper in (0, 2) then 1 end)     v14,
           count(case when ev.dep_oper in (0, 2) then 1 end)     v15,
           count(ev.in_c_main)                                   v16
      from rf, ev
     where ev.rfpm(+) = rf.rfpm
     group by rf.rfpm
),
s8x as (
    -- строка 8: все выплаты месяца по виду, ridt_id 6/7/8
    select substr(d.rfpm_id, 1, 4) rfpm, sum(d.pay_sum + d.sum_debt) v08
      from pnpd_document d
     where d.pncp_date = :d_from
       and d.ridt_id in (6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
     group by substr(d.rfpm_id, 1, 4)
),
tt as (
    select t.*, nvl(s8x.v08, 0) v08
      from t, s8x
     where s8x.rfpm(+) = t.rfpm
),
spine as (
{_SPINE}
)
select n.name, n.kind,
       {_PIVOT}
  from spine n, tt
 group by n.vt, n.name, n.kind
 order by n.vt
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=False,
    period_label=_period_label,
)
