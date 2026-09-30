# -*- coding: utf-8 -*-
"""Приложение 36. Число страховых случаев и суммы соцвыплат по видам,
в разрезе пола (СВ 0701-0705).

Перенос REP_STAT_EXTEND.app_36_37_spool + Rep_app_36_37(..., iRepNum='sex')
(pck_utf8.sql, 3873-4560). Реестр: группа 1360, вызов app_36_37_1m('sex','m')
и аналоги по типам периода 1-5 (тип 7 у этой пары не зарегистрирован и в
самом пакете не реализован - Rep_app_36_37 обрабатывает только iDate_type
1-5, отдельной ветки для 7 нет).

Как и app_34_35, это одна процедура с параметром iRepNum ('sex'/'age'), но
разный SQL и колонки → два модуля: app_36.py (sex) и app_37.py (age).

Отличие от app_34_35: регион берётся не через организацию, а напрямую из
substr(rfbn_id,1,2) исходной строки (строка 3900) - проще, лишнего join
через rfon_organization/cato_branch не нужно. Возраст (только в app_37)
считается от risk_date, а не от даты последней выплаты (строка 3910) - тоже
отличие от app_34_35, где это была последняя дата обращения.

"Страховой случай" (cFmtInt-колонки) - это count(1) по факту назначения
(строка 3903: "здесь мы получаем кол-во выплат по всем людям - кол-во
СТРАХОВЫХ СЛУЧАЕВ"), а не count(distinct sicid) как в app_34_35: один
человек может дать несколько случаев.

Виды выплат (rfpm_id) фиксированы и порождаются внешним соединением с
маской 5 кодов (0701-0705, PrnOneGoup, строки 4095-4171) - как и с другими
семействами, отсутствующий в данных код молча не попадёт в отчёт (в
оригинале PrnOneGoup просто не читает других кодов).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.36'
# cSPTitle дословно (строка 4021): двойной пробел между "получателей" и "и
# суммах" - сохранён.
report_name = ('Сведения о числе получателей  и суммах социальных выплат '
               '(в разрезе принадлежности к полу), {period}')

# Подпись периода - тот же Begin-блок, что и у app_34_35 (типы 1-5
# идентичны текстуально, строки 4522-4541). Тип 7 у этой пары не
# используется - отдельного шаблона не заводим, для него подпись не нужна.
_period_label = make_period_label({
    1: '{Month} {year} года ',
    2: ' {n} квартал {year} года ',
    3: ' {n} полугодие {year} года ',
    4: '  9 месяцев {year} года ',
    5: ' {year} год ',
})

# (код rfpm, суффикс колонки, заголовок группы, есть ли сноска "*")
_PAY_TYPES = [
    ('0701', '1', 'по случаю потери кормильца', True),
    ('0702', '2', 'по случаю утраты трудоспособности', False),
    ('0703', '3', 'по случаю потери работы', False),
    ('0704', '4', 'на случай потери дохода в связи с беременностью и родами, '
                  'с усыновлением (удочерением) новорожденного ребенка '
                  '(детей)', False),
    ('0705', '5', 'на случай потери дохода в связи с уходом за ребенком по '
                  'достижении им возраста 1 года', False),
]


def _pay_group(suffix, title, footnote):
    money_title = 'Всего Сумма Выплат *(тенге)' if footnote \
        else 'Всего Сумма Выплат (тенге)'
    return Group(title, [
        Col('Всего СТРАХОВЫХ СЛУЧАЕВ', f'all_cnt{suffix}', 'int'),
        Group('в том числе', [
            Col('Мужчин', f'cnt_m{suffix}', 'int'),
            Col('Женщин', f'cnt_w{suffix}', 'int'),
        ]),
        Col(money_title, f'summ_all{suffix}', 'money', 18),
        Group('в том числе', [
            Col('Мужчин', f'summ_m{suffix}', 'money', 18),
            Col('Женщин', f'summ_w{suffix}', 'money', 18),
        ]),
    ])


COLUMNS = [
    Col('Области, города', 'reg', 'text', 30),
    *[_pay_group(suffix, title, footnote)
      for _, suffix, title, footnote in _PAY_TYPES],
    Group('Число СТРАХОВЫХ СЛУЧАЕВ', [
        Col('Всего', 'all_all_cnt', 'int'),
        Group('в том числе', [
            Col('Мужчин', 'all_cnt_m', 'int'),
            Col('Женщин', 'all_cnt_w', 'int'),
        ]),
    ]),
    Group('Сумма Выплат (тенге)', [
        Col('Всего', 'sum_summ_all', 'money', 18),
        Group('в том числе', [
            Col('Мужчин', 'all_summ_m', 'money', 18),
            Col('Женщин', 'all_summ_w', 'money', 18),
        ]),
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# base - строки sipr_maket_first_approve_2 за период, inner join person по
# sicp_id=sicid (в оригинале без (+) - строка 3941: если человека нет в
# Person, строка молча пропадает, как и в исходнике).
#
# agg/pivot - per-регион подсчёт "страховых случаев" (count(1), не distinct)
# и сумм по 5 видам выплат и полу. Не попавшие в маску 0701-0705 коды
# rfpm_id отбрасываются в base - так же, как PrnOneGoup никогда их не
# читает.
STMT = """
with base as (
    select substr(s.rfbn_id, 1, 2) reg_id,
           substr(s.rfpm_id, 1, 4) rfpm,
           s.sum_all,
           pr.sex
      from sipr_maket_first_approve_2 s, person pr
     where trunc(s.date_approve) >= :d_from
       and trunc(s.date_approve) <  :d_to
       and s.sicp_id = pr.sicid
       and substr(s.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
),
agg as (
    select reg_id, rfpm, sex,
           count(1)     cnt,
           sum(sum_all) summ
      from base
     group by reg_id, rfpm, sex
),
pivot as (
    select reg_id,
           sum(case when rfpm = '0701' and sex = 1 then cnt  end) cnt_m1,
           sum(case when rfpm = '0701' and sex = 0 then cnt  end) cnt_w1,
           sum(case when rfpm = '0701' and sex = 1 then summ end) summ_m1,
           sum(case when rfpm = '0701' and sex = 0 then summ end) summ_w1,
           sum(case when rfpm = '0702' and sex = 1 then cnt  end) cnt_m2,
           sum(case when rfpm = '0702' and sex = 0 then cnt  end) cnt_w2,
           sum(case when rfpm = '0702' and sex = 1 then summ end) summ_m2,
           sum(case when rfpm = '0702' and sex = 0 then summ end) summ_w2,
           sum(case when rfpm = '0703' and sex = 1 then cnt  end) cnt_m3,
           sum(case when rfpm = '0703' and sex = 0 then cnt  end) cnt_w3,
           sum(case when rfpm = '0703' and sex = 1 then summ end) summ_m3,
           sum(case when rfpm = '0703' and sex = 0 then summ end) summ_w3,
           sum(case when rfpm = '0704' and sex = 1 then cnt  end) cnt_m4,
           sum(case when rfpm = '0704' and sex = 0 then cnt  end) cnt_w4,
           sum(case when rfpm = '0704' and sex = 1 then summ end) summ_m4,
           sum(case when rfpm = '0704' and sex = 0 then summ end) summ_w4,
           sum(case when rfpm = '0705' and sex = 1 then cnt  end) cnt_m5,
           sum(case when rfpm = '0705' and sex = 0 then cnt  end) cnt_w5,
           sum(case when rfpm = '0705' and sex = 1 then summ end) summ_m5,
           sum(case when rfpm = '0705' and sex = 0 then summ end) summ_w5
      from agg
     group by reg_id
)
select rr.name                                        reg,
       nvl(v.cnt_m1, 0) + nvl(v.cnt_w1, 0)             all_cnt1,
       nvl(v.cnt_m1, 0)                                cnt_m1,
       nvl(v.cnt_w1, 0)                                cnt_w1,
       nvl(v.summ_m1, 0) + nvl(v.summ_w1, 0)           summ_all1,
       nvl(v.summ_m1, 0)                               summ_m1,
       nvl(v.summ_w1, 0)                               summ_w1,
       nvl(v.cnt_m2, 0) + nvl(v.cnt_w2, 0)             all_cnt2,
       nvl(v.cnt_m2, 0)                                cnt_m2,
       nvl(v.cnt_w2, 0)                                cnt_w2,
       nvl(v.summ_m2, 0) + nvl(v.summ_w2, 0)           summ_all2,
       nvl(v.summ_m2, 0)                               summ_m2,
       nvl(v.summ_w2, 0)                               summ_w2,
       nvl(v.cnt_m3, 0) + nvl(v.cnt_w3, 0)             all_cnt3,
       nvl(v.cnt_m3, 0)                                cnt_m3,
       nvl(v.cnt_w3, 0)                                cnt_w3,
       nvl(v.summ_m3, 0) + nvl(v.summ_w3, 0)           summ_all3,
       nvl(v.summ_m3, 0)                               summ_m3,
       nvl(v.summ_w3, 0)                               summ_w3,
       nvl(v.cnt_m4, 0) + nvl(v.cnt_w4, 0)             all_cnt4,
       nvl(v.cnt_m4, 0)                                cnt_m4,
       nvl(v.cnt_w4, 0)                                cnt_w4,
       nvl(v.summ_m4, 0) + nvl(v.summ_w4, 0)           summ_all4,
       nvl(v.summ_m4, 0)                               summ_m4,
       nvl(v.summ_w4, 0)                               summ_w4,
       nvl(v.cnt_m5, 0) + nvl(v.cnt_w5, 0)             all_cnt5,
       nvl(v.cnt_m5, 0)                                cnt_m5,
       nvl(v.cnt_w5, 0)                                cnt_w5,
       nvl(v.summ_m5, 0) + nvl(v.summ_w5, 0)           summ_all5,
       nvl(v.summ_m5, 0)                               summ_m5,
       nvl(v.summ_w5, 0)                               summ_w5,
       nvl(v.cnt_m1,0)+nvl(v.cnt_w1,0)+nvl(v.cnt_m2,0)+nvl(v.cnt_w2,0)
         + nvl(v.cnt_m3,0)+nvl(v.cnt_w3,0)+nvl(v.cnt_m4,0)+nvl(v.cnt_w4,0)
         + nvl(v.cnt_m5,0)+nvl(v.cnt_w5,0)             all_all_cnt,
       nvl(v.cnt_m1,0)+nvl(v.cnt_m2,0)+nvl(v.cnt_m3,0)
         + nvl(v.cnt_m4,0)+nvl(v.cnt_m5,0)             all_cnt_m,
       nvl(v.cnt_w1,0)+nvl(v.cnt_w2,0)+nvl(v.cnt_w3,0)
         + nvl(v.cnt_w4,0)+nvl(v.cnt_w5,0)             all_cnt_w,
       nvl(v.summ_m1,0)+nvl(v.summ_w1,0)+nvl(v.summ_m2,0)+nvl(v.summ_w2,0)
         + nvl(v.summ_m3,0)+nvl(v.summ_w3,0)+nvl(v.summ_m4,0)+nvl(v.summ_w4,0)
         + nvl(v.summ_m5,0)+nvl(v.summ_w5,0)           sum_summ_all,
       nvl(v.summ_m1,0)+nvl(v.summ_m2,0)+nvl(v.summ_m3,0)
         + nvl(v.summ_m4,0)+nvl(v.summ_m5,0)           all_summ_m,
       nvl(v.summ_w1,0)+nvl(v.summ_w2,0)+nvl(v.summ_w3,0)
         + nvl(v.summ_w4,0)+nvl(v.summ_w5,0)           all_summ_w
  from RFRG_REGION rr, pivot v
 where v.reg_id(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=True,
    period_label=_period_label,
    footnote=('* - без учета удержаний обязательных пенсионных взносов'),
)
