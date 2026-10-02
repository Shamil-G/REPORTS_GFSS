# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Actuar», отчёт 714 (процедура Rep_Actuar_14).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Средняя продолжительность (факт) осуществления социальных выплат получателям
по утрате трудоспособности: по коэффициенту утраты трудоспособности (КУТ)
число получателей и средняя продолжительность в месяцах, отдельно мужчины и
женщины, для «новых» получателей (расчёт назначения в периоде) и для «всех».

Источник - `payment_history` (месяц конца периода, вид 0702) + `sifl_file` +
`sipr_payer` + `person`. Продолжительность - `months_between(least(конец,
nvl(stop_date, конец)), appoint_date)`. Дата расчёта назначения - скалярный
подзапрос по `siap_action_protocol` (`rownum = 1`, как в оригинале). КУТ - последняя
цифра вида: 1 -> 0,7, 2 -> 0,5, 3 -> 0,3. Пол: '1' - мужчины, '0' - женщины.
Итоги по колонкам «Кол-во».

Конец периода, как в оригинале, сдвигается на конец месяца
(`last_day(p_EndDate)`) - в запросе `last_day(:d_to - 1)`, а в названии
печатается уже этот день. Обе даты задаются в форме (в оригинале пустые
заменялись «по сегодня» и «год назад»).

Таблицы `sipr_payer`, `sifl_file`, `payment_history` в тестовой reports_test
доступны не все (`sipr_payer_arc`, `siap_action_protocol` - нет): на данных
отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '714'
report_name = ('Средняя продолжительность осуществления социальных выплат '
               'получателям по утрате трудоспособности\n'
               'за период с {date_from} по {date_to_eom}')

_CNT = 'Кол-во'
_AVG = 'Ср. продолжительность, мес'


def _sexes(prefix):
    return [
        Group('Мужчины', [Col(_CNT, f'cnt_{prefix}_m', 'int', 12),
                          Col(_AVG, f'avg_{prefix}_m', 'money', 16, total=False)]),
        Group('Женщины', [Col(_CNT, f'cnt_{prefix}_f', 'int', 12),
                          Col(_AVG, f'avg_{prefix}_f', 'money', 16, total=False)]),
    ]


COLUMNS = [
    Col('Коэффициент утраты трудоспособности', 'kut', 'center', 22),
    Group('Для "новых" получателей', _sexes('new')),
    Group('Для "всех" получателей', _sexes('all')),
]

# :d_from - начало периода; конец - last_day(:d_to - 1) (конец месяца даты «по»).
STMT = """
select to_char(decode(gr_i, '1', 0.7, '2', 0.5, '3', 0.3), 'FM0D0') kut,
       count(case when sex = '1' and in_date >= :d_from
                       and in_date < last_day(:d_to - 1) + 1 then 1 end) cnt_new_m,
       avg(case when sex = '1' and in_date >= :d_from
                     and in_date < last_day(:d_to - 1) + 1 then mnt end) avg_new_m,
       count(case when sex = '0' and in_date >= :d_from
                       and in_date < last_day(:d_to - 1) + 1 then 1 end) cnt_new_f,
       avg(case when sex = '0' and in_date >= :d_from
                     and in_date < last_day(:d_to - 1) + 1 then mnt end) avg_new_f,
       count(decode(sex, '1', 1)) cnt_all_m, avg(decode(sex, '1', mnt)) avg_all_m,
       count(decode(sex, '0', 1)) cnt_all_f, avg(decode(sex, '0', mnt)) avg_all_f
  from (select substr(h.rfpm_id, -1) gr_i, pr.sex,
               months_between(least(last_day(:d_to - 1),
                                    nvl(p.stop_date, last_day(:d_to - 1))),
                              p.appoint_date) mnt,
               (select /*+index (pa xp_sipr_payer_arc)*/ ap.date_calc
                  from sipr_payer_arc pa, siap_action_protocol ap
                 where pa.sipr_id = p.sipr_id
                   and p.actp_id = ap.actp_id
                   and rownum = 1) in_date
          from payment_history h, sifl_file f, sipr_payer p, person pr
         where h.act_month = trunc(:d_to - 1, 'month')
           and h.rfpm_id like '0702%'
           and h.pnpt_id = f.sifl_id
           and f.sipr_id = p.sipr_id
           and p.sicp_id = pr.sicid)
 group by gr_i
 order by gr_i
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
)
