# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3321 (процедура REP_R_3321).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения по лицам, зарегистрированным в качестве безработного, за период:
сколько обратилось за назначением СВпр (всего и по источникам подачи), сколько
не обратилось (с отчислениями за последние 24 месяца и без), сколько снято с
учёта, со стажем менее 6 месяцев, и распределение по предварительно рассчитанному
размеру выплаты.

Источник тот же, что у 3320: `sswh.v_lm_unemploy_ss_info` (регистрации в ЦЗ) +
`unemployed_calc` (расчёт) + `v_sipr_maket_first_approve_dn` (макет СВпр).
Соединения внешние и, как в 3320, собраны через подзапрос `ux` (одну
таблицу нельзя внешне соединять с двумя в синтаксисе `(+)`).

Считаются уникальные ИИН: все (`ca`); подавшие заявление (`id_sour` не пусто) -
всего и по источникам в порядке вывода оригинала: `sfaz` (`ZSP`, «ОЗиСП»),
`sfap` (`PEP`, «ПЭП»), `sfac` (`CON`, «ГК»); не обратившиеся (`id_sour` пусто) -
всего, без отчислений (`so = 0`), с отчислениями; снятые с учёта
(`regclosedate` не пусто); со стажем менее 6 месяцев (`nsu < 6`); а также
число не снятых с учёта по размеру расчёта `sum_calc` (0; от 0 до 1000;
1000-5000; 5000-10000; от 10000 и выше).

Шапка - из `SetPageHead`, три уровня. Название дословно, но «с» перед датой
кириллическая (в оригинале латинская «c»), «зарегистрированным» вместо
«зарегистрированные». Колонка «Номер» оригинала в данных не печаталась
(закомментирована).
В `AddCol` оригинала стоят табуляции в подписях и «0 тенге» - в
`SetPageHead` их нет, печаталось именно оно.

Объекты `v_lm_unemploy_ss_info`, `unemployed_calc`, `v_sipr_maket_first_approve_dn`
в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3321'
report_name = ('Сведения по лицам, зарегистрированным в качестве безработного '
               'с {period} года')

COLUMNS = [
    Col('Количество зарегистрированных лиц в качестве безработного', 'ca',
        'int', 22),
    Group('Обратившиеся за назначением СВпр', [
        Col('Всего:', 'sfaall', 'int', 12),
        Col('ОЗиСП', 'sfaz', 'int', 12),
        Col('ПЭП', 'sfap', 'int', 12),
        Col('ГК', 'sfac', 'int', 12),
    ]),
    Group('Не обратившиеся за назначением', [
        Col('Всего:', 'n', 'int', 12),
        Col('Нет СО за посл. 24 мес. перед регистрацией в качестве безработного',
            'n0', 'int', 28),
        Col('Есть СО за посл. 24 мес. перед регистрацией в качестве безработного',
            'n1', 'int', 28),
    ]),
    Col('Сняты с учета в качестве безработного', 'cls', 'int', 18),
    Col('Стаж участия менее 6 месяцев', 'stage', 'int', 18),
    Group('Есть СО за посл. 24 мес. перед регистрацией в качестве безработного', [
        Group('Предварительно рассчитанный размер', [
            Col('0 тенге', 's0', 'int', 12),
            Col('От 1 до 1000 тенге', 's1', 'int', 14),
            Col('От 1000 до 5000 тенге', 's2', 'int', 14),
            Col('От 5000 до 10 000 тенге', 's3', 'int', 14),
            Col('От 10 000 тенге и выше', 's4', 'int', 14),
        ]),
    ]),
]

# :d_from / :d_to - период из формы по дате регистрации, :d_to исключительная.
STMT = """
with ux as (
    select u.iin, u.regdate, u.regclosedate, u.unemployedcategorycode,
           uc.so, uc.sicid, uc.nsu, uc.sum_calc
      from sswh.v_lm_unemploy_ss_info u, unemployed_calc uc
     where u.regdate >= :d_from
       and u.regdate <  :d_to
       and u.iin     = uc.iin(+)
       and u.regdate = uc.regdate(+)
)
select count(distinct iin) ca,
       count(distinct case when id_sour is not null then iin else null end) sfaall,
       count(distinct case when id_sour = 'ZSP' then iin else null end) sfaz,
       count(distinct case when id_sour = 'PEP' then iin else null end) sfap,
       count(distinct case when id_sour = 'CON' then iin else null end) sfac,
       count(distinct case when id_sour is null then iin else null end) n,
       count(distinct case when id_sour is null and nvl(so, 0) = 0 then iin else null end) n0,
       count(distinct case when id_sour is null and nvl(so, 0) > 0 then iin else null end) n1,
       count(distinct case when regclosedate is not null then iin else null end) cls,
       count(distinct case when nsu < 6 then iin else null end) stage,
       sum(case when sum_calc = 0 and regclosedate is null then 1 else 0 end) s0,
       sum(case when sum_calc >= 0 and sum_calc < 1000 and regclosedate is null then 1 else 0 end) s1,
       sum(case when sum_calc >= 1000 and sum_calc < 5000 and regclosedate is null then 1 else 0 end) s2,
       sum(case when sum_calc >= 5000 and sum_calc < 10000 and regclosedate is null then 1 else 0 end) s3,
       sum(case when sum_calc >= 10000 and regclosedate is null then 1 else 0 end) s4
  from (select ux.iin, ux.regdate, ux.regclosedate, ux.unemployedcategorycode,
               ux.so, sfa.rfpm_id, sfa.id_sour, ux.nsu, ux.sum_calc
          from ux, v_sipr_maket_first_approve_dn sfa
         where sfa.sicp_id(+)   = ux.sicid
           and sfa.risk_date(+) = ux.regdate)
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
