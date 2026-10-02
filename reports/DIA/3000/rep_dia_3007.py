# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3007 (процедура rep_mt_att_07,
приложение Минтруда №7).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения о градации размеров социальных выплат по годам назначения: для вида
выплаты за месяц - сколько выплат попало в каждую ступень размера (шаг 100
тенге), и из них назначенных в каждом году.

Источник - `pnpd_document` + `payment_history` (по `source_id = pnpt_id`):
документы месяца вида выплаты (`pnsp_id > 0`, типы 4, 6, 7, 8, состояния
0, 1, 2, 3, 5, 7). На выплату берётся размер последнего месяца
(`first_value(sum_pay) over (partition by pnpt_id order by act_month desc)`),
округлённый вверх до сотни (`ceil(x / 100) * 100`, не менее 0), и дата
назначения последнего месяца (`appointdate`). Ступень печатается парой «от»
(`размер - 100`) и «до» (`размер`).

Колонки лет. В оригинале заголовки лет строились циклом по годам (для видов 0701 и 0702
- с 2005 года, для остальных - последние шесть лет), а значения выводились
жёстко 18 колонками `cnt2005...cnt2022`, привязанными к `pCurYear - 17 ...
pCurYear` (в самом коде комментарий: «каждый год увеличивать на 1»). С каждым
годом заголовки и данные расходились. Здесь колонки лет - те же годы
заголовка (для 0701/0702 с 2005 по текущий год, для остальных - последние
шесть лет), число назначенных считается за каждый из них. Это единственное
осознанное отклонение; тексты дословно. Набор колонок зависит от вида выплаты
и от текущего года, поэтому отчёт собирается при обращении (`_variant`).

Название - три строки оригинала: название, «Вид выплаты: <код> <название из
справочника srpm_payment>», «Период с: ... по: ...» (первое и последнее число
месяца). Вид, которого нет в справочнике: ошибка «Не найден вид выплаты <...> в
"справочнике выплат"».

`srpm_payment` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна; расчёт по `payment_history` и `pnpd_document` на данных
проверен (rep_stat_extend/docs/Made_2026_10_2.md).
"""
import datetime

from db.connect import LOADER_PROFILE
from util.period import period_bounds, last_day, split_period
from util.xlsx_report import build_report, Col, Group

report_code = '3007'

STEP = 100


def _years(rfpm):
    cur = datetime.date.today().year
    first = 2005 if rfpm in ('0702', '0701') else cur - 5
    return list(range(first, cur + 1))


def _columns(years):
    return [
        Group('Размер социальной выплаты с шагом в 100 тенге', [
            Col('от', 's_from', 'int', 12),
            Col('до', 's_to', 'int', 12),
        ]),
        Col('Всего, выплат', 'cnt', 'int', 16),
        Group('по году назначения',
              [Col(str(y), f'cnt{y}', 'int', 10) for y in years]),
    ]


def _stmt(years):
    year_cols = ',\n       '.join(
        f'sum(case when extract(year from appoint_date) = {y} then 1 else 0 end) cnt{y}'
        for y in years)
    return f"""
select t.sum_all - {STEP} s_from,
       t.sum_all s_to,
       count(distinct pnpt_id) cnt,
       {year_cols}
  from (select distinct
               ph.pnpt_id,
               first_value(ph.appointdate) over (partition by pnpt_id
                                                 order by ph.act_month desc) appoint_date,
               greatest(ceil(first_value(ph.sum_pay) over (partition by pnpt_id
                                  order by ph.act_month desc) / 100) * 100, 0) sum_all
          from pnpd_document d, payment_history ph
         where d.source_id = ph.pnpt_id
           and d.rfpm_id like :rfpm_id || '%'
           and d.pnsp_id > 0
           and d.pncp_date >= :d_from
           and d.pncp_date <  :d_to
           and d.ridt_id in (4, 6, 7, 8)
           and d.status in (0, 1, 2, 3, 5, 7)) t
 group by t.sum_all
 order by t.sum_all
"""


# Название вида выплаты из справочника; нет вида - ошибка, как в оригинале.
TITLE_SQL = """
select :rfpm_id || ' ' || name_ru rfpm_name
  from srpm_payment
 where rfpm_id = :rfpm_id
"""

_NAME = ('Сведения о градации размеров социальных выплат по годам назначения\n'
         'Вид выплаты: {rfpm_name}\n'
         'Период с: {period}')


def _label(rep_year, date_type, date_start=None):
    d_from, d_to = period_bounds(rep_year, date_type, date_start)
    return f'{d_from:%d.%m.%Y} по: {last_day(d_to):%d.%m.%Y}'


_variants = {}


def _variant(params):
    rfpm = str(params.get('rfpm_id') or '')[:4]
    years = tuple(_years(rfpm))
    if years not in _variants:
        _variants[years] = build_report(
            code=report_code, name=_NAME, columns=_columns(years),
            stmt=_stmt(years), profile=LOADER_PROFILE, period=True,
            period_label=_label, title_sql=TITLE_SQL,
            title_not_found='Не найден вид выплаты в "справочнике выплат"')
    return _variants[years]


def do_report(file_name, **params):
    return _variant(params)[0](file_name, **params)


def thread_report(file_name, **params):
    return _variant(params)[1](file_name, **params)
