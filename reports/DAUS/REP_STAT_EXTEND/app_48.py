# -*- coding: utf-8 -*-
"""Приложение 48. Участники СОСС по стажу участия (в месяцах, окно 24
месяца), в разрезе пола.

Перенос REP_STAT_EXTEND.app_48_spool + Rep_app_48_24m (pck_utf8.sql,
7269-7590). Реестр: группа 1480, зарегистрирован ТОЛЬКО тип периода 6
(24 месяца) - единственный вызов app_48_24m('m'). В самом пакете остальные
типы прямо отключены (case для LTD_rep, строки 7346-7351, ветки 2-5
закомментированы), и Rep_app_48_24m не проверяет iDate_type вообще -
подпись периода строится одной и той же строкой всегда (см. ниже).

По общему решению проекта ("все 7 типов периода доступны любому отчёту")
остальные типы здесь всё равно включены через PERIOD_24M, хотя семантика
"стажа участия" при коротких периодах не такая наглядная, как при 24
месяцах (окно `pay_date` в SQL всё равно масштабируется period_bounds под
выбранный тип - формула та же, что и в оригинале, просто с другими
границами).

СТАЖ УЧАСТИЯ (`stag_uch`, строки 7311-7317) - не текущий период, а сколько
РАЗНЫХ месяцев начисления (`count(distinct pay_month)`) нашлось у человека
в широком окне `pay_date` (от начала периода минус 1 месяц до конца, строка
7343: "and f.pay_date between add_months(:p_DateB, -1) and :p_DatE" -
опечатка в имени бинда `p_DateB` вместо `p_DatB` не влияет на результат:
в native dynamic SQL это позиционный, а не именованный бинд). Бакеты: <13,
<24, <36, <48, <60, >=60 месяцев - 6 групп, справочник `s_standopar`.

Кол-во участников (`cnt`) - фактически индикатор 0/1 на человека: "была ли
хотя бы одна строка knp=012 с pay_date_gfss в пределах периода" (в
оригинале выражено как count(distinct sicid) по условному case, что для
одного человека даёт 0 или 1 - здесь эквивалентно max(case...)). Сумма
СО/пени (`sum24_so`/`sum24_peny`) считаются в ТОМ ЖЕ периоде (pay_date_gfss
>= :d_from), а не в широком окне для стажа - две разные границы внутри
одного запроса, сохранены как в оригинале.

Фильтр `x.sum24_peny + x.sum24_so > 0` (строка 7345) - исключает людей без
СО/пени в периоде (даже если стаж по широкому окну есть).

Как и app_47: НЕТ занижения нулей (blank_zero=False, PrnOneGoup печатает
значения без проверки "<>0", строки 7480-7488).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.48'
report_name = ('Количество участников СОСС, за которых уплачивались '
               'социальные отчисления хотя бы 1 раз за 24 календарных '
               'месяца, от стажа участия')

# Begin блок Rep_app_48_24m (строка 7583) - ОДНА строка без разбора по
# iDate_type: подпись периода всегда "квартал", даже если бы отчёт вызвали
# с другим типом (в реестре этого не бывает, но per_ent-политика проекта
# держит остальные типы доступными). Дословно воспроизведено для всех
# типов - это не ошибка переноса, а точная копия безусловного оригинала.
_period_label = make_period_label({t: ', за {n} квартал {year} года '
                                   for t in range(1, 8)})

_TOTAL = 'Всего'
_OF_WHICH = 'в том числе'
_M = 'мужчины'
_F = 'женщины'

COLUMNS = [
    Col('Стаж участия, месяцев', 'staj', 'text', 24),
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
# member_win - строки si_member_2 в широком окне для расчёта стажа: верхняя
# граница pay_date_gfss < :d_to (эквивалент "<= p_DatE" оригинала при
# открытом интервале), pay_date в [d_from-1 месяц, d_to).
#
# per_person - на человека: cnt_so (число разных месяцев начисления в
# широком окне - основа для бакета стажа), cnt_flag (был ли хотя бы один
# knp=012 в САМОМ периоде, не в широком окне), sum24_so/sum24_peny (суммы
# СО/пени тоже в самом периоде).
STMT = """
with member_win as (
    select f.sicid, f.knp, f.pay_month, f.pay_date_gfss, f.sum_pay
      from si_member_2 f
     where f.pay_date_gfss <  :d_to
       and f.pay_date       >= add_months(:d_from, -1)
       and f.pay_date       <  :d_to
),
per_person as (
    select sicid,
           count(distinct pay_month)                                        cnt_so,
           max(case when knp = '012' and pay_date_gfss >= :d_from
                    then 1 else 0 end)                                       cnt_flag,
           sum(case when knp = '017' and pay_date_gfss >= :d_from
                    then sum_pay else 0 end)                                 sum24_peny,
           sum(case when knp = '012' and pay_date_gfss >= :d_from
                    then sum_pay else 0 end)                                 sum24_so
      from member_win
     group by sicid
    having sum(case when knp = '017' and pay_date_gfss >= :d_from
                     then sum_pay else 0 end)
         + sum(case when knp = '012' and pay_date_gfss >= :d_from
                     then sum_pay else 0 end) > 0
),
bucketed as (
    select pr.sex,
           pp.cnt_flag, pp.sum24_so, pp.sum24_peny,
           case when pp.cnt_so < 13 then 1
                when pp.cnt_so < 24 then 2
                when pp.cnt_so < 36 then 3
                when pp.cnt_so < 48 then 4
                when pp.cnt_so < 60 then 5
                when pp.cnt_so >= 60 then 6
           end stag_uch
      from per_person pp, person pr
     where pr.sicid = pp.sicid
),
agg as (
    select stag_uch,
           sum(case when sex = '1' then cnt_flag  end) cnt_m,
           sum(case when sex = '0' then cnt_flag  end) cnt_w,
           sum(case when sex = '1' then sum24_so  end) sm_m,
           sum(case when sex = '0' then sum24_so  end) sm_w,
           sum(case when sex = '1' then sum24_peny end) sp_m,
           sum(case when sex = '0' then sum24_peny end) sp_w
      from bucketed
     group by stag_uch
)
select s.sop_name                             staj,
       nvl(a.cnt_m, 0) + nvl(a.cnt_w, 0)      all_cnt,
       a.cnt_m                                 cnt_m,
       a.cnt_w                                 cnt_w,
       nvl(a.sm_m, 0) + nvl(a.sm_w, 0)        all_sm,
       a.sm_m                                  sm_m,
       a.sm_w                                  sm_w,
       nvl(a.sp_m, 0) + nvl(a.sp_w, 0)        all_sp,
       a.sp_m                                  sp_m,
       a.sp_w                                  sp_w
  from s_standopar s, agg a
 where a.stag_uch(+) = s.sop_id
 order by s.sop_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
