# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3011 (процедура REP_MT_ATT_11).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения по первому разделу (приложение Минтруда; в заголовке оригинала
«Приложение №11», номер бланка не переносится): получатели и суммы по
числу месяцев, за которые назначена сумма первого раздела (долг /
ежемесячная выплата).

Источник - `pnpd_document` + `pnpt_payment` + `payment_history`: по
получателю, виду выплаты и размеру выплаты суммируется `sum_debt`
(только документы с `sum_debt > 0`), число месяцев - `sum_debt / sum_pay`
с округлением вниз до целого, не более 12 (`least(floor(trunc(x, 2)), 12)`).
Деление на `ph.sum_pay` оригинальное: нулевая выплата даст ORA-01476, как
и в PL/SQL, - молча подставлять защиту от нуля нельзя, это поменяет итоги.

Строка «Количество месяцев»: 0 - «до 1», 12 - «12 и более», остальное -
число. Виды выплат - 0701...0705, группы в шапке из `SetPageHead`. Закомментированный
в оригинале блок «Нулевые» (нулевая сумма выплаты) не переносится.
Итоговая строка суммирует все колонки (`SetColSumTotal(2..11)`).

Период - один месяц (`trunc(month, 'MM')` и `last_day`). Подпись «с ... по ...»
печатает первый и последний день месяца.
"""
from db.connect import LOADER_PROFILE
from util.period import dates_label
from util.xlsx_report import build_report, Col, Group

report_code = '3011'
report_name = 'Сведения по первому разделу с {period}'

_CNT = 'Всего получателей, человек'
_SUM = 'Всего сумма, тенге'


def _pair(title, code):
    return Group(title, [Col(_CNT, f'c{code}', 'int', 16),
                         Col(_SUM, f's{code}', 'money', 20)])


COLUMNS = [
    Col('Количество месяцев, за которые назначается сумма 1 раздела',
        'mnth_txt', 'center', 22),
    _pair('Получатели социальной выплаты на случай потери кормильца', '0701'),
    _pair('Получатели социальной выплаты на случай утраты '
          'трудоспособности', '0702'),
    _pair('Получатели социальной выплаты на случай потери работы', '0703'),
    _pair('Получатели социальной выплаты на случай потери дохода в связи '
          'с беременностью и родами', '0704'),
    _pair('Получатели социальной выплаты на случай потери дохода в связи '
          'с уходом за ребенком по достижению им одного года', '0705'),
]

# :d_from / :d_to - границы месяца, :d_to исключительная. Условие по
# pd.pncp_date и ph.act_month - одно и то же окно, как в оригинале.
STMT = """
select case when t.mnth = 0  then 'до 1'
            when t.mnth = 12 then '12 и более'
            else to_char(t.mnth) end mnth_txt,
       sum(case when substr(t.rfpm, 1, 4) = '0701' then 1 else 0 end)   c0701,
       sum(case when substr(t.rfpm, 1, 4) = '0701' then dbt else 0 end) s0701,
       sum(case when substr(t.rfpm, 1, 4) = '0702' then 1 else 0 end)   c0702,
       sum(case when substr(t.rfpm, 1, 4) = '0702' then dbt else 0 end) s0702,
       sum(case when substr(t.rfpm, 1, 4) = '0703' then 1 else 0 end)   c0703,
       sum(case when substr(t.rfpm, 1, 4) = '0703' then dbt else 0 end) s0703,
       sum(case when substr(t.rfpm, 1, 4) = '0704' then 1 else 0 end)   c0704,
       sum(case when substr(t.rfpm, 1, 4) = '0704' then dbt else 0 end) s0704,
       sum(case when substr(t.rfpm, 1, 4) = '0705' then 1 else 0 end)   c0705,
       sum(case when substr(t.rfpm, 1, 4) = '0705' then dbt else 0 end) s0705
  from (select pd.pncd_id,
               pd.rfpm_id rfpm,
               sum(pd.sum_debt) dbt,
               least(floor(trunc(sum(pd.sum_debt) / ph.sum_pay, 2)), 12) mnth
          from pnpd_document pd, pnpt_payment pp, payment_history ph
         where pd.pncp_date >= :d_from
           and pd.pncp_date <  :d_to
           and ph.act_month >= :d_from
           and ph.act_month <  :d_to
           and pd.source_id = pp.pnpt_id
           and pd.source_id = ph.pnpt_id
           and pd.rfpm_id like '07%'
           and pd.pnsp_id > 0
           and pd.sum_debt > 0
           and pd.ridt_id in (4, 6, 7, 8)
           and pd.status in (0, 1, 2, 3, 5, 7)
         group by pd.pncd_id, pd.rfpm_id, ph.sum_pay, ph.pnpt_id) t
 group by t.mnth
 order by t.mnth
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True,
    period_label=dates_label,
)
