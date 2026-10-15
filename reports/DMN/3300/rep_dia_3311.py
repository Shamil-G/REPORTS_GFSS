# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3311 (процедура REP_R_3311).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Откаты статусов макета (`ss_m_sol_st`, запись «откат» ссылается на откатываемую
через `backid`) за период по дате отката: ИИН и ФИО получателя, вид выплаты,
дата обращения, тип назначения, статус, дата перехода в него и дата отката,
разница в днях, логин инспектора. Берутся статусы 5, 6, 7, 10, 11, 12, 17, 18,
66-69, 76, 77, 86-88 и статус 8, поставленный пользователем на «G». Код
региона - первые две цифры кода отделения + `00` (в оригинале с проверкой по
`rfbn_branch`, здесь по `branch`). Даты перехода и отката выведены строкой
`dd.mm.yyyy hh24:mi:ss`, как в оригинале.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(back.dat) between` заменён на `back.dat >= :d_from and back.dat < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_m_*`, `ss_z_doc`, `person` reports_test видит, часть остальных (вьюшка SSWH.V_REFUSE, `dic_country`) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3311'
report_name = 'Отчет по произведенным откатам с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код региона', 'rfbn_id', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Вид выплаты', 'p_pc', 'center', 12),
    Col('Дата обращения', 'd_inp', 'date', 14),
    Col('Тип назначения', 'id_tip', 'center', 12),
    Col('Статус', 'st2', 'center', 10),
    Col('Дата перехода в статус', 'dat1', 'center', 20),
    Col('Дата отката статуса', 'dat2', 'center', 20),
    Col('Разница', 'raz', 'int', 10, total=False),
    Col('Логин инспектора филиала', 'usr', 'center', 20),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select br.rfbn_id, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       st.p_pc, z.d_inp, z.id_tip, st.st2,
       to_char(st.dat, 'dd.mm.yyyy hh24:mi:ss') dat1,
       to_char(back.dat, 'dd.mm.yyyy hh24:mi:ss') dat2,
       trunc(back.dat) - trunc(st.dat) raz, st.usr
  from ss_m_sol_st st, ss_m_sol_st back, ss_m_sol sol, person p, ss_z_doc z,
       branch br
 where back.dat >= :d_from and back.dat < :d_to
   and back.sid = st.sid
   and sol.id = st.sid
   and back.backid = st.id
   and p.sicid = sol.sicid
   and st.sid = z.id
   and substr(st.brid, 1, 2) || '00' = br.rfbn_id
   and (st.st2 in (5, 6, 7, 10, 11, 12, 17, 18, 66, 67, 68, 69, 76, 77, 86, 87, 88)
        or (st.st2 = 8 and st.usr like 'G%'))
 order by br.rfbn_id, fio
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
