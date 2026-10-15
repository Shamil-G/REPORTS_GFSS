# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 614 (процедура REP_R_614).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Список получателей социальной выплаты на случай потери работы (0703), снятых
с учёта в качестве безработного в Центре занятости: сведения из
информационной системы «Рынок труда» (`v_lm_unemploy_ss_info`, статус 601)
сопоставляются с назначенной выплатой в ЦБД (`pnpt_payment`, вид 0703%,
дата назначения = дата постановки на учёт, выплата не закрыта) и с последним
решением макета (`ss_m_pay`, `ss_m_sol`, `s_state`).

`person.rn` заменён на `person.iin`. Ограничение по области пользователя
(`ms.brid like <область>%`; у пользователя не центрального аппарата) не
переносится: у веб-отчётов отделения пользователя нет, выводятся все. Порядок - по коду региона и дате снятия с учёта в ИС Рынок
Труда (`order by 1, 7` оригинала). Подписи под
таблицей (руководитель, исполнитель, дата создания) оригинала в Excel не
выводятся.

`v_lm_unemploy_ss_info`, `ss_m_*` и `s_state`: первая в SSWH и reports_test
недоступна, остальные видны; запрос на данных не сверен, только синтаксис.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '614'
report_name = ('Список получателей социальной выплаты на случай потери '
               'работы, которые сняты с учета в качестве безработного в '
               'Центре занятости')

COLUMNS = [
    Col('Код региона', 'brid', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 40),
    Col('Вид выплаты', 'rfpm', 'center', 12),
    Col('Номер дела', 'z_numb', 'center', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата снятия в ИС Рынок Труда', 'regclosedate', 'date', 16),
    Col('Код статуса Е-макет', 'st_id', 'center', 10),
    Col('Статус Е-макет', 'st_name', 'text', 28),
    Col('Дата окончания Е-макет', 'stopdate', 'date', 16),
    Col('Дата окончания ЦБД', 'cbd_stopdate', 'date', 16),
    Col('Сумма', 'nsum', 'money', 14, total=False),
]

STMT = """
select ms.brid,
       p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       mp.pc rfpm,
       ms.z_numb,
       mp.d_naz,
       s.regclosedate,
       st.id st_id,
       st.name st_name,
       mp.stopdate,
       pp.stopdate cbd_stopdate,
       mp.nsum
  from v_lm_unemploy_ss_info s, person p, pnpt_payment pp, ss_m_pay mp,
       ss_m_sol ms, s_state st
 where s.statcode = '601'
   and s.iin = p.iin
   and p.sicid = pp.pncd_id
   and pp.rfpm_id like '0703%'
   and pp.appointdate = s.regdate
   and pp.act_close is null
   and mp.soliray_id = pp.pnpt_id
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.sid = ms.id
   and ms.st = st.id(+)
 order by ms.brid, s.regclosedate
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE,
)
