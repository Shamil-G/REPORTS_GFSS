# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3302 (процедура REP_R_3302).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

СВут (0702): назначения за период, у которых коэффициент утраты
трудоспособности по ЭМД (`ss_data.kut`) не равен норме вида выплаты (0,7 для
07020101, 0,5 для 07020102, 0,3 для 07020103). Последнее назначение по делу.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3302'
report_name = 'СВут несоответствие вида выплаты и коэфициента утраты трудоспособности {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата окончания', 'stopdate', 'date', 14),
    Col('Назначенный размер', 'sum_all', 'money', 16, total=False),
    Col('Коэфициент утраты трудоспособности по виду выплаты', 'need_kut', 'money', 16, total=False),
    Col('Коэфициент утраты трудоспособности по ЭМД', 'kut', 'money', 16, total=False),
    Col('Статус ЭМД', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       mp.pc, ms.z_date date_address, sd.risk_date, mp.d_naz, mp.stopdate,
       ms.nsum sum_all,
       case mp.pc when '07020101' then 0.7 when '07020102' then 0.5
                  when '07020103' then 0.3 end need_kut,
       sd.kut, ms.st
  from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p
 where mp.id = ms.mpay
   and mp.pc like '0702%'
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.d_naz >= :d_from and mp.d_naz < :d_to
   and ms.id = sd.sipr_id
   and p.sicid = sd.sicp_id
   and ((mp.pc = '07020101' and sd.kut <> 0.7) or
        (mp.pc = '07020102' and sd.kut <> 0.5) or
        (mp.pc = '07020103' and sd.kut <> 0.3))
 order by ms.brid, mp.pc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
