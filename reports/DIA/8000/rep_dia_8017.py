# -*- coding: utf-8 -*-
"""8017. Получатели социальных выплат.

Перенос WEB_REP_R_8017 (AIS 8017, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8017.xlsx` (январь - июль
2025). Период - с начала года по выбранный месяц (в оригинале зашит
01.01.2025 - 01.08.2025).

Строка - вид выплаты (0702 СВут, 0701 СВпк, 0703 СВпр, 0704 СВбр, 0705 СВур;
прочие коды - «Неизвестно», в конце). Из первых назначений
`sipr_maket_first_approve_2` за период (`date_approve`), по человеку
(`person.sicid = sicp_id`): среднее `sum_avg` (СМД), минимум, максимум и
среднее `sum_all` (размер выплаты), средний возраст (полных лет на конец
периода), средний стаж (`count_donation`, мес.). Из платёжных документов
`pnpd_document` за период: число различных получателей, из них мужчин
(`person.sex = 1`) и женщин (0).

Как в оригинале: назначения и документы связаны только по коду вида; средний
возраст - среднее целых лет по каждому человеку.

Отличие от образца: документы в оригинале брались `between '01.01.2025' and
'01.08.2025'`, то есть включали 1 августа (в образце 0702: 96 973 получателя,
56 104 мужчины, 40 869 женщин - так же получается за период по 01.08). Здесь
период заканчивается последним числом выбранного месяца, как у остальных
отчётов группы, поэтому за январь-июль 2025 численность меньше (95 724 для 0702);
СМД, мин/макс, средние размер и стаж совпали с образцом. Средний возраст в
образце показан целым числом.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '8017'
report_name = ('Получатели социальных выплат {period} '
               '(8017, составлен без технического задания)')

_period_label = make_period_label({7: 'за {n} мес. {year} года'})

COLUMNS = [
    Col('Виды выплат', 'nm', 'center', 14),
    Col('СМД, тенге', 'smd', 'money', 18),
    Col('Размеры выплат (тенге)\nMIN', 'payout_min', 'int', 16, align='center'),
    Col('Размеры выплат (тенге)\nMAX', 'payout_max', 'int', 16, align='center'),
    Col('Средний назначенный размер СВ, тенге', 'avg_payout', 'money', 20),
    Col('Средний возраст, лет', 'avg_age', 'int', 14, align='center'),
    Col('Средний стаж участия, мес.', 'avg_exp', 'money', 16, align='center'),
    Col('Всего получателей СВ, человек', 'cnt', 'int', 16, align='center'),
    Col('в том числе\nмужчины', 'cnt_m', 'int', 14, align='center'),
    Col('в том числе\nженщины', 'cnt_f', 'int', 14, align='center'),
]

STMT = """
with s as (
    select substr(sfa.rfpm_id, 1, 4) rfpm,
           avg(sfa.sum_avg) smd,
           min(sfa.sum_all) payout_min,
           max(sfa.sum_all) payout_max,
           avg(sfa.sum_all) avg_payout,
           avg(trunc(months_between(:d_to, p.birthdate) / 12)) avg_age,
           avg(sfa.count_donation) avg_exp
      from sipr_maket_first_approve_2 sfa, person p
     where sfa.sicp_id = p.sicid
       and sfa.date_approve >= :y_from
       and sfa.date_approve <  :d_to
     group by substr(sfa.rfpm_id, 1, 4)
),
m as (
    select x.rfpm_m,
           count(distinct x.pncd_id) cnt,
           count(distinct case when x.sex = 1 then x.pncd_id end) cnt_m,
           count(distinct case when x.sex = 0 then x.pncd_id end) cnt_f
      from (select /*+parallel(4)*/
                   substr(d.rfpm_id, 1, 4) rfpm_m, d.pncd_id, p.sex
              from pnpd_document d, person p
             where d.pncd_id = p.sicid
               and d.pncp_date >= :y_from
               and d.pncp_date <  :d_to
               and d.ridt_id in (4, 6, 7, 8)
               and d.status in (0, 1, 2, 3, 5, 7)
               and d.pnsp_id > 0) x
     group by x.rfpm_m
)
select decode(s.rfpm, '0702', 'СВут', '0701', 'СВпк', '0703', 'СВпр',
                      '0704', 'СВбр', '0705', 'СВур', 'Неизвестно') nm,
       s.smd, s.payout_min, s.payout_max, s.avg_payout, s.avg_age, s.avg_exp,
       m.cnt, m.cnt_m, m.cnt_f
  from s, m
 where s.rfpm = m.rfpm_m
 order by decode(s.rfpm, '0702', 1, '0701', 2, '0703', 3, '0704', 4, '0705', 5, 6)
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, period_label=_period_label,
)
