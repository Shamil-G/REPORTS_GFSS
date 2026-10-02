# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 16. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_49_spool, Rep_app_49
# ============================================================
"""Приложение 49. Обращения и назначения социальных выплат из ГФСС, по
срокам рассмотрения (рабочие дни), в разрезе регионов.

Перенос REP_STAT_EXTEND.app_49_spool + Rep_app_49 (pck_utf8.sql,
7598-7887). Реестр: группа 1490, вызовы app_49_2k/_3hy/_4_9m/_5y('m') -
типы периода 2-5. Тип 1 у ЭТОЙ ветки не зарегистрирован и не имеет
подписи периода в Rep_app_49 (Begin-блок, строки 7877-7889, обрабатывает
только 2-5) - месячный вариант считается ДРУГОЙ парой процедур,
app_49_1_spool/Rep_app_49_1 (метрика "4 рабочих дня" вместо 15/30/>30,
см. migration-plan.md про группу 1490) - перенесён отдельно в app_49_1.py.
Тип 1 здесь включён по общему решению "все периоды доступны", с шаблоном
подписи по аналогии с типами 2-5 (в оригинале для него шаблона просто нет).

Заявление (`sipr_payer_maket_arc`) обрабатывается по всем действиям
(`actp_id`) для одного `sipr_id`: регион и дата подачи берутся из САМОГО
РАННЕГО действия (keep dense_rank first order by actp_id), последнее
состояние - из САМОГО ПОЗДНЕГО (keep ... last), "назначено" (is_appoint) -
если хотя бы одно действие имело state=3 и пустой rfcr_id, дата назначения
- дата САМОГО РАННЕГО такого действия. Рабочие дни (`cnt_wd`) - количество
дней с типом 'R' в `s_calendar` между датой подачи и датой назначения
(или датой подачи, если не назначено).

Порог "быстрого" назначения (15 vs 10 рабочих дней) зависит от года
отчёта: до 2014 - 15 дней, начиная с 2014 - 10 дней (строки 7658-7663).
Сам расчёт это учитывает (:rep_year в SQL), а вот ЗАГОЛОВОК колонки в
оригинале тоже менялся по году (строки 7818-7822) - здесь это НЕ
воспроизведено: заголовок зафиксирован на современном варианте "10 рабочих
дней", потому что заголовок колонки в build_report задаётся один раз при
импорте модуля, а не на каждый вызов (в отличие от report_name, для
которого есть text_params). Для отчётов за годы до 2014 заголовок будет
неточным, а числа - верными.

Смысл кодов состояния (`state` 3/5/8/11) и роли `rfcr_id` не
задокументирован в комментариях исходника - перенесено как есть, уточнить
у ДАУС при сверке.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.49'
report_name = ('Сведения об обращениях и назначениях социальных выплат '
               'из ГФСС{period}')

# Begin блок Rep_app_49 (строки 7877-7889) - типы 2-5 дословно; тип 1 в
# оригинале отсутствует, добавлен по аналогии (см. docstring).
_period_label = make_period_label({
    1: ', за {Month} месяц {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за 9 месяцев {year} года ',
    5: ', за {year} год ',
})

COLUMNS = [
    Col('Наименование региона', 'obl', 'text', 30),
    Col('Кол-во обращений', 'cnt_obr', 'int'),
    Col('Кол-во отказов в назначении', 'cnt_otcaz', 'int'),
    Col('Кол-во назначений', 'cnt_naz', 'int'),
    Group('из них назначено', [
        Col('в течение 10 рабочих дней', 'cnt_n15', 'int'),
        Col('в течение 30 рабочих дней', 'cnt_n30', 'int'),
        Col('более 30 рабочих дней', 'cnt_nmo30', 'int'),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :rep_year - год отчёта, только для порога 15/10 рабочих дней (см. docstring).
#
# app_raw - все действия (actp_id) по заявлениям за период.
# pp - одна строка на sipr_id: регион/дата подачи - из первого действия по
# actp_id, последнее состояние - из последнего, is_appoint/date_approve -
# по наличию действия с state=3 и пустым rfcr_id (keep(dense_rank ...)
# вместо оконных first_value/min ... over(), тот же результат проще).
STMT = """
with app_raw as (
    select ma.sipr_id, ma.actp_id, ma.state, ma.rfcr_id,
           substr(ma.rfbn_id, 1, 2) obl_raw,
           ap.date_calc
      from sipr_payer_maket_arc ma, siap_action_protocol ap
     where ma.actp_id = ap.actp_id
),
pp as (
    select sipr_id,
           min(obl_raw)   keep (dense_rank first order by actp_id) obl,
           min(date_calc) keep (dense_rank first order by actp_id) date_enter,
           max(case when state = 3 and rfcr_id is null then 1 else 0 end) is_appoint,
           min(case when state = 3 and rfcr_id is null then date_calc end) date_approve,
           max(state)     keep (dense_rank last  order by actp_id) last_state
      from app_raw
     group by sipr_id
    having min(date_calc) keep (dense_rank first order by actp_id) >= :d_from
       and min(date_calc) keep (dense_rank first order by actp_id) <  :d_to
),
wd as (
    select pp.sipr_id,
           count(case when c.pday_type = 'R' then 1 end) cnt_wd
      from pp, s_calendar c
     where c.pday between trunc(pp.date_enter)
                       and nvl(pp.date_approve, trunc(pp.date_enter))
     group by pp.sipr_id
),
agg as (
    select pp.obl                                                        obl,
           count(1)                                                       cnt_obr,
           sum(case when pp.is_appoint = 0 and pp.last_state in (3, 5, 8, 11)
                    then 1 end)                                           cnt_otcaz,
           sum(pp.is_appoint)                                             cnt_naz,
           sum(case when (:rep_year < 2014 and w.cnt_wd <= 15)
                      or (:rep_year >= 2014 and w.cnt_wd <= 10)
                    then pp.is_appoint end)                                cnt_n15,
           sum(case when (:rep_year < 2014 and w.cnt_wd > 15 and w.cnt_wd <= 30)
                      or (:rep_year >= 2014 and w.cnt_wd > 10 and w.cnt_wd <= 30)
                    then pp.is_appoint end)                                cnt_n30,
           sum(case when w.cnt_wd > 30 then pp.is_appoint end)             cnt_nmo30
      from pp, wd w
     where w.sipr_id(+) = pp.sipr_id
     group by pp.obl
)
select rr.name                obl,
       a.cnt_obr               cnt_obr,
       a.cnt_otcaz             cnt_otcaz,
       a.cnt_naz               cnt_naz,
       a.cnt_n15               cnt_n15,
       a.cnt_n30               cnt_n30,
       a.cnt_nmo30             cnt_nmo30
  from RFRG_REGION rr, agg a
 where a.obl(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label,
)
