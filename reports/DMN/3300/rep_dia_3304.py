# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3304 (процедура REP_R_3304).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Назначения СВпк, СВут, СВпр (0701, 0702, 0703) за период, у которых КСУ по
ЭМД (`ss_data.ksu`, коэффициент стажа участия) не равен норме по стажу
участия в месяцах (`cnt_don`): меньше 6 - 0,1; 6-11 - 0,7; 12-23 - 0,75;
24-35 - 0,85; 36-47 - 0,9; 48-59 - 0,95; 60 и больше - 1. Последнее
назначение по делу. В названии оригинала латинская «c» и двойные пробелы
исправлены.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3304'
report_name = 'Несоответствие КУМ и КСУ с {date_from} по {date_to} года'

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
    Col('Стаж участия, месяцев', 'cnt_don', 'int', 12, total=False),
    Col('КСУ по выплате', 'need_ksu', 'money', 12, total=False),
    Col('КСУ по ЭМД', 'ksu', 'money', 12, total=False),
    Col('Статус ЭМД', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       mp.pc, ms.z_date date_address, sd.risk_date, mp.d_naz, mp.stopdate,
       ms.nsum sum_all, sd.cnt_don,
       case when sd.cnt_don < 6 then 0.1
            when sd.cnt_don >= 6 and sd.cnt_don < 12 then 0.7
            when sd.cnt_don >= 12 and sd.cnt_don < 24 then 0.75
            when sd.cnt_don >= 24 and sd.cnt_don < 36 then 0.85
            when sd.cnt_don >= 36 and sd.cnt_don < 48 then 0.9
            when sd.cnt_don >= 48 and sd.cnt_don < 60 then 0.95
            when sd.cnt_don >= 60 then 1 end need_ksu,
       sd.ksu, ms.st
  from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p
 where mp.id = ms.mpay
   and substr(mp.pc, 1, 4) in ('0701', '0702', '0703')
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.d_naz >= :d_from and mp.d_naz < :d_to
   and ms.id = sd.sipr_id
   and p.sicid = sd.sicp_id
   and ((sd.cnt_don < 6 and sd.ksu <> 0.1) or
        (sd.cnt_don >= 6 and sd.cnt_don < 12 and sd.ksu <> 0.70) or
        (sd.cnt_don >= 12 and sd.cnt_don < 24 and sd.ksu <> 0.75) or
        (sd.cnt_don >= 24 and sd.cnt_don < 36 and sd.ksu <> 0.85) or
        (sd.cnt_don >= 36 and sd.cnt_don < 48 and sd.ksu <> 0.9) or
        (sd.cnt_don >= 48 and sd.cnt_don < 60 and sd.ksu <> 0.95) or
        (sd.cnt_don >= 60 and sd.ksu <> 1))
 order by mp.pc, ms.brid
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
