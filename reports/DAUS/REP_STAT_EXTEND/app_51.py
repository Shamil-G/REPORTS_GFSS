# -*- coding: utf-8 -*-
"""Приложение 51. Социальные выплаты по беременности и родам (СВбр, СВ
0704) в разрезе стажа участия (1-12 месяцев) и суммы назначенной выплаты
(14 денежных интервалов).

Перенос REP_STAT_EXTEND.app_51_spool + Rep_app_51 (pck_utf8.sql,
9456-10018). Реестр: группа 1510, вызов app_51_1m('m') и аналоги.

Это настоящая сводная таблица (кросс-таб), а не список строк с колонками-
метриками, как везде: КОЛОНКИ - это стаж (1..12 месяцев + "Всего"), а
СТРОК две категории:
  1. Две строки "Социальные отчисления" (сумма уплаченных / сумма,
     принятая к расчёту СВ) - по одной цифре на колонку стажа, просуммировано
     по ВСЕМ денежным интервалам.
  2. 15 денежных интервалов (0 = "СВБР, всего:" + 1-14 из группы group_sm) x
     3 строки метрик (Количество / Доля в % / Сумма выплаты) = 45 строк.

Поэтому и колонки, и правило "занижать нули" здесь другие, чем везде:
13 числовых колонок описаны одним и тем же kind='money' (как в оригинале -
Rep.AddCol в цикле 1..13 c cFmtCur для ВСЕХ колонок, даже когда в них
фактически лежит количество человек - строка 9974); соответствие "какая
строка что означает" - в первых двух текстовых колонках, а не в структуре
колонок. Строки блока 1 показывают 0, если данных нет (p_a по умолчанию 0,
строки 9788-9807); строки блока 2 показывают пусто (NULL) - кроме "Доля в
%", где по правилу оригинала (строка 9884: "if doly <> 0 then ... else
Rep.td('')") пустует ещё и точный ноль. Обе особенности воспроизведены на
уровне SQL (nvl(...,0) в блоке 1, nullif(...,0) в строке "Доля"), поэтому
blank_zero=False работает для всего отчёта разом.

СТАЖ (`staj`) - least(count_donation, 12), где `count_donation` считается
полем sipr_maket_first_approve_2 (число месяцев уплаты соц. отчислений,
явно не документировано в комментариях исходника - подлежит проверке на
базе при первой сверке).

ДЕДУПЛИКАЦИЯ БЕЗ ROW_NUMBER: оригинал соединяет sipr_maket_first_approve_2
с si_member_2 (по sicid, knp='012') и дальше с em5_sird_reckon_donation
(по mhmh_id/pmdl_n/sipr_id), из-за чего одна СВ-запись размножается на
много строк (по числу подходящих строк начислений и их "зачётов"). Чтобы
не досчитать sum_all и sum_pay лишний раз, оригинал переразмечает строки
row_number() over(...) и берёт только rn=1/rn_ip=1 - тот же результат даёт
обычная агрегация на нужном уровне детализации:
  - `person` - один ряд на sipr_id (сумма выплаты/стаж/интервал не зависят
    от размножения через si_member_2, поэтому exists вместо join);
  - `contrib` - один ряд на (sipr_id, mhmh_id, pmdl_n) для суммы отчислений
    (sum_pay), через max() - в оригинале дубли по этому ключу гарантированно
    одинаковы (иначе rn_ip=1 в оригинале был бы недетерминированным выбором
    одного из разных значений, что было бы багом там, а не здесь);
  - `donation` - СУММА sum_donation по всем подходящим строкам
    em5_sird_reckon_donation на человека (здесь дедупликации НЕТ и в
    оригинале - Sum(sum_donation) без rn-фильтра, строка 9587).

CUBE(staj, group_sm) считает разом детальные ячейки и обе линии итогов
(по стажу - строка "Всего" человек по всем интервалам; по интервалу -
колонка "Всего" по всем стажам) и их пересечение (общий итог) - это прямой
аналог того, что делает оригинал через фиксированные теги '13'+gr и
st+'00' (строки 9930-9951).

НЕ ПЕРЕНЕСЕНО (косметика): в оригинале между блоком "Социальные
отчисления" и блоком по интервалам есть одна пустая строка (Rep.tr; без
печати перед ней, строка 9825) - декоративный разделитель, без данных.
В Python-версии её нет: фреймворк рисует ровно по одной строке на запись
результата, вставлять пустую строку ради визуального отступа не стали.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.51'
report_name = ('Социальные выплаты по беременности и родам по назначенным '
               'социальным выплатам, за {period}')

# Begin блок Rep_app_51 (строки 9994-10008): все типы без ", за"-приставки,
# прямое присваивание. Тип 1 - с пробелом между месяцем и годом (тот же
# сознательный приём, что и в остальных отчётах раздела).
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

# Дословные подписи месяцев (p_PageHead, строки 9928-9941) - с русской
# формой множественного числа "месяц/месяца/месяцев", как в оригинале.
_MONTH_LABEL = {
    1: '1 месяц', 2: '2 месяца', 3: '3 месяца', 4: '4 месяца',
    5: '5 месяцев', 6: '6 месяцев', 7: '7 месяцев', 8: '8 месяцев',
    9: '9 месяцев', 10: '10 месяцев', 11: '11 месяцев', 12: '12 месяцев',
}

COLUMNS = [
    Col(' ', 'a1', 'text', 24),
    Col(' ', 'a2', 'text', 42),
    Group('Стаж участия, принятый для расчета СВбр', [
        *[Col(_MONTH_LABEL[n], f's{n}', 'money', 13) for n in range(1, 13)],
        Col('Всего', 's13', 'money', 14),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
_N = range(1, 14)  # 1..12 - стаж, 13 - "Всего" (nvl(staj, 13) из CUBE)


def _pivot(metric, alias):
    return ',\n           '.join(
        f'max(case when staj13 = {n} then {metric} end) {alias}{n}'
        for n in _N
    )


def _select_cols(alias):
    return ', '.join(f'{alias}{n}' for n in _N)


def _doly_cols():
    return ',\n       '.join(
        f'nullif(round(nvl(p.cnt{n}, 0) * 100 / nullif(p.cnt13, 0), 2), 0) d{n}'
        for n in _N
    )


STMT = f"""
with person as (
    select b.sipr_id,
           least(b.count_donation, 12) staj,
           case when b.sum_all <  100000 then 1
                when b.sum_all <  200000 then 2
                when b.sum_all <  300000 then 3
                when b.sum_all <  400000 then 4
                when b.sum_all <  500000 then 5
                when b.sum_all <  600000 then 6
                when b.sum_all <  700000 then 7
                when b.sum_all <  800000 then 8
                when b.sum_all <  900000 then 9
                when b.sum_all < 1000000 then 10
                when b.sum_all < 2000000 then 11
                when b.sum_all < 3000000 then 12
                when b.sum_all < 4000000 then 13
                else 14
           end group_sm,
           b.sum_all
      from sipr_maket_first_approve_2 b
     where b.date_approve >= :d_from
       and b.date_approve <  :d_to
       and substr(b.rfpm_id, 1, 4) = '0704'
       and exists (select 1 from si_member_2 ip
                    where ip.sicid = b.sicp_id and ip.knp = '012')
),
contrib as (
    select b.sipr_id, ip.mhmh_id, ip.pmdl_n,
           max(ip.sum_pay) sum_pay
      from sipr_maket_first_approve_2 b, si_member_2 ip
     where b.date_approve >= :d_from
       and b.date_approve <  :d_to
       and substr(b.rfpm_id, 1, 4) = '0704'
       and b.sicp_id = ip.sicid
       and ip.knp = '012'
     group by b.sipr_id, ip.mhmh_id, ip.pmdl_n
),
vznos as (
    select sipr_id, sum(sum_pay) sm_vznos
      from contrib
     group by sipr_id
),
donation as (
    select c.sipr_id, sum(rd.sum_donation) sm_ucht
      from contrib c, em5_sird_reckon_donation rd
     where rd.mhmh_id(+) = c.mhmh_id
       and rd.pmdl_n(+)  = c.pmdl_n
       and rd.sipr_id(+) = c.sipr_id
       and nvl(rd.is_calc, 'Y') = 'Y'
     group by c.sipr_id
),
per_person as (
    select p.staj, p.group_sm, p.sum_all,
           v.sm_vznos, d.sm_ucht
      from person p, vznos v, donation d
     where v.sipr_id(+) = p.sipr_id
       and d.sipr_id(+) = p.sipr_id
),
cube_agg as (
    select nvl(staj, 13)    staj13,
           nvl(group_sm, 0) grp,
           count(*)         cnt,
           sum(sum_all)     sm_all,
           sum(sm_vznos)    sm_vznos,
           sum(sm_ucht)     sm_ucht
      from per_person
     group by cube(staj, group_sm)
),
pivoted as (
    select grp,
           {_pivot('cnt', 'cnt')},
           {_pivot('sm_all', 'suma')},
           {_pivot('sm_vznos', 'vzn')},
           {_pivot('sm_ucht', 'ucht')}
      from cube_agg
     group by grp
),
grp_dim as (
    select level - 1 grp from dual connect by level <= 15
),
p as (
    select d.grp, v.*
      from grp_dim d, pivoted v
     where v.grp(+) = d.grp
)
-- Блок 1: "Социальные отчисления" - только группа-итог (grp=0), суммы за
-- весь период, никогда не пустует (nvl(...,0), строки 9788-9807 оригинала).
select 'Социальные отчисления' a1,
       'Сумма уплаченных социальных отчислений' a2,
       0 ord1, 0 ord2, 0 grp,
       {', '.join(f'nvl(vzn{n}, 0) s{n}' for n in _N)}
  from p where grp = 0
union all
select 'Социальные отчисления',
       'Сумма СО (принятые для расчета СВбр)',
       0, 1, 0,
       {', '.join(f'nvl(ucht{n}, 0) s{n}' for n in _N)}
  from p where grp = 0
-- Блок 2: 15 денежных интервалов (0 = "Всего") x 3 метрики.
union all
select case when p.grp = 0 then 'СВБР, всего:' else gs.sm end,
       'Количество назначенных СВбр',
       1, 0, p.grp,
       {_select_cols('cnt')}
  from p, group_sm gs
 where gs.id_sm(+) = to_char(p.grp, 'fm00')
union all
select case when p.grp = 0 then 'СВБР, всего:' else gs.sm end,
       'Доля в % к общему количеству получателей',
       1, 1, p.grp,
       {_doly_cols()}
  from p, group_sm gs
 where gs.id_sm(+) = to_char(p.grp, 'fm00')
union all
select case when p.grp = 0 then 'СВБР, всего:' else gs.sm end,
       'Сумма выплаты',
       1, 2, p.grp,
       {_select_cols('suma')}
  from p, group_sm gs
 where gs.id_sm(+) = to_char(p.grp, 'fm00')
order by ord1, grp, ord2
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=False, blank_zero=False,
    period_label=_period_label,
)
