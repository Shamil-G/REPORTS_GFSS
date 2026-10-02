# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3118 (процедура REP_R_3118).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

График социальных выплат на месяц: по дням выплат и этапам (`pnsp_id`)
численность и суммы по пяти видам выплат и итого.

Источник - `loader.pnpd_potr` (потребность по выплатам) + `pndy_daypay`
(календарь выплат). В отбор идут только этапы, совпадающие с началом или
концом этапа дня выплаты (`pnsp_id in (stagebegin, stageend)`). Численность
считается только по `ridt_id = 6`, сумма - по всем (`all_sum`); долги
(`debt_sum`, `debt_cnt`) в оригинале закомментированы и не учитываются.

Порядок видов - как в оригинале: потеря кормильца (0701), утрата
трудоспособности (0702), потеря работы (0703), беременность и роды (0704),
уход за ребёнком (0705). Заголовки групп - из `SetPageHead` (там они
расходятся с `AddCol`: «Даты социальных выплаты» и т.д.), печатался именно он.
Итого по строке - сумма пяти видов; итоговая строка суммирует все колонки
(`SetColSumTotal(3..14)`).

Период - один месяц: в оригинале `pncp_date = pMonth`, то есть параметр -
первое число месяца. Подпись: `to_char(pMonth, 'month yyyy')` - месяц строчными
и год через пробел.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '3118'
report_name = 'График социальных выплат на {period} года'

_period_label = make_period_label({1: '{month} {year}'})

_CNT = 'Численность, человек'
_SUM = 'Сумма, тенге'


def _pair(title, n):
    return Group(title, [Col(_CNT, f'c{n}', 'int', 14),
                         Col(_SUM, f's{n}', 'money', 18)])


COLUMNS = [
    Col('Даты социальных выплат', 'pay_day', 'date', 14),
    Col('Этапы социальных выплат', 'pnsp_id', 'center', 12),
    _pair('Социальная выплата на случай потери кормильца', 1),
    _pair('Социальная выплата на случай утраты трудоспособности', 2),
    _pair('Социальная выплата на случай потери работы', 3),
    _pair('Социальная выплата на случай потери дохода в связи с '
          'беременностью и родами', 4),
    _pair('Социальная выплата на случай потери дохода в связи с уходом '
          'за ребенком до года', 5),
    _pair('Итого', 6),
]

# :d_from - первое число месяца (pncp_date в pnpd_potr - месячная дата).
STMT = """
select t.pay_day,
       t.pnsp_id,
       sum(case when rfpm = '0701' then cn else 0 end) c1,
       sum(case when rfpm = '0701' then sm else 0 end) s1,
       sum(case when rfpm = '0702' then cn else 0 end) c2,
       sum(case when rfpm = '0702' then sm else 0 end) s2,
       sum(case when rfpm = '0703' then cn else 0 end) c3,
       sum(case when rfpm = '0703' then sm else 0 end) s3,
       sum(case when rfpm = '0704' then cn else 0 end) c4,
       sum(case when rfpm = '0704' then sm else 0 end) s4,
       sum(case when rfpm = '0705' then cn else 0 end) c5,
       sum(case when rfpm = '0705' then sm else 0 end) s5,
       sum(case when rfpm in ('0701', '0702', '0703', '0704', '0705')
                then cn else 0 end) c6,
       sum(case when rfpm in ('0701', '0702', '0703', '0704', '0705')
                then sm else 0 end) s6
  from (select pnsp_id, dp.pay_day, substr(pt.rfpm_id, 1, 4) rfpm,
               sum(pt.all_sum) sm,
               sum(case when ridt_id = 6 then pt.all_cnt else 0 end) cn
          from loader.pnpd_potr pt, pndy_daypay dp
         where pncp_date = :d_from
           and pt.pncp_date = dp.pay_month
           and pt.pnsp_id in (dp.stagebegin, dp.stageend)
           and rfpm_id like '07%'
         group by pnsp_id, dp.pay_day, substr(pt.rfpm_id, 1, 4)) t
 group by t.pay_day, t.pnsp_id
 order by t.pay_day, t.pnsp_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True,
    period_label=_period_label,
)
