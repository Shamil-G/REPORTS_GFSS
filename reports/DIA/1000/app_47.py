# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 14. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_47_spool, Rep_app_47
# ============================================================
"""Приложение 47. Участники СОСС по уровню дохода (в долях МЗП), в разрезе
пола.

Перенос REP_STAT_EXTEND.app_47_spool + Rep_app_47 (pck_utf8.sql, 6780-7210).
Реестр: группа 1470, все 6 типов периода зарегистрированы, включая тип 6
(24 месяца) - единственный отчёт из уже перенесённых с этим типом.

Доход по человеку - не сумма отчислений напрямую, а среднемесячный
коэффициент к МЗП: `cnt_mzp` (сумма по строкам с knp='012') делится на
`p_type` - число РАЗНЫХ месяцев начисления (count(distinct pay_month)) в
широком окне. Окно для `pay_date` на 2 месяца шире окна `pay_date_gfss`
(строка 6857: "отступаем 1 месяца..." - комментарий расходится с кодом,
там add_months(..,-2); код - источник истины). Итоговый коэффициент режется
на 12 корзин (<1, <2, ..., <10, =10, >10 МЗП) - строки 6857-6869.

Так как в новой архитектуре период задаётся один раз через :d_from/:d_to
(а не копится из EAV помесячно), группировка по `nummonth` в оригинале не
нужна: `nummonth` вычисляется из `pay_date_gfss`, а он и так уже ограничен
одним отчётным периодом - `nummonth` в пределах такого запроса всегда
константа, группировка по нему - no-op. Именно поэтому она не перенесена
(в отличие от `p_type`, который реально участвует в расчёте, а не только
маркирует помесячный срез).

СОЗНАТЕЛЬНОЕ ОТСТУПЛЕНИЕ: конверсия `between -> >=/< ` (принятое решение
проекта) применена и к `pay_date`, хотя в оригинале там тоже `between`, а
не только у главного периода.

Особенность вывода - НЕТ занижения нулей (blank_zero=False): PrnOneGoup
печатает Rep.td(значение) без проверки "<>0" (строки 7086-7094, в отличие
от почти всех остальных отчётов семейства). Пусто - только когда данных
по этой ячейке совсем нет (NULL), а не когда сумма ноль. При этом графа
"Всего" НЕ бывает пустой - она считается как sum(мужчины, женщины) с
подстановкой 0 за отсутствующих (строки 7075-7080: приращение p_all_c
происходит только при exists, то есть отсутствие эквивалентно 0 для суммы,
но не для самой ячейки муж/жен).

Люди, у которых знаменатель p_type равен исходному NULL-числителю (нет ни
одной строки knp='012' в окне - sum_k_doh IS NULL), не попадают ни в одну
явную корзину (case ничего не матчит) и группируются в "01" через
nvl(kat_mzp,1) - но при этом НЕ учитываются в кол-ве/сумме дохода этой
корзины (условие "kat_mzp is not null" в исходном SUM, строки 6849-6852),
хотя их пеня всё равно попадает в "01" (у peny условия по kat_mzp нет,
строки 6853-6854). Это сохранено дословно.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.47'
report_name = ('Количество участников СОСС, за которых уплачивались '
               'социальные отчисления хотя бы 1 раз в отчетном периоде, '
               'от уровня доходов, по состоянию на {period}')

# Begin блок Rep_app_47 (строки 7195-7209). Тип 6 (24 месяца) - известная
# ошибка оригинала: подпись дословно берёт слово "квартал", хотя период -
# 24 месяца, а не квартал (комментарий в коде тоже путает "24"/"25 месяца").
# Сохранено как есть - тексты официальной отчётности не поправляются.
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: '  9 месяцев {year} года ',
    5: ' {year} год ',
    6: '{n} квартал {year} года ',
})

_TOTAL = 'Всего'
_OF_WHICH = 'в том числе'
_M = 'мужчины'
_F = 'женщины'

COLUMNS = [
    Col('Размер дохода', 'razmer_doh', 'text', 30),
    Group('Кол-во участников (человек)*', [
        Col(_TOTAL, 'all_cnt', 'int'),
        Group(_OF_WHICH, [
            Col(_M, 'cnt_m', 'int'),
            Col(_F, 'cnt_w', 'int'),
        ]),
    ]),
    Group('Сумма социальных отчислений (тенге)', [
        Col(_TOTAL, 'all_sm', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'sm_m', 'money', 18),
            Col(_F, 'sm_w', 'money', 18),
        ]),
    ]),
    Group('Пеня (тенге)', [
        Col(_TOTAL, 'all_sp', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'sp_m', 'money', 18),
            Col(_F, 'sp_w', 'money', 18),
        ]),
    ]),
]

FOOTNOTE = (
    '* - участники системы обязательного социального страхования - лица, '
    'за которых в отчетном периоде была произведена уплата социальных '
    'отчислений, учтенные хотя бы 1 раз'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# member_win - строки si_member_2 в двойном окне: pay_date_gfss внутри
# отчётного периода (как обычно), pay_date - в расширенном на 2 месяца
# назад окне (строка 6858-6859 оригинала).
#
# per_person - на человека: p_type (число разных месяцев начисления),
# sum_k_doh (сумма коэффициентов МЗП по строкам knp=012), sm_peny (пеня,
# knp=017), sum_doh (сумма дохода, knp=012).
#
# bucketed - средний коэффициент МЗП (sum_k_doh/p_type) режется на 12
# корзин (строки 6857-6869), kat_mzp_raw - без подстановки nvl, чтобы
# ниже правильно исключить NULL-корзину из кол-ва/суммы, но не из пени.
STMT = """
with member_win as (
    select ff.sicid, ff.sum_pay, ff.knp, ff.pay_month, ff.cnt_mzp
      from si_member_2 ff
     where ff.pay_date_gfss >= :d_from
       and ff.pay_date_gfss <  :d_to
       and ff.pay_date       >= add_months(:d_from, -2)
       and ff.pay_date       <  :d_to
),
per_person as (
    select sicid,
           count(distinct pay_month)                                    p_type,
           sum(case when knp = '012' then nvl(round(cnt_mzp, 3), 0) end) sum_k_doh,
           sum(case when knp = '017' then sum_pay end)                  sm_peny,
           sum(case when knp = '012' then sum_pay end)                  sum_doh
      from member_win
     group by sicid
),
bucketed as (
    select pp.sm_peny, pp.sum_doh, pr.sex,
           case when pp.sum_k_doh / pp.p_type < 1  then 1
                when pp.sum_k_doh / pp.p_type < 2  then 2
                when pp.sum_k_doh / pp.p_type < 3  then 3
                when pp.sum_k_doh / pp.p_type < 4  then 4
                when pp.sum_k_doh / pp.p_type < 5  then 5
                when pp.sum_k_doh / pp.p_type < 6  then 6
                when pp.sum_k_doh / pp.p_type < 7  then 7
                when pp.sum_k_doh / pp.p_type < 8  then 8
                when pp.sum_k_doh / pp.p_type < 9  then 9
                when pp.sum_k_doh / pp.p_type < 10 then 10
                when pp.sum_k_doh / pp.p_type = 10 then 11
                when pp.sum_k_doh / pp.p_type > 10 then 12
           end kat_mzp_raw
      from per_person pp, person pr
     where pr.sicid = pp.sicid
),
agg as (
    select nvl(kat_mzp_raw, 1)                                             kat_mzp,
           sum(case when sex = '1' and kat_mzp_raw is not null then 1    end) cnt_m,
           sum(case when sex = '0' and kat_mzp_raw is not null then 1    end) cnt_w,
           sum(case when sex = '1' and kat_mzp_raw is not null then sum_doh end) sm_m,
           sum(case when sex = '0' and kat_mzp_raw is not null then sum_doh end) sm_w,
           sum(case when sex = '1' then sm_peny end)                          sp_m,
           sum(case when sex = '0' then sm_peny end)                          sp_w
      from bucketed
     group by nvl(kat_mzp_raw, 1)
)
select s.is_name                             razmer_doh,
       nvl(a.cnt_m, 0) + nvl(a.cnt_w, 0)      all_cnt,
       a.cnt_m                                cnt_m,
       a.cnt_w                                cnt_w,
       nvl(a.sm_m, 0) + nvl(a.sm_w, 0)        all_sm,
       a.sm_m                                 sm_m,
       a.sm_w                                 sm_w,
       nvl(a.sp_m, 0) + nvl(a.sp_w, 0)        all_sp,
       a.sp_m                                 sp_m,
       a.sp_w                                 sp_w
  from s_incominsize s, agg a
 where a.kat_mzp(+) = s.is_id
 order by s.is_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
