# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3313 (процедура REP_R_3313).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Макеты, по которым первое ЭМД получило отказ (вьюшка `v_refuse`), а по тому
же человеку, виду выплаты и дате риска позже появилось утверждённое
назначение (`sipr_maket_first_approve_2`, `date_approve > D_UTV` отказа). За
период по дате отказа (`ret_date`). Показаны оба дела: номер, суммы при отказе
и при назначении и их разница, причина отказа и примечание, дата и статус
нового дела. Год рождения - `extract(year ...)`.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `ret_date between` заменён на `ret_date >= :d_from and ret_date < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_m_*`, `ss_z_doc`, `person` reports_test видит, часть остальных (вьюшка SSWH.V_REFUSE, `dic_country`) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3313'
report_name = 'По одной дате риска 1 ЭМД отказ, 2 ЭМД назначение с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('Номер дела', 'numb', 'center', 14),
    Col('ИИН получателя', 'iin', 'center', 16),
    Col('ФИО получателя', 'fio', 'text', 36),
    Col('Год рождения получателя', 'y', 'center', 12),
    Col('Вид выплаты', 'p_pc', 'center', 12),
    Col('Дата обращения', 'd_inp', 'date', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата утверждения', 'd_utv', 'date', 14),
    Col('Размер выплаты при отказе', 'sum_all', 'money', 16, total=False),
    Col('Размер выплаты при назначении', 'sum_all_new', 'money', 16, total=False),
    Col('Разница', 'raz', 'money', 14, total=False),
    Col('Статус ЭМД', 'st', 'center', 10),
    Col('Причина отказа', 'ret_name', 'text', 30),
    Col('Примечание', 'ret_txt', 'text', 30),
    Col('№ дела новый', 'numb_new', 'center', 14),
    Col('Дата назначения нового', 'd_resh', 'date', 14),
    Col('Дата риска новый', 'risk_date_new', 'date', 14),
    Col('Дата утвержд новый', 'date_approve', 'date', 14),
    Col('Статус новый', 'st_new', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select vr.brid, vr.numb, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       extract(year from p.birthdate) y, vr.p_pc, vr.d_inp, vr.d_naz,
       vr.risk_date, vr.d_utv, vr.sum_all, sfa.sum_all sum_all_new,
       sfa.sum_all - vr.sum_all raz, vr.st, vr.ret_name, vr.ret_txt,
       ms.numb numb_new, ms.d_resh, sfa.risk_date risk_date_new,
       sfa.date_approve, ms.st st_new
  from v_refuse vr, sipr_maket_first_approve_2 sfa, person p, ss_m_sol ms
 where vr.ret_date >= :d_from and vr.ret_date < :d_to
   and vr.sicid = sfa.sicp_id
   and vr.p_pc = sfa.rfpm_id
   and vr.risk_date = sfa.risk_date
   and sfa.date_approve > vr.d_utv
   and vr.sicid = p.sicid
   and ms.id = vr.sipr_id
 order by vr.brid, fio
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
