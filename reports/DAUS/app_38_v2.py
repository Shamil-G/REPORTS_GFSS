# -*- coding: utf-8 -*-
"""Приложение 38 (v2). Коэффициент замещения дохода при утрате
трудоспособности (СВ 0702), с выбором - учитывать ли ГСП.

Перенос REP_STAT_EXTEND.app_38_spool_v2 + Rep_app_38_v2 (pck_utf8.sql,
14116-14661). Реестр: группа 2280, вызов app_38_1m_v2('m') и аналоги по
типам периода 1-5. Третий параметр формы (Rep.ParAsNumb(3): 1 -> 'g' - с
учётом ГСП, 2 -> 'n' - без учёта) здесь - обычное поле формы (util.GSP).

Это НЕ версия взамен app_38.py: оба зарегистрированы и живы одновременно
(1380 и 2280) - два разных отчёта. Главное отличие - формула коэффициента
замещения:

  - app_38 (v1): К = (Σ сумма СВ / Σ доход) * 100 - отношение СУММ по
    региону+степени (app_38_spool, строка 4640: "sm_all / sm_avg" уже после
    Sum() по группе).
  - app_38_v2: К = (Σ по каждой отдельной выплате (сумма_i [+ГСП] / доход_i))
    / количество * 100 - СРЕДНЕЕ отношений по каждому получателю (kof_per
    считается ДО группировки, строка 14186-14188, затем Sum(kof_per)/cnt в
    итоговом select, строка 14168). Это две разные статистики, не опечатка -
    сохранены обе дословно, каждая в своём модуле.

С учётом ГСП (iTypRep='g') к сумме выплаты добавляется base_size (текущий
размер ГСП на дату, RFBS_BASE_SIZE.base_type=2) умноженный на коэффициент
по степени утраты (decode: 1->1.36, 2->1.06, 3->0.74, строка 14196). Без
учёта (iTypRep='n') это слагаемое не добавляется, но join к RFBS_BASE_SIZE
всё равно обязателен (INNER, строка 14208-14210) - запись без подходящей
строки ГСП на дату выпадает из отчёта в ОБОИХ режимах. Это сохранено как
есть: не понятно, баг это или расчёт намеренно ограничен периодами
действия ГСП, уточнить у ДАУС при сверке.

СОЗНАТЕЛЬНОЕ ОТСТУПЛЕНИЕ - то же, что в app_38.py (см. там подробно): в
оригинале строка региона копит помесячные отношения из EAV без пересчёта, и
только строка "По республике" считает правильно. Здесь правильная формула
(here - среднее отношений по каждой выплате, а не по каждому месяцу)
применяется к каждой строке региона и последовательно продолжается в
итоговой строке через avg_of, а не переключается на другую формулу, как в
оригинале (строки 4894-4896 у v1 использовали ratio-сумм даже для v2 -
здесь везде среднее отношений, единообразно).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.38.V2'
report_name = ('Коэффициент (К) замещения дохода получателей социальных '
               'выплат на случай утраты трудоспособности в разрезе '
               'регионов, за {period}')

# Тот же Begin-блок, что у app_38.py (строки 14643-14658 - дословное
# повторение 5080-5092).
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: '{n} квартал {year} года ',
    3: '{n} полугодие {year} года ',
    4: ' 9 месяцев {year} года ',
    5: '{year} год ',
})

_STEPS = [
    ('1', 'степень утраты общей трудоспособности от 80% до 100%'),
    ('2', 'степень утраты общей трудоспособности от 60% до 80%'),
    ('3', 'степень утраты общей трудоспособности от 30% до 60%'),
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
    Col('По утрате трудоспособности', 'reg', 'text', 30),
    *[_metric_group(suffix, title) for suffix, title in _STEPS],
    _metric_group('_t', 'Всего'),
]

# В v2 4 из 5 сносок закомментированы в исходнике (строки 14636-14639,
# /* ... */) - выводится только формула коэффициента (строка 14634).
FOOTNOTE = 'коэффициент (K) = (sum(расчет./доход))/колво.'

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :gsp - 'g' (с учётом ГСП) или 'n' (без учёта), обычный параметр формы.
#
# base - строки sipr_maket_first_approve_2 с кодом 0702 за период, ОБЯЗАТЕЛЬНО
# с парой из RFBS_BASE_SIZE (base_type=2, дата назначения в интервале
# действия размера ГСП) - без неё запись не попадает в отчёт независимо от
# :gsp (см. комментарий в docstring). kof_per - отношение по ОТДЕЛЬНОЙ
# выплате, до агрегации: с ГСП - (сумма + размер_ГСП * коэффициент_степени)
# / доход, без ГСП - просто сумма / доход.
#
# agg/pivot - per-регион суммы по 3 степеням, как в app_38.py, плюс sm_kof
# (сумма kof_per) для правильного среднего отношения.
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
     where substr(s.rfpm_id, 1, 4) = '0702'
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
           sum(case when step_utr = '3' then sm_kof  end) sm_kof3
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
       nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0)           cnt_t,
       nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0)  sm_all_t,
       nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0)  sum_avg_t,
       case when nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) > 0
            then (nvl(v.sm_all1, 0) + nvl(v.sm_all2, 0) + nvl(v.sm_all3, 0))
               / (nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0))
            else 0 end                                           avg_size_t,
       case when nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) > 0
            then (nvl(v.sm_avg1, 0) + nvl(v.sm_avg2, 0) + nvl(v.sm_avg3, 0))
               / (nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0))
            else 0 end                                           avg_smd_t,
       case when nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0) > 0
            then ((nvl(v.sm_kof1, 0) + nvl(v.sm_kof2, 0) + nvl(v.sm_kof3, 0))
                / (nvl(v.cnt1, 0) + nvl(v.cnt2, 0) + nvl(v.cnt3, 0))) * 100
            else 0 end                                           kof_t,
       (nvl(v.sm_kof1, 0) + nvl(v.sm_kof2, 0) + nvl(v.sm_kof3, 0)) * 100
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
