# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 615 (пакет AO_ONLINE_NEW, процедура
less_1mzp, «Взносы менее 1 МЗП»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Работники организации (БИН), за которых за месяц, оплаченный платежами
периода, внесено менее 1 МЗП: месяц, сумма взноса, доля МЗП, ИИН, ФИО.

Отбор как в оригинале: месяцы (`pay_month`), за которые организация платила
в выбранном периоде (`pay_date`); по этим месяцам - все платежи КНП 012 этой
организации (`si_member_2`), сумма по работнику и месяцу, остаются те, у кого
`sum(round(cnt_mzp, 7)) < 1`. В оригинале условие `s2.KNP = '012'` стояло
внутри подзапроса, но относилось к внешней таблице (подзапрос выбирал месяцы
по платежам любого КНП); так же сохранено. Пара `(p_rnn, pay_month)` в
`in (...)` сведена к одному месяцу: БИН фиксирован.

Период. `between pDateFrom and pDateTo` заменён на `>= :d_from and < :d_to`.
Проверка БИНа в оригинале закомментирована, здесь тоже нет (пустой БИН
просто даёт пустой отчёт). `p.rn` заменён на `p.iin`. Доля МЗП - `trunc(...,
4)`, формат оригинала `9999990D0999` выведен текстом, чтобы не потерять
знаки. Сортировка - по ФИО и месяцу. Подписи под таблицей оригинала не
переносятся.

Таблицы `si_member_2` и `person` reports_test видит - отчёт проверен
запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '615'
report_name = ('Список работников на которых были взносы менее 1 МЗП в '
               'период с {date_from} по {date_to} года\n'
               'для организации с БИН: {bin}')

COLUMNS = [
    Col('За какой месяц', 'pay_month', 'date', 14),
    Col('Сумма взноса', 'sum_all', 'money', 16, total=False),
    Col('Доля МЗП', 'perc', 'center', 12),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 40),
]

# :bin - БИН; :d_from, :d_to - период по дате платежа (d_to исключительная).
STMT = """
select a.pay_month,
       sum(a.sum_pay) sum_all,
       to_char(trunc(sum(a.cnt_mzp), 4), 'FM9999990.0999') perc,
       p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio
  from (select s2.pay_month, s2.sicid, round(s2.cnt_mzp, 7) cnt_mzp,
               s2.sum_pay
          from si_member_2 s2
         where s2.p_rnn = trim(:bin)
           and s2.knp = '012'
           and s2.pay_month in (select s.pay_month
                                  from si_member_2 s
                                 where s.p_rnn = trim(:bin)
                                   and s.pay_date >= :d_from
                                   and s.pay_date <  :d_to)) a,
       person p
 where a.sicid = p.sicid
 group by p.iin, a.pay_month, p.lastname || ' ' || p.firstname || ' ' || p.middlename
having sum(a.cnt_mzp) < 1
 order by fio, a.pay_month
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, title_params=('bin',),
)
