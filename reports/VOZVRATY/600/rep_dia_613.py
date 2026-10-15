# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 613 (процедура REP_R_3318, «Макеты по ЕСП»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сводка по областям к отчёту 612: число получателей (всего, мужчин, женщин) и
назначенная сумма (всего, мужчин, женщин) по пяти видам выплат (0701-0705) и
итого. В отбор попадают макеты за период по дате обращения (`ms.z_date`) в
статусах 7, 12, 20, по которым есть отчисления плательщика ЕСП
(`em5_sird_reckon_donation.is_esp = 'Y'`).

Параметр «Статус» (в оригинале '1' / '2' / '3'): 1 - макеты в статусах 7 и
20, 2 - в статусе 12, 3 - все (оригинал подставлял '%' и печатал его в
названии, здесь - «все»).

Период. `between pDateFrom and pDateTo` заменён на `>= :d_from and < :d_to`.
Область - `branch.name` по коду `<2 знака brid>00` (в оригинале
`rfrg_region.name`, у которого казахские буквы подменены), правило Шамиля
14.10.2026. `p.rn` в оригинале считался `count(rn)`: заменён на `p.iin`.
Ограничение по отделению пользователя (`ms.brid like <область>%`) не
переносится, подсчёт идёт по всем областям. Подсчёты «есть СО»
(`have_so`) оригинала в итоговые колонки не попадали и опущены.

`em5_sird_reckon_donation` лежит в SSWH и reports_test недоступна: запрос на
данных не сверен, только синтаксис.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '613'
report_name = ('Макеты по ЕСП\nПо дате обращения с {date_from} по {date_to}\n'
               'Статус: {status}')


def _block(title, tag):
    return Group(title, [
        Col('Всего', f'cnt{tag}', 'int', 10),
        Col('Мужчин', f'cnt{tag}m', 'int', 10),
        Col('Женщин', f'cnt{tag}w', 'int', 10),
        Col('Всего сумма', f'sm{tag}', 'money', 16),
        Col('Мужчин', f'sm{tag}m', 'money', 16),
        Col('Женщин', f'sm{tag}w', 'money', 16),
    ])


COLUMNS = [
    Col('Области', 'name', 'text', 30),
    _block('По потере кормильца', '_0701'),
    _block('По утрате трудоспособности', '_0702'),
    _block('По потере работы', '_0703'),
    _block('Соцвыплаты по беременности и родам', '_0704'),
    _block('Соцвыплаты по уходу за ребенком до года', '_0705'),
    _block('Итого', ''),
]

# :d_from, :d_to - период по дате обращения (d_to исключительная);
# :status - '1' (статусы 7, 20), '2' (статус 12) или '3' (все).
STMT = """
select name,
       count(case when pc like '0701%' then iin end) cnt_0701,
       count(case when pc like '0701%' and pol = 'М' then iin end) cnt_0701m,
       count(case when pc like '0701%' and pol = 'Ж' then iin end) cnt_0701w,
       sum(case when pc like '0701%' then nsum end) sm_0701,
       sum(case when pc like '0701%' and pol = 'М' then nsum end) sm_0701m,
       sum(case when pc like '0701%' and pol = 'Ж' then nsum end) sm_0701w,
       count(case when pc like '0702%' then iin end) cnt_0702,
       count(case when pc like '0702%' and pol = 'М' then iin end) cnt_0702m,
       count(case when pc like '0702%' and pol = 'Ж' then iin end) cnt_0702w,
       sum(case when pc like '0702%' then nsum end) sm_0702,
       sum(case when pc like '0702%' and pol = 'М' then nsum end) sm_0702m,
       sum(case when pc like '0702%' and pol = 'Ж' then nsum end) sm_0702w,
       count(case when pc like '0703%' then iin end) cnt_0703,
       count(case when pc like '0703%' and pol = 'М' then iin end) cnt_0703m,
       count(case when pc like '0703%' and pol = 'Ж' then iin end) cnt_0703w,
       sum(case when pc like '0703%' then nsum end) sm_0703,
       sum(case when pc like '0703%' and pol = 'М' then nsum end) sm_0703m,
       sum(case when pc like '0703%' and pol = 'Ж' then nsum end) sm_0703w,
       count(case when pc like '0704%' then iin end) cnt_0704,
       count(case when pc like '0704%' and pol = 'М' then iin end) cnt_0704m,
       count(case when pc like '0704%' and pol = 'Ж' then iin end) cnt_0704w,
       sum(case when pc like '0704%' then nsum end) sm_0704,
       sum(case when pc like '0704%' and pol = 'М' then nsum end) sm_0704m,
       sum(case when pc like '0704%' and pol = 'Ж' then nsum end) sm_0704w,
       count(case when pc like '0705%' then iin end) cnt_0705,
       count(case when pc like '0705%' and pol = 'М' then iin end) cnt_0705m,
       count(case when pc like '0705%' and pol = 'Ж' then iin end) cnt_0705w,
       sum(case when pc like '0705%' then nsum end) sm_0705,
       sum(case when pc like '0705%' and pol = 'М' then nsum end) sm_0705m,
       sum(case when pc like '0705%' and pol = 'Ж' then nsum end) sm_0705w,
       count(iin) cnt,
       count(case when pol = 'М' then iin end) cntm,
       count(case when pol = 'Ж' then iin end) cntw,
       sum(nsum) sm,
       sum(case when pol = 'М' then nsum end) smm,
       sum(case when pol = 'Ж' then nsum end) smw
  from (
    select substr(ms.brid, 1, 2) brid, b.name, p.iin,
           (case when p.sex = 1 then 'М' else 'Ж' end) pol,
           mp.pc, mp.nsum,
           (case when ms.st in (7, 20) then '1' else '2' end) status
      from ss_m_sol ms, ss_m_pay mp, person p, branch b
     where ms.mpay = mp.id
       and ms.sicid = p.sicid
       and substr(ms.brid, 1, 2) || '00' = b.rfbn_id
       and ms.z_date >= :d_from and ms.z_date < :d_to
       and ms.st in (7, 12, 20)
       and exists (select 1 from em5_sird_reckon_donation e
                    where e.sipr_id = ms.id and nvl(e.is_esp, 'N') = 'Y'))
 where (:status = '3' or status = :status)
 group by brid, name
 order by brid
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
    text_params={'status': {'1': '1', '2': '2', '3': 'все'}},
)
