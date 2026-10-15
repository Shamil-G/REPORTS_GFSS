# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3315 (процедура REP_R_3315).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Обращения за назначением СВпр (потеря работы, основание 103, новое
обращение `id_tip = NEW`) за период по дате обращения (`d_inp`), по которым
когда-либо был действующий (не откатанный) статус 4, 16 или 29. Для каждого:
код региона, ИИН, ФИО, сумма, код и дата статуса (последний переход в текущий
статус), название статуса, источник обращения (ОЗСП, ЦОН, ПЭП), признаки
«Доработка ГК» (статус 8 поставил не пользователь «G...») и «Доработка Фонд»
(статус 8 от «G...»). Откатанные записи статусов в проверках исключены.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `d_inp between` заменён на `d_inp >= :d_from and d_inp < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_*`, `person` reports_test видит, часть остальных (вьюшки SSWH) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3315'
report_name = 'Отчет по обращениям за назначением СВпр с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код региона', 'brid', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Вид выплаты', 'rfpm', 'text', 18),
    Col('Дата обращения', 'd_inp', 'date', 14),
    Col('Сумма', 'nsum', 'money', 16, total=False),
    Col('Код статуса', 'st', 'center', 10),
    Col('Дата статуса', 'dat', 'date', 14),
    Col('Статус', 'name', 'text', 28),
    Col('Источник', 'src', 'center', 12),
    Col('Доработка ГК', 'rwgk', 'center', 12),
    Col('Доработка Фонд', 'rwfnd', 'center', 12),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       'Потеря работы' rfpm, zd.d_inp, ms.nsum, ms.st,
       (select max(st1.dat) from ss_m_sol_st st1
         where st1.sid = ms.id and st1.st2 = ms.st) dat,
       s.name,
       case when zd.id_sour = 'ZSP' then 'ОЗСП'
            when zd.id_sour = 'CON' then 'ЦОН'
            when zd.id_sour = 'PEP' then 'ПЭП'
            else zd.id_sour end src,
       case when exists (select 1 from ss_m_sol_st st
                          where st.sid = ms.id and st.st2 = 8
                            and st.usr not like 'G%'
                            and not exists (select 1 from ss_m_sol_st e where e.backid = st.id and e.sid = st.sid)
                            and not exists (select 1 from ss_m_sol_st e where e.id = st.id and e.backid is not null))
            then 'Да' else 'Нет' end rwgk,
       case when exists (select 1 from ss_m_sol_st st
                          where st.sid = ms.id and st.st2 = 8
                            and st.usr like 'G%'
                            and not exists (select 1 from ss_m_sol_st e where e.backid = st.id and e.sid = st.sid)
                            and not exists (select 1 from ss_m_sol_st e where e.id = st.id and e.backid is not null))
            then 'Да' else 'Нет' end rwfnd
  from ss_z_doc zd, ss_m_sol ms, person p, s_state s
 where zd.d_inp >= :d_from and zd.d_inp < :d_to
   and zd.id_osn = 103
   and zd.id_tip = 'NEW'
   and zd.id = ms.id
   and ms.sicid = p.sicid
   and ms.st = s.id
   and exists (select 1 from ss_m_sol_st st
                where st.sid = ms.id
                  and st.st2 in (4, 16, 29)
                  and not exists (select 1 from ss_m_sol_st e where e.backid = st.id and e.sid = st.sid)
                  and not exists (select 1 from ss_m_sol_st e where e.id = st.id and e.backid is not null))
 order by ms.brid, fio
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
