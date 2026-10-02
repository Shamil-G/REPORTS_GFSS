# -*- coding: utf-8 -*-
# ============================================================
# УСТАРЕЛ - по сообщению Заказчика (02.10.2026).
# Закомментирован в model/list_reports.py (группа «Отчеты для Минтруда (REP_STAT_EXTEND)»), ключ 03. Код не удалён - для итоговой сверки.
# Oracle: REP_STAT_EXTEND.app_34_35_spool / Rep_app_34_35, ветка iRepNum='sex' (общая процедура с app_35, он остаётся)
# ============================================================
"""Приложение 34. Половозрастной состав участников СОСС (разрез "пол").

Перенос REP_STAT_EXTEND.app_34_35_spool + Rep_app_34_35(..., iRepNum='sex')
(pck_utf8.sql, 3143-3826). Реестр: группа 1340, вызов app_34_35_1m('sex','m')
и аналоги по всем типам периода, плюс app_34_35_7mn('sex','m') (тип 7).

app_34_35 - одна процедура с параметром iRepNum ('sex'/'age'), но SQL и набор
колонок для двух разрезов разные (age добавляет измерение "возраст" и читает
данные по-другому: substr(tag,1,1) вместо всего tag) - поэтому, как и с
app_49_1 (Prn_SP/Prn_SP_7), это два отдельных модуля: app_34.py (sex) и
app_35.py (age), а не флаг внутри одного.

Тип периода 7 ('7mn', Prn_SP7) в реестре зарегистрирован только для 'sex',
но переносить отдельную процедуру не нужно: Prn_SP7 отличается от Prn_SP
только тем, что читает EAV за диапазон date_spare from 1 to N при
date_type=1 (строка 3673: "t.date_spare between 1 and date_spare_"), то есть
де-факто это "с начала года по месяц N" - ровно то, что period_bounds(...,7,s)
и так возвращает (jan..начало месяца s+1). Решение "все 7 типов периода
доступны любому отчёту" (см. migration-plan.md) уже покрывает этот случай
без специального кода.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.34'
# Дословно из исходника (cSPTitle, строки 3325-3327 + сборка заголовка в
# Prn_SP, строка 3499): "Сведения о половозрастном " + cSPTitle + период.
# АО"Государственный фонд..." - без пробела перед кавычкой, как в оригинале.
report_name = ('Сведения о половозрастном составе участников системы '
               'обязательного социального страхования и суммах социальных '
               'отчислений, поступивших в АО"Государственный фонд '
               'социального страхования", за {period}')

_MONTH_WORD = {1: 'месяц', 2: 'месяца', 3: 'месяца', 4: 'месяца'}


def _month_word(s: int) -> str:
    # Дословно из PH_per для типа 7 (строки 3765-3768): 1 - "месяц",
    # 2-4 - "месяца", 5-12 - "месяцев".
    return _MONTH_WORD.get(s, 'месяцев')


# Подпись периода (Begin блок Rep_app_34_35, строки 3752-3771) - у каждого
# типа своя форма. Тип 1 без "за"; пробел между месяцем и годом добавлен
# сознательно для читаемости (в оригинале "Август2026" слитно). Тип 4 - с
# двойным пробелом (p_PH_per изначально null, ' ' || null || ' 9 месяцев '
# даёт два пробела) - оставлено дословно. Тип 7 подставляет словоформу
# количества месяцев отдельным шагом.
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


_COUNT = 'Число участников (человек)'
_SUM = 'Сумма социальных отчислений (тенге)'
_PEN = 'Пеня (тенге)'
_TOTAL = 'Всего'
_OF_WHICH = 'в том числе'
_M = 'мужчины'
_F = 'женщины'

COLUMNS = [
    Col('Области, города', 'reg', 'text', 30),
    Group(_COUNT, [
        Col(_TOTAL, 'cnt_all', 'int'),
        Group(_OF_WHICH, [
            Col(_M, 'cnt_m', 'int'),
            Col(_F, 'cnt_f', 'int'),
        ]),
    ]),
    Group(_SUM, [
        Col(_TOTAL, 'sum_all', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'sum_m', 'money', 18),
            Col(_F, 'sum_f', 'money', 18),
        ]),
    ]),
    Group(_PEN, [
        Col(_TOTAL, 'pen_all', 'money', 18),
        Group(_OF_WHICH, [
            Col(_M, 'pen_m', 'money', 18),
            Col(_F, 'pen_f', 'money', 18),
        ]),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# raw - строки si_member_2 за период как есть (без агрегации, как в
# оригинале - там p_sql строил построчный набор с оконными функциями).
# last_rnn/last_date - организация и дата последней выплаты человеку в
# периоде, с приоритетом knp='012' (decode(knp,'012',0,1) - строки
# 3200-3204), окно "rows between unbounded preceding and unbounded
# following" считает по всей группе, а не нарастающим итогом.
#
# located - регион организации на дату last_rnn/last_date: цепочка
# rfon_organization.bin -> cato_branch.code -> rfbn_id (строки 3216-3218),
# первые 2 символа - код региона; нет организации/региона -> '00'
# ("Не определен", строка 3376).
#
# agg/pivot - per-регион подсчёт уникальных людей (count distinct sicid,
# как в оригинале count(unique ...)) и сумм по полу и КНП: 012 - основные
# отчисления (количество + сумма), 017 - пеня (только сумма, строки
# 3283-3296).
STMT = """
with raw_member as (
    select /*+parallel(4)*/ a.sicid, a.knp, a.sum_pay,
           first_value(a.p_rnn) over (
               partition by a.sicid
               order by decode(a.knp, '012', 0, 1), a.pay_date_gfss desc
               rows between unbounded preceding and unbounded following) last_rnn,
           first_value(a.pay_date_gfss) over (
               partition by a.sicid
               order by decode(a.knp, '012', 0, 1), a.pay_date_gfss desc
               rows between unbounded preceding and unbounded following) last_date
    from si_member_2 a
    where a.pay_date_gfss >= :d_from
    and a.pay_date_gfss <  :d_to
),
member as (
    select /*+parallel(2)*/ r.sicid, r.knp, r.sum_pay, r.last_rnn, p.sex
    from raw_member r, person p
    where r.sicid = p.sicid(+)
),
located as (
    select /*+parallel(4)*/
           m.sicid, m.knp, m.sum_pay, m.sex,
           substr(nvl(br.rfbn_id, '00'), 1, 2) reg_id
    from member m, rfon_organization rf, cato_branch br
    where m.last_rnn = rf.bin(+)
    and rf.cato    = br.code(+)
),
agg as (
    select /*+parallel(4)*/
           reg_id, sex, knp,
           count(distinct sicid) cnt,
           sum(sum_pay)          summ
    from located
    group by reg_id, sex, knp
),
pivot as (
    select reg_id,
           sum(case when sex = 1 and knp = '012' then cnt  end) cnt_m,
           sum(case when sex = 0 and knp = '012' then cnt  end) cnt_f,
           sum(case when sex = 1 and knp = '012' then summ end) sum_m,
           sum(case when sex = 0 and knp = '012' then summ end) sum_f,
           sum(case when sex = 1 and knp = '017' then summ end) pen_m,
           sum(case when sex = 0 and knp = '017' then summ end) pen_f
    from agg
    group by reg_id
),
regions as (
    select rfrg_id reg_id, 0 ord from RFRG_REGION
    union all
    select '00', 1 from dual
)
select /*+parallel(4)*/
       nvl(rr.name, 'Не определен')         reg,
       nvl(v.cnt_m, 0) + nvl(v.cnt_f, 0)    cnt_all,
       nvl(v.cnt_m, 0)                      cnt_m,
       nvl(v.cnt_f, 0)                      cnt_f,
       nvl(v.sum_m, 0) + nvl(v.sum_f, 0)    sum_all,
       nvl(v.sum_m, 0)                      sum_m,
       nvl(v.sum_f, 0)                      sum_f,
       nvl(v.pen_m, 0) + nvl(v.pen_f, 0)    pen_all,
       nvl(v.pen_m, 0)                      pen_m,
       nvl(v.pen_f, 0)                      pen_f
from regions r, RFRG_REGION rr, pivot v
where rr.rfrg_id(+) = r.reg_id
and v.reg_id(+)   = r.reg_id
order by r.ord, r.reg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
)
