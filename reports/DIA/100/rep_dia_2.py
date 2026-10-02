# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты по выплатам», отчёт 2 (процедура rep_2).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Социальные выплаты из АО "ГФСС" через ГЦВП по РК за месяц: по областям
число получателей и сумма выплат всего и по видам - потеря кормильца (0701),
утрата трудоспособности (0702), потеря работы (0703), беременность и роды
(0704), уход за ребёнком (0705).

Источник - `pnpd_document` + `pmpd_pay_doc` (платёжные документы
выплаты по `mhmh_id`, доставленные: `tmst_id = 103`) за месяц `pncp_date`.
Сумма - `pay_sum + sum_debt` по документам в статусах 1, 2, 5, 3, 7; число
получателей - число документов с `ridt_id = 6` (как в оригинале: считается
строка, а не уникальный человек). «Всего» - сумма по пяти видам (считается в
запросе, как `i.cnt_0701 + ... ` в оригинале). Строка итога -
`grouping sets (1, (регион, название))`, у неё область пустая.

Параметр - месяц; в оригинале при пустом значении бралась текущая оплатная
дата `setup.PayPeriod`, здесь значение по умолчанию - текущий месяц.
Название: месяц с заглавной буквы без года (`Initcap(tlsd.Get_Month_Name)`),
опечатка оригинала (латинская «C» в слове «Социальные») исправлена.

Шапка. В `SetPageHead` оригинала скобки расставлены с лишними закрывающими:
по смыслу пять видов выплат вложены в группу «в том числе по видам
социальных выплат», так они и выведены. `<br>` в заголовках заменены
пробелами. `s_region_name` - функция схемы SSWH (название из `rfrg_region`).

`pmpd_pay_doc` и `s_region_name` в тестовой reports_test недоступны: на данных
отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = '2'
report_name = 'Социальные выплаты из АО "ГФСС" через ГЦВП по РК за {period}'

_period_label = make_period_label({1: '{Month}'})

_CNT = 'Число получателей (человек)'
_SUM = 'Сумма выплат (тенге)'


def _pair(title, code):
    return Group(title, [Col(_CNT, f'cnt_{code}', 'int', 16),
                         Col(_SUM, f'sum_{code}', 'money', 20)])


COLUMNS = [
    Col('Области', 'reg_name', 'text', 36),
    Group('Всего', [
        Col('Число получателей * (человек)', 'cnt_all', 'int', 16),
        Col('Сумма выплат ** (тенге)', 'sum_all', 'money', 20),
    ]),
    Group('в том числе по видам социальных выплат', [
        _pair('По случаю потери кормильца', '0701'),
        _pair('По случаю утраты трудоспособности', '0702'),
        _pair('По случаю потери работы', '0703'),
        _pair('По беременности и родам', '0704'),
        _pair('По уходу за ребенком по достижению им 1 года', '0705'),
    ]),
]

# :d_from - первое число месяца (pncp_date документов - месячная дата).
STMT = """
select region, reg_name,
       cnt_0701 + cnt_0702 + cnt_0703 + cnt_0704 + cnt_0705 cnt_all,
       sum_0701 + sum_0702 + sum_0703 + sum_0704 + sum_0705 sum_all,
       cnt_0701, sum_0701, cnt_0702, sum_0702, cnt_0703, sum_0703,
       cnt_0704, sum_0704, cnt_0705, sum_0705
  from (select /*+ first_rows*/
               substr(d.rfbn_id, 1, 2) region,
               s_region_name(substr(d.rfbn_id, 1, 2)) reg_name,
               sum(case when d.rfpm_id like '0701%' and d.status in (1, 2, 5, 3, 7) then d.pay_sum + d.sum_debt else 0 end) sum_0701,
               sum(case when d.rfpm_id like '0701%' and d.ridt_id = 6 then 1 else 0 end) cnt_0701,
               sum(case when d.rfpm_id like '0702%' and d.status in (1, 2, 5, 3, 7) then d.pay_sum + d.sum_debt else 0 end) sum_0702,
               sum(case when d.rfpm_id like '0702%' and d.ridt_id = 6 then 1 else 0 end) cnt_0702,
               sum(case when d.rfpm_id like '0703%' and d.status in (1, 2, 5, 3, 7) then d.pay_sum + d.sum_debt else 0 end) sum_0703,
               sum(case when d.rfpm_id like '0703%' and d.ridt_id = 6 then 1 else 0 end) cnt_0703,
               sum(case when d.rfpm_id like '0704%' and d.status in (1, 2, 5, 3, 7) then d.pay_sum + d.sum_debt else 0 end) sum_0704,
               sum(case when d.rfpm_id like '0704%' and d.ridt_id = 6 then 1 else 0 end) cnt_0704,
               sum(case when d.rfpm_id like '0705%' and d.status in (1, 2, 5, 3, 7) then d.pay_sum + d.sum_debt else 0 end) sum_0705,
               sum(case when d.rfpm_id like '0705%' and d.ridt_id = 6 then 1 else 0 end) cnt_0705
          from pnpd_document d, pmpd_pay_doc pd
         where d.pncp_date = :d_from
           and d.ridt_id in (3, 4, 7, 6, 8)
           and d.status in (0, 1, 2, 5, 3, 7)
           and d.rfpm_id like '07%'
           and d.pnsp_id > 0
           and d.mhmh_id = pd.mhmh_id
           and pd.tmst_id = 103
         group by grouping sets (1, (substr(d.rfbn_id, 1, 2), s_region_name(substr(d.rfbn_id, 1, 2)))))
 order by region
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
