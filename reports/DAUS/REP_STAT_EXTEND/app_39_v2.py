# -*- coding: utf-8 -*-
"""Приложение 39 (v2). Коэффициент замещения дохода при потере кормильца
(СВ 0701), с выбором - учитывать ли ГСП.

Перенос REP_STAT_EXTEND.app_39_spool_v2 + Rep_app_39_v2 (pck_utf8.sql,
14739-15346). Реестр: группа 2290, вызов app_39_1m_v2('m') и аналоги.

Устройство - как у app_38_v2.py (см. там подробный разбор методологии
"среднее отношений", а не "отношение сумм", и про обязательный INNER join к
RFBS_BASE_SIZE независимо от режима ГСП). Здесь то же самое для СВ 0701
(потеря кормильца) и 4 групп по количеству иждивенцев вместо 3 по степени
утраты, плюс два отличия от app_39.py (v1):

  - фильтр `sum_all > 0`, который есть в v1, в v2 ЗАКОММЕНТИРОВАН в
    исходнике (строка 14822: "-- and s.sum_all > 0" - это PL/SQL-комментарий
    после закрывающей скобки строки, а не часть генерируемого SQL) -
    отрицательные суммы в v2 не отфильтровываются;
  - коэффициент ГСП по степени/группе (decode(substr(rfpm_id,-1),1,1.36,
    2,1.06,3,0.74), строка 14822) определён только для групп 1-3. Для
    группы 4 (4 и более иждивенцев) decode не имеет ветки и возвращает
    NULL - в режиме "с учётом ГСП" kof_per для всей группы 4 становится
    NULL (sum_all + pm*NULL = NULL), а значит kof4 не считается вообще.
    Это сохранено как есть, а не "исправлено" подстановкой похожего
    коэффициента - неизвестно, оговорка это в задании или сознательное
    решение (четвёртая группа неоднородна по числу иждивенцев, единого
    коэффициента для неё может не быть). Уточнить у ДАУС при сверке.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.39.V2'
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай потери кормильца в разрезе регионов, за '
               '{period}')

_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

_GROUPS = [
    ('1', 'c 1-иждевенцем'),
    ('2', 'c 2-иждевенцами'),
    ('3', 'c 3-иждевенцами'),
    ('4', 'c 4-иждевенцами и более'),
]


def _metric_group(suffix, title):
    return Group(title, [
        Col('Количество *(человек)', f'cnt{suffix}', 'int'),
        Col('Сумма назначенных размеров соц. выплат,**(тенге)',
            f'sm_all{suffix}', 'money', 18),
        Col('Средний размер назначенных соц. выплат ***(тенге)',
            f'avg_size{suffix}', 'avg', 18, avg_of=(f'sm_all{suffix}', f'cnt{suffix}')),
        Col('Среднемесяч. доход, принятый для исчисления выплат (тенге)',
            f'avg_smd{suffix}', 'avg', 20, avg_of=(f'sum_avg{suffix}', f'cnt{suffix}')),
        Col('К замещения ****, %',
            f'kof{suffix}', 'avg', 14, avg_of=(f'kof_num{suffix}', f'cnt{suffix}')),
    ])


COLUMNS = [
    Col('По утере кормильца', 'reg', 'text', 30),
    *[_metric_group(suffix, title) for suffix, title in _GROUPS],
    _metric_group('_t', 'Всего'),
]

# В v2 4 из 5 сносок закомментированы в исходнике (строки 15305-15308) -
# выводится только формула коэффициента (строка 15304).
FOOTNOTE = 'коэффициент (K) = (sum(расчет./доход))/колво.'

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :gsp - 'g' (с учётом ГСП) или 'n' (без учёта).
#
# gk считается только для групп 1-3 (case без ветки для '4' -> null) -
# отличие от app_38_v2.py, где групп было ровно 3 и decode покрывал все.
# Здесь для step_utr='4' gk остаётся null, и при :gsp='g' kof_per для этой
# группы null (см. docstring).
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           substr(s.rfpm_id, -1)   step_utr,
           s.sipr_id,
           s.sum_all,
           s.sum_avg,
           case when :gsp = 'g'
                then (s.sum_all + r.base_size *
                      decode(substr(s.rfpm_id, -1), 1, 1.36, 2, 1.06, 3, 0.74))
                     / nullif(s.sum_avg, 0)
                else s.sum_all / nullif(s.sum_avg, 0)
           end kof_per
      from sipr_maket_first_approve_2 s, RFBS_BASE_SIZE r
     where substr(s.rfpm_id, 1, 4) = '0701'
       and r.base_type = 2
       and trunc(s.date_approve) between r.date_beg and nvl(r.date_end, trunc(sysdate))
       and trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
),
agg as (
    select reg_id, step_utr,
           count(distinct sipr_id) cnt,
           sum(sum_all)            sm_all,
           sum(sum_avg)            sm_avg,
           sum(kof_per)            sm_kof
      from base
     group by reg_id, step_utr
),
pivot as (
    select reg_id,
           sum(case when step_utr = '1' then cnt    end) cnt1,
           sum(case when step_utr = '1' then sm_all  end) sm_all1,
           sum(case when step_utr = '1' then sm_avg  end) sm_avg1,
           sum(case when step_utr = '1' then sm_kof  end) sm_kof1,
           sum(case when step_utr = '2' then cnt    end) cnt2,
           sum(case when step_utr = '2' then sm_all  end) sm_all2,
           sum(case when step_utr = '2' then sm_avg  end) sm_avg2,
           sum(case when step_utr = '2' then sm_kof  end) sm_kof2,
           sum(case when step_utr = '3' then cnt    end) cnt3,
           sum(case when step_utr = '3' then sm_all  end) sm_all3,
           sum(case when step_utr = '3' then sm_avg  end) sm_avg3,
           sum(case when step_utr = '3' then sm_kof  end) sm_kof3,
           sum(case when step_utr = '4' then cnt    end) cnt4,
           sum(case when step_utr = '4' then sm_all  end) sm_all4,
           sum(case when step_utr = '4' then sm_avg  end) sm_avg4,
           sum(case when step_utr = '4' then sm_kof  end) sm_kof4
      from agg
     group by reg_id
)
select rr.name                                                  reg,
       nvl(v.cnt1, 0)                                            cnt1,
       nvl(v.sm_all1, 0)                                         sm_all1,
       nvl(v.sm_avg1, 0)                                         sum_avg1,
       case when nvl(v.cnt1, 0) > 0
            then v.sm_all1 / v.cnt1 else 0 end                   avg_size1,
       case when nvl(v.cnt1, 0) > 0
            then v.sm_avg1 / v.cnt1 else 0 end                   avg_smd1,
       case when nvl(v.cnt1, 0) > 0
            then (v.sm_kof1 / v.cnt1) * 100 else 0 end           kof1,
       nvl(v.sm_kof1, 0) * 100                                   kof_num1,
       nvl(v.cnt2, 0)                                            cnt2,
       nvl(v.sm_all2, 0)                                         sm_all2,
       nvl(v.sm_avg2, 0)                                         sum_avg2,
       case when nvl(v.cnt2, 0) > 0
            then v.sm_all2 / v.cnt2 else 0 end                   avg_size2,
       case when nvl(v.cnt2, 0) > 0
            then v.sm_avg2 / v.cnt2 else 0 end                   avg_smd2,
       case when nvl(v.cnt2, 0) > 0
            then (v.sm_kof2 / v.cnt2) * 100 else 0 end           kof2,
       nvl(v.sm_kof2, 0) * 100                                   kof_num2,
       nvl(v.cnt3, 0)                                            cnt3,
       nvl(v.sm_all3, 0)                                         sm_all3,
       nvl(v.sm_avg3, 0)                                         sum_avg3,
       case when nvl(v.cnt3, 0) > 0
            then v.sm_all3 / v.cnt3 else 0 end                   avg_size3,
       case when nvl(v.cnt3, 0) > 0
            then v.sm_avg3 / v.cnt3 else 0 end                   avg_smd3,
       case when nvl(v.cnt3, 0) > 0
            then (v.sm_kof3 / v.cnt3) * 100 else 0 end           kof3,
       nvl(v.sm_kof3, 0) * 100                                   kof_num3,
       nvl(v.cnt4, 0)                                            cnt4,
       nvl(v.sm_all4, 0)                                         sm_all4,
       nvl(v.sm_avg4, 0)                                         sum_avg4,
       case when nvl(v.cnt4, 0) > 0
            then v.sm_all4 / v.cnt4 else 0 end                   avg_size4,
       case when nvl(v.cnt4, 0) > 0
            then v.sm_avg4 / v.cnt4 else 0 end                   avg_smd4,
       case when nvl(v.cnt4, 0) > 0 and v.sm_kof4 is not null
            then (v.sm_kof4 / v.cnt4) * 100 else 0 end           kof4,
       nvl(v.sm_kof4, 0) * 100                                   kof_num4,
       nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) + nvl(v.cnt4, 0)
                                                                  cnt_t,
       nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0)
         + nvl(v.sm_all4, 0)                                     sm_all_t,
       nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0)
         + nvl(v.sm_avg4, 0)                                     sum_avg_t,
       case when nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0) > 0
            then (nvl(v.sm_all1,0)+nvl(v.sm_all2,0)+nvl(v.sm_all3,0)+nvl(v.sm_all4,0))
               / (nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0))
            else 0 end                                           avg_size_t,
       case when nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0) > 0
            then (nvl(v.sm_avg1,0)+nvl(v.sm_avg2,0)+nvl(v.sm_avg3,0)+nvl(v.sm_avg4,0))
               / (nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0))
            else 0 end                                           avg_smd_t,
       case when nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0) > 0
            then ((nvl(v.sm_kof1,0)+nvl(v.sm_kof2,0)+nvl(v.sm_kof3,0)+nvl(v.sm_kof4,0))
                / (nvl(v.cnt1,0)+nvl(v.cnt2,0)+nvl(v.cnt3,0)+nvl(v.cnt4,0))) * 100
            else 0 end                                           kof_t,
       (nvl(v.sm_kof1,0)+nvl(v.sm_kof2,0)+nvl(v.sm_kof3,0)+nvl(v.sm_kof4,0)) * 100
                                                                  kof_num_t
  from RFRG_REGION rr, pivot v
 where v.reg_id(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label, footnote=FOOTNOTE,
)
