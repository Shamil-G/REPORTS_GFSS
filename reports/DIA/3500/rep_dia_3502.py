# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ЕСП», отчёт 3502 (процедура REP_R_3502).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Отчёт о поступивших социальных отчислениях от плательщиков единого
совокупного платежа (ЕСП): число участников и суммы по областям и по
размеру платежа - в столице, городах республиканского и областного значения
(платёж = 1/5 базового размера из `rfbs_base_size`) и в других населённых
пунктах (платёж другого размера).

Источник - `si_member_2` (плательщик ЕСП) + `person` + `rfbs_base_size`
(`base_type = 1`, база действует на месяц платежа: `pay_month` между
`date_beg` и `date_end`, открытая база - до конца следующего года, как в
оригинале). Период - по дате поступления в ГФСС (`pay_date_gfss`).

Два разреза по параметру «область» (в оригинале `reg`, первый параметр):
  - пусто - вся республика: строка на область (`rfrg_region`); область участника -
    по самому свежему платежу (`first_value ... over (partition by sicid
    order by pay_date_gfss desc)`), отдельные районы сведены в области 17-20
    (списки `branchid` из оригинала дословно), «00» -> «99», не нашедшие
    область называются «Не определена»;
  - код области - строка на отделение (`branch`), название «код - наименование»,
    «0000» -> «9999».
Запрос выбирается функцией от параметров, на листе SQL остаётся тот, что
реально выполнялся.

Отличие от оригинала: тип плательщика ЕСП - латинская «E» (так он хранится в
`si_member_2`, см. коммит f54ac2e: кириллическая «Е» из исходника AIS даёт
пустой результат). Остальное дословно (кроме пробела перед запятой в заголовке «В столице,
городах...»). Количество - `count(unique ...)`. Название дословно, под таблицей - сноска оригинала со звёздочкой.
Платёж по ЕСП в `si_member_2` в боевых данных есть только по начало 2024 года.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3502'
report_name = ('Отчет о поступивших социальных отчислениях от плательщиков '
               'единого совокупного платежа с {period} года')

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

# Отделения, сведённые в области 17-20 (дословно из оригинала).
_BR_GROUPS = """case when p.branchid in ('1403', '1416', '1417', '1418') then '1700'
                    when p.branchid in ('0503', '0504', '0505', '0506', '0507', '0508', '0510', '0518') then '18'
                    when p.branchid in ('0303', '0304', '0305', '0306', '0311', '0313', '0314', '0315', '0317', '0318') then '19'
                    when p.branchid in ('0802', '0804', '0812', '0816', '0818') then '20'
                    else p.branchid end"""

# :d_from / :d_to - период из формы по pay_date_gfss, :d_to исключительная.
_STMT_REPUBLIC = f"""
select nvl(brname, 'Не определена') brname,
       count(unique case when g.sum_pay =  base_size / 5 then sicid else null end) cnt_1,
       sum(case when g.sum_pay =  base_size / 5 then g.sum_pay else 0 end) sum1,
       count(unique case when g.sum_pay != base_size / 5 then sicid else null end) cnt_2,
       sum(case when g.sum_pay != base_size / 5 then g.sum_pay else 0 end) sum_2
  from (select r.name brname,
               first_value(replace(substr({_BR_GROUPS}, 1, 2), '00', '99'))
                   over (partition by v.sicid order by v.pay_date_gfss desc) br,
               p.sex,
               v.sum_pay,
               p.sicid,
               bs.base_size
          from si_member_2 v, person p, rfrg_region r, rfbs_base_size bs
         where v.sicid = p.sicid
           and v.type_payer = 'E'
           and substr(p.branchid, 1, 2) = r.rfrg_id(+)
           and bs.base_type = 1
           and v.pay_month between bs.date_beg
                               and nvl(bs.date_end, add_months(trunc(sysdate, 'YY'), 12) - 1)
           and v.pay_date_gfss >= :d_from
           and v.pay_date_gfss <  :d_to) g
 group by brname, br
 order by br
"""

_STMT_REGION = f"""
select br || ' - ' || nvl(brname, 'Не определена') brname,
       count(unique case when g.sum_pay =  base_size / 5 then sicid else null end) cnt_1,
       sum(case when g.sum_pay =  base_size / 5 then g.sum_pay else 0 end) sum1,
       count(unique case when g.sum_pay != base_size / 5 then sicid else null end) cnt_2,
       sum(case when g.sum_pay != base_size / 5 then g.sum_pay else 0 end) sum_2
  from (select r.short_name brname,
               replace({_BR_GROUPS}, '0000', '9999') br,
               p.sex,
               v.sum_pay,
               p.sicid,
               bs.base_size
          from si_member_2 v, person p, branch r, rfbs_base_size bs
         where v.sicid = p.sicid
           and v.type_payer = 'E'
           and p.branchid = r.rfbn_id
           and bs.base_type = 1
           and substr(p.branchid, 1, 2) = substr(:rfbn_id, 1, 2)
           and v.pay_month between bs.date_beg
                               and nvl(bs.date_end, add_months(trunc(sysdate, 'YY'), 12) - 1)
           and v.pay_date_gfss >= :d_from
           and v.pay_date_gfss <  :d_to) g
 group by brname, br
 order by br
"""


def STMT(params):
    """Пусто - вся республика, иначе одна область."""
    reg = str(params.get('rfbn_id') or '00')[:2]
    return _STMT_REPUBLIC if reg == '00' else _STMT_REGION


do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True, footnote=FOOTNOTE,
)
