# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3003 (процедура REP_MT_ATT_03,
из веба вызывается WEB_REP_MT_ATT_03).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Оперативные сведения по социальным выплатам в разрезе областей за год -
по месяцам.

Оригинал сам ничего не считает: читает EAV `rptb_rep_mintrud_data`
(date_type = 1, date_spare = месяц 1..12, value_type 4 - число получателей,
5 - сумма), которую заполняет ежемесячный `REP_MINTRUD.fill_f4(год, 1,
месяц)` из планировщика. REP_MINTRUD признан устаревшим, поэтому здесь
считается напрямую из источника `fill_f4` - курсора `cur_F4` (тот же запрос,
что в f4.py и консолидированном 6CB), по каждому месяцу отдельно: регион -
по последнему за МЕСЯЦ документу на человека, число получателей -
count(distinct pncd_id) за месяц, как давал помесячный fill_f4.

«Всего сумма» по виду и «Итого ... с начала года» - только суммы, численность
за год в оригинале не считается. В паре сначала сумма, потом численность
(в F4 наоборот). Порядок видов 0701..0705 - как в оригинале (rfpms).
Пропуски - пустые ячейки (PrnOnePair проверяет tbl.exists), blank_zero не нужен.

Области - из `branch` (`XX00`, кроме `0000` ГЦВП центр). Состав сверен с
`rfrg_region` 13.10.2026: коды 01..20 совпадают один к одному; название из
`branch` полное («Акмолинская область»), в `rfrg_region` короткое и с
подменой казахской буквы («Ўлытау»), поэтому взято из `branch`, как в
TOLEM_REP_MT_ATT_03. Колонка «№» - как в WEB_REP_MT_ATT_03.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3003'
report_name = ('Оперативные сведения по социальным выплатам в разрезе '
               'областей за отчетный период {rep_year} года')

_MONTHS = ['январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль',
           'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']

_TYPES = [
    ('0701', 'по случаю потери кормильца'),
    ('0702', 'по случаю утраты трудоспособности'),
    ('0703', 'по случаю потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, '
             'с усыновлением (удочерением) новорожденного ребенка(детей)'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

COLUMNS = [Col('Области', 'reg', 'text', 30)]
for code, title in _TYPES:
    COLUMNS.append(Group(title, [
        Group(month, [
            Col('сумма', f'sum_{code}_{m:02}', 'money', 16),
            Col('числ-ть', f'cnt_{code}_{m:02}', 'int', 10),
        ]) for m, month in enumerate(_MONTHS, start=1)
    ]))
    COLUMNS.append(Col('Всего сумма', f'sum_{code}', 'money', 18))
COLUMNS.append(Col('Итого сумма по социальным выплатам с начала года',
                   'sum_all', 'money', 20))

_PIVOT = ',\n'.join(
    f"           sum(case when rfpm = '{code}' and mon = {m} then sm end) sum_{code}_{m:02},\n"
    f"           sum(case when rfpm = '{code}' and mon = {m} then cnt end) cnt_{code}_{m:02}"
    for code, _ in _TYPES for m in range(1, 13)
) + ',\n' + ',\n'.join(
    f"           sum(case when rfpm = '{code}' then sm end) sum_{code}"
    for code, _ in _TYPES
)

# :rep_year - год из формы. Месяц - календарный, по pncp_date. Текущий
# (неполный) месяц не берётся: в оригинале месяц появлялся только после
# fill_f4 в начале следующего.
STMT = f"""
with base as (
    select /*+ parallel(4) */
           substr(d.rfpm_id, 1, 4) rfpm,
           extract(month from d.pncp_date) mon,
           d.pncd_id,
           d.pay_sum + d.sum_debt sum_pay,
           first_value(substr(d.rfbn_id, 1, 2)) over (
               partition by d.pncd_id, trunc(d.pncp_date, 'mm')
               order by d.pncp_date desc) reg
      from pnpd_document d, pnpt_payment pp
     where d.source_id = pp.pnpt_id(+)
       and d.pncp_date >= to_date('01.01.' || :rep_year, 'dd.mm.yyyy')
       and d.pncp_date <  least(add_months(to_date('01.01.' || :rep_year, 'dd.mm.yyyy'), 12),
                                trunc(sysdate, 'mm'))
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
),
agg as (
    select rfpm, reg, mon,
           count(distinct pncd_id) cnt,
           sum(sum_pay)            sm
      from base
     group by rfpm, reg, mon
),
pivot as (
    select reg rg,
{_PIVOT},
           sum(sm) sum_all
      from agg
     group by reg
)
select substr(b.rfbn_id, 1, 2) || ' - ' || b.name reg, p.*
  from branch b, pivot p
 where b.rfbn_id like '__00'
   and b.rfbn_id != '0000'
   and p.rg(+) = substr(b.rfbn_id, 1, 2)
 order by b.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, title_params=('rep_year',), totals=True,
)
