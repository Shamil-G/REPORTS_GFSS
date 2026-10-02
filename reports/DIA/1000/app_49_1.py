# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 17. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_49_1_spool, Rep_app_49_1
# ============================================================
"""Приложение 49 (вариант "4 рабочих дня"). Обращения и назначения СВ по
срокам рассмотрения, метрика "4 рабочих дня со дня отправления в ГФСС", в
разрезе региона и вида риска.

Перенос REP_STAT_EXTEND.app_49_1_spool + Rep_app_49_1 (pck_utf8.sql,
7930-8717). Реестр: та же группа 1490, что у app_49.py, но вызовы
app_49_1_1m('m') (тип 1) и app_49_1_7mn('m') (тип 7) - типы 2-5 у ЭТОЙ
ветки в реестре не зарегистрированы (принадлежат app_49.py), хотя
Rep_app_49_1 их технически обрабатывает (Prn_SP против Prn_SP_7 - тот же
приём, что у app_34_35: два вывода на разные типы периода, здесь не
понадобился, т.к. один SQL-запрос с :d_from/:d_to покрывает оба).

Главное отличие от app_49.py - не просто регион, а регион x вид риска (5
видов СВ), и метрика "назначено в течение 4 рабочих дней" считается не от
даты подачи, а от даты ОТПРАВКИ В ГФСС (date_send_gfss, state=2 с пустым
rfcr_id) до даты назначения, отдельно "без доработок" (is_regfss=0) и "с
доработками" (is_regfss>=1, т.е. было хотя бы одно действие state=60 -
"регистрация в ГФСС"). Плюс те же n30/nmo30, что в app_49.py, но окно
для них отсчитывается от подачи до ПЕРВОГО назначения (date_first_approve),
а не от подачи до одобрения вообще - в app_49.py где назначение только одно,
эта разница неощутима, здесь есть и first, и last (см. ниже).

Зануление здесь ДРУГОЕ, чем в app_49.py: PrnOneGoup показывает 0 явно в
ELSE-ветке (строки 8228-8300, "Rep.td(0)"), а не пропускает ячейку - то
есть отсутствие данных и настоящий ноль неразличимы, всё всегда число.

НЕ ПЕРЕНЕСЕНО (узкий исторический случай, строки 7969-7976): для
rep_year=2016 и типа периода 7 отчёт в оригинале начинается с марта 2016
(не с расчётной даты) - в PL/SQL это правка вручную под конкретный год.
Здесь эта поправка не воспроизведена: период считается обычной формулой
period_bounds() для любого года. Если понадобится сверка именно 2016 года
по этому отчёту типа 7 - разница ожидаема и это её причина.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.49.1'
report_name = ('Сведения об обращениях и назначениях социальных выплат '
               'из ГФСС{period}')

_MONTH_WORD = {1: 'месяц', 2: 'месяца', 3: 'месяца', 4: 'месяца'}


def _month_word(s: int) -> str:
    return _MONTH_WORD.get(s, 'месяцев')


# Begin блок Rep_app_49_1 (строки 8686-8710) - текстуально совпадает с
# app_34_35 (тип 1 без "за", пробел между месяцем и годом добавлен для
# читаемости; тип 4 - с двойным пробелом; тип 7 - словоформа количества
# месяцев).
_base_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: '  9 месяцев {year} года ',
    5: ' {year} год ',
    7: ' {n} MONTHWORD {year} год ',
})


def _period_label(rep_year, date_type, date_start=None):
    label = _base_label(rep_year, date_type, date_start)
    if int(date_type) == 7:
        label = label.replace('MONTHWORD', _month_word(int(date_start)))
    return label


COLUMNS = [
    Col('Регион', 'obl', 'text', 26),
    Col('Вид риска', 'rfpm_name', 'text', 22),
    Col('Кол-во обращений', 'cnt_obr', 'int'),
    Col('Кол-во отказов', 'cnt_otcaz', 'int'),
    Col('Кол-во назначенных', 'cnt_naz', 'int'),
    Group('Со дня отправления в ГФСС', [
        Group('Без доработок', [
            Col('В течении 4-х рабочих дней', 'cnt_n4_gfss', 'int'),
            Col('Более 4-х рабочих дней', 'cnt_mon4_gfss', 'int'),
        ]),
        Group('С доработками', [
            Col('В течении 4-х рабочих дней', 'cnt_n4_gfss_dor', 'int'),
            Col('Более 4-х рабочих дней', 'cnt_mon4_gfss_dor', 'int'),
        ]),
    ]),
    Group('Назначено со дня риска', [
        Col('В течении 30', 'cnt_n30', 'int'),
        Col('Более 30', 'cnt_nmo30', 'int'),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# app_raw - все действия по заявлениям (0701-0705) за период.
# pp - одна строка на sipr_id: регион/дата подачи/rfpm - из первого
# действия по actp_id (keep dense_rank first), is_regfss - было ли хотя бы
# одно действие "регистрация в ГФСС" (state=60), date_send_gfss - дата
# ПОСЛЕДНЕЙ отправки в ГФСС (state=2, rfcr_id пуст), date_last_approve -
# дата ПОСЛЕДНЕГО назначения, date_first_approve - дата ПЕРВОГО назначения
# (все три - state=3, rfcr_id пуст).
#
# wd1 - рабочие дни от подачи до первого назначения (или отправки в ГФСС,
# если назначения не было) - знаменатель для n30/nmo30.
# wd2 - рабочие дни от отправки в ГФСС до последнего назначения (или до
# отправки, если не назначено) - знаменатель для n4_gfss*.
STMT = """
with app_raw as (
    select ma.sipr_id, ma.actp_id, ma.state, ma.rfcr_id,
           substr(ma.rfbn_id, 1, 2) obl_raw,
           substr(ma.rfpm_id, 1, 4) rfpm_raw,
           ap.date_calc
      from sipr_payer_maket_arc ma, siap_action_protocol ap
     where ma.actp_id = ap.actp_id
       and substr(ma.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
),
pp as (
    select sipr_id,
           min(obl_raw)    keep (dense_rank first order by actp_id) obl,
           min(rfpm_raw)   keep (dense_rank first order by actp_id) rfpm,
           min(date_calc)  keep (dense_rank first order by actp_id) date_enter,
           max(case when state = 60 then 1 else 0 end)               is_regfss,
           max(case when state = 3 and rfcr_id is null then 1 else 0 end) is_appoint,
           max(case when state = 2 and rfcr_id is null then date_calc end) date_send_gfss,
           max(case when state = 3 and rfcr_id is null then date_calc end) date_last_approve,
           min(case when state = 3 and rfcr_id is null then date_calc end) date_first_approve,
           max(state)      keep (dense_rank last  order by actp_id) last_state
      from app_raw
     group by sipr_id
    having min(date_calc) keep (dense_rank first order by actp_id) >= :d_from
       and min(date_calc) keep (dense_rank first order by actp_id) <  :d_to
),
wd1 as (
    select pp.sipr_id,
           count(case when c.pday_type = 'R' then 1 end) cnt_wd
      from pp, s_calendar c
     where c.pday between trunc(pp.date_enter)
                       and nvl(pp.date_first_approve, trunc(nvl(pp.date_send_gfss, pp.date_enter)))
     group by pp.sipr_id
),
wd2 as (
    select pp.sipr_id,
           count(case when c.pday_type = 'R' then 1 end) cnt_wd_gfss
      from pp, s_calendar c
     where pp.date_send_gfss is not null
       and c.pday between trunc(pp.date_send_gfss)
                       and nvl(pp.date_last_approve, trunc(pp.date_send_gfss))
     group by pp.sipr_id
),
agg as (
    select pp.obl, pp.rfpm,
           count(1)                                                        cnt_obr,
           sum(case when pp.is_appoint = 0 and pp.last_state in (3, 5, 8, 11)
                    then 1 end)                                            cnt_otcaz,
           sum(pp.is_appoint)                                              cnt_naz,
           sum(case when w2.cnt_wd_gfss <= 4 and pp.is_regfss = 0
                    then pp.is_appoint end)                                cnt_n4_gfss,
           sum(case when w2.cnt_wd_gfss > 4 and pp.is_regfss = 0
                    then pp.is_appoint end)                                cnt_mon4_gfss,
           sum(case when w2.cnt_wd_gfss <= 4 and pp.is_regfss >= 1
                    then pp.is_appoint end)                                cnt_n4_gfss_dor,
           sum(case when w2.cnt_wd_gfss > 4 and pp.is_regfss >= 1
                    then pp.is_appoint end)                                cnt_mon4_gfss_dor,
           sum(case when w1.cnt_wd <= 30 then pp.is_appoint end)           cnt_n30,
           sum(case when w1.cnt_wd > 30 then pp.is_appoint end)            cnt_nmo30
      from pp, wd1 w1, wd2 w2
     where w1.sipr_id(+) = pp.sipr_id
       and w2.sipr_id(+) = pp.sipr_id
     group by pp.obl, pp.rfpm
)
select rr.name                    obl,
       rp.name                    rfpm_name,
       nvl(a.cnt_obr, 0)          cnt_obr,
       nvl(a.cnt_otcaz, 0)        cnt_otcaz,
       nvl(a.cnt_naz, 0)          cnt_naz,
       nvl(a.cnt_n4_gfss, 0)      cnt_n4_gfss,
       nvl(a.cnt_mon4_gfss, 0)    cnt_mon4_gfss,
       nvl(a.cnt_n4_gfss_dor, 0)  cnt_n4_gfss_dor,
       nvl(a.cnt_mon4_gfss_dor, 0) cnt_mon4_gfss_dor,
       nvl(a.cnt_n30, 0)          cnt_n30,
       nvl(a.cnt_nmo30, 0)        cnt_nmo30
  from RFRG_REGION rr,
       (select '0701' rfpm_id from dual union all
        select '0702' from dual union all
        select '0703' from dual union all
        select '0704' from dual union all
        select '0705' from dual) v,
       rfpm_payments rp,
       agg a
 where rp.rfpm_id = v.rfpm_id
   and a.obl(+)  = rr.rfrg_id
   and a.rfpm(+) = v.rfpm_id
 order by rr.rfrg_id, v.rfpm_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label,
)
