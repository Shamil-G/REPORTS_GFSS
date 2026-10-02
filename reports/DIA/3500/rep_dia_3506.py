# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ЕСП», отчёт 3506 (процедура REP_R_3506).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Отчёт о поступивших социальных отчислениях от плательщиков ЕСП по периоду
(по месяцам платежа): число участников и суммы по областям и по размеру
платежа - в столице, городах республиканского и областного значения
(платёж = 1/5 базового размера из `rfbs_base_size`) и в других населённых
пунктах.

Отличия от 3502 (тот же расчёт): период берётся по МЕСЯЦУ платежа
(`pay_month`, а не по дате поступления в ГФСС), отделения, сведённые в
области 18-20, здесь не объединяются (только 14xx -> 1700), и название
области в республиканском разрезе подтягивается внешним соединением уже
после группировки. Две формы запроса по параметру «область»: «00» - вся
республика, иначе одна область по отделениям.

Тип плательщика ЕСП - латинская «E» вместо кириллической «Е» исходника:
так он хранится в `si_member_2` (см. коммит f54ac2e), иначе результат пуст.
Название дословно, под таблицей - сноска оригинала со звёздочкой.
В оригинале комментарий: справочник `rfbs_base_size` надо заполнять с Нового
года, иначе расчёт вернёт неверный результат - это по-прежнему так.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3506'
report_name = ('Отчет о поступивших социальных отчислениях от плательщиков '
               'ЕСП по периоду с {period} года')

FOOTNOTE = ('* - участники, за которых в отчетном периоде произведены '
            'социальные отчисления, учтенные, хотя бы один раз')

_CNT = 'Количество, человек*'
_SUM = 'Сумма, тенге'

COLUMNS = [
    Col('Наименование области', 'brname', 'text', 40),
    Group('В столице, городах республиканского и областного значения', [
        Col(_CNT, 'cnt_1', 'int', 16),
        Col(_SUM, 'sum1', 'money', 20),
    ]),
    Group('В других населенных пунктах', [
        Col(_CNT, 'cnt_2', 'int', 16),
        Col(_SUM, 'sum_2', 'money', 20),
    ]),
]

# :d_from / :d_to - период из формы по pay_month, :d_to исключительная.
_STMT_REPUBLIC = """
select nvl(r.name, 'Не определена') brname,
       count(unique case when g.sum_pay =  base_size / 5 then sicid else null end) cnt_1,
       sum(case when g.sum_pay =  base_size / 5 then g.sum_pay else 0 end) sum1,
       count(unique case when g.sum_pay != base_size / 5 then sicid else null end) cnt_2,
       sum(case when g.sum_pay != base_size / 5 then g.sum_pay else 0 end) sum_2
  from (select first_value(replace(substr(case when p.branchid in ('1403', '1416', '1417', '1418')
                                               then '1700' else p.branchid end, 1, 2), '00', '99'))
                   over (partition by v.sicid order by v.pay_date_gfss desc) br,
               p.sex,
               v.sum_pay,
               p.sicid,
               bs.base_size
          from si_member_2 v, person p, rfbs_base_size bs
         where v.sicid = p.sicid
           and v.type_payer = 'E'
           and bs.base_type = 1
           and v.pay_month between bs.date_beg
                               and nvl(bs.date_end, add_months(trunc(sysdate, 'YY'), 12) - 1)
           and v.pay_month >= :d_from
           and v.pay_month <  :d_to) g,
       rfrg_region r
 where substr(br, 1, 2) = r.rfrg_id(+)
 group by r.name, substr(br, 1, 2)
 order by substr(br, 1, 2)
"""

_STMT_REGION = """
select br || ' - ' || nvl(r.short_name, 'Не определена') brname,
       count(unique case when g.sum_pay =  base_size / 5 then sicid else null end) cnt_1,
       sum(case when g.sum_pay =  base_size / 5 then g.sum_pay else 0 end) sum1,
       count(unique case when g.sum_pay != base_size / 5 then sicid else null end) cnt_2,
       sum(case when g.sum_pay != base_size / 5 then g.sum_pay else 0 end) sum_2
  from (select replace(case when p.branchid in ('1403', '1416', '1417', '1418')
                            then '1700' else p.branchid end, '0000', '9999') br,
               p.sex,
               v.sum_pay,
               p.sicid,
               bs.base_size
          from si_member_2 v, person p, rfbs_base_size bs
         where v.sicid = p.sicid
           and v.type_payer = 'E'
           and bs.base_type = 1
           and substr(p.branchid, 1, 2) = substr(:rfbn_id, 1, 2)
           and v.pay_month between bs.date_beg
                               and nvl(bs.date_end, add_months(trunc(sysdate, 'YY'), 12) - 1)
           and v.pay_month >= :d_from
           and v.pay_month <  :d_to) g,
       branch r
 where br = r.rfbn_id
 group by r.short_name, br
 order by br
"""


def STMT(params):
    """«00» - вся республика, иначе одна область."""
    reg = str(params.get('rfbn_id') or '00')[:2]
    return _STMT_REPUBLIC if reg == '00' else _STMT_REGION


do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True, footnote=FOOTNOTE,
)
