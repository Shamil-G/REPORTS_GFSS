# -*- coding: utf-8 -*-
"""8006. Доля суммы социальных выплат к сумме социальных отчислений (с учетом
пени) в разрезе регионов.

Перенос WEB_REP_R_8006 (AIS 8006, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8006.xlsx` (январь - июль
2025). Период - с начала года по выбранный месяц (в оригинале зашит).

Регион социального отчисления - регион плательщика по последнему платежу
участника: `si_member_2.p_rnn` -> `rfon_organization.bin` -> `.cato` ->
`cato_branch.rfbn_id`; все платежи участника за период относятся к этому
региону (`first_value ... over (partition by sicid order by pay_date_gfss
desc)`), как в оригинале. Регион социальной выплаты - регион отделения
(`pnpd_document.rfbn_id`) по последнему документу получателя. Плательщик без
региона - строка «Не определен». Платежи берутся так же, как в 8005
(`pay_date_gfss` в периоде, `pay_date` с месяца, предшествующего началу).

Отличие от образца: заголовок колонок «млн. тенге», а в образце стояли суммы в
тенге (18 763 022 932 вместо 18 763,02). В 8005, где колонки подписаны так же,
деление на миллион есть, поэтому здесь суммы пересчитаны в миллионы; доля не
изменилась. Оригинал соединял `pnpt_payment`, не используя её колонки, - здесь
она не берётся.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '8006'
report_name = ('Доля суммы социальных выплат к сумме социальных отчислений '
               '(с учетом пени) {period} '
               '(8006, составлен без технического задания)')

_period_label = make_period_label({7: 'за {n} мес. {year} года'})

COLUMNS = [
    Col('Регионы', 'region', 'text', 36),
    Col('Сумма социальных отчислений  с учетом пени, млн. тенге', 'so',
        'money', 26),
    Col('Сумма социальных выплат, млн. тенге', 'sv', 'money', 24),
    Col('Доля суммы СВ к сумме СО (с учетом пени), в %', 'perc', 'pct', 20),
]

STMT = """
with s as (
    select m.sicid, m.sum_pay, m.pay_date_gfss, m.p_rnn
      from si_member_2 m
     where m.pay_date_gfss >= :y_from
       and m.pay_date_gfss <  :d_to
       and m.pay_date >= add_months(:y_from, -1)
       and m.pay_date <  :d_to
),
so_prep as (
    select /*+parallel(2)*/
           first_value(substr(coalesce(cb.rfbn_id, 'ZZ'), 1, 2))
               over (partition by s.sicid order by s.pay_date_gfss desc) reg,
           s.sum_pay
      from s, rfon_organization rf, cato_branch cb
     where s.p_rnn = rf.bin(+)
       and rf.cato = cb.code(+)
),
so as (
    select coalesce(reg, 'ZZ') reg, sum(sum_pay) sm
      from so_prep
     group by reg
),
sv as (
    select /*+parallel(2)*/
           x.reg, sum(x.sum_pay) total_sum
      from (select d.pay_sum + d.sum_debt sum_pay,
                   first_value(substr(d.rfbn_id, 1, 2))
                       over (partition by d.pncd_id order by d.pncp_date desc) reg
              from pnpd_document d
             where d.pncp_date >= :y_from
               and d.pncp_date <  :d_to
               and d.ridt_id in (4, 6, 7, 8)
               and d.status in (0, 1, 2, 3, 5, 7)
               and d.pnsp_id > 0) x
     group by x.reg
),
regs as (
    select so.reg ord, nvl(b.name, 'Не определен') region,
           so.sm / 1000000 so, sv.total_sum / 1000000 sv,
           sv.total_sum / nullif(so.sm, 0) perc, 0 bold
      from so, sv, branch b
     where sv.reg(+) = so.reg
       and b.rfbn_id(+) = so.reg || '00'
)
select region, so, sv, perc, bold
  from (
    select ord, region, so, sv, perc, bold from regs
    union all
    select 'ZZZ', 'Всего', sum(so), sum(sv), sum(sv) / nullif(sum(so), 0), 1
      from regs
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
    bold_key='bold',
)
