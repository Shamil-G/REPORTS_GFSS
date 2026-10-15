# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3306 (процедура REP_R_3306).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатели СВпр, СВбр, СВур (0703, 0704, 0705) с назначением за период, у
которых от даты риска (`ss_data.risk_date`) до даты обращения (`ms.z_date`)
больше 12 месяцев (`months_between > 12`); «Разница, дни» - число полных
дней. Последнее назначение по делу. Название оригинала («у которых с даты
риска до даты обращения превышает на 12 месяцев c ...») приведено к
читаемому виду: латинская «c», двойные пробелы и «Свбр» исправлены.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3306'
report_name = 'Список получателей СВур, СВпр, СВбр, у которых с даты риска до даты обращения прошло более 12 месяцев, с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('ИИН получателя', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Назначенная сумма', 'sum_all', 'money', 16, total=False),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Разница, дни', 'raz', 'int', 12, total=False),
    Col('Статус ЭМД', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       p.birthdate, mp.pc, ms.nsum sum_all, mp.d_naz, sd.risk_date,
       ms.z_date date_address, trunc(ms.z_date - sd.risk_date) raz, ms.st
  from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p
 where mp.id = ms.mpay
   and substr(mp.pc, 1, 4) in ('0703', '0704', '0705')
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.d_naz >= :d_from and mp.d_naz < :d_to
   and ms.id = sd.sipr_id
   and p.sicid = sd.sicp_id
   and months_between(ms.z_date, sd.risk_date) > 12
 order by ms.brid, mp.pc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
