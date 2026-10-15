# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3301 (процедура REP_R_3301).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

СВбр (0704): назначения за период, у которых число дней нетрудоспособности
по ЭМД (`ss_data.ksu`) не равно норме вида выплаты (126, 140, 70, 56, 170,
184, 93, 79 дней по видам 07040101 ... 07040205). Последнее назначение по
делу (`mp.id = max(id)` по `soliray_id`). Колонка «Количество дней по виду
выплаты» (`need_ksu`) в оригинале считается с нормой 91 и 77 дней для
07040204 и 07040205, а отбор и «Несоответствие» - с 93 и 79: расхождение
оригинала сохранено как есть.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3301'
report_name = 'СВбр несоответствие вида выплаты и количество дней нетрудоспособности {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Номер дела', 'numb', 'center', 14),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата окончания', 'stopdate', 'date', 14),
    Col('Назначенный размер', 'sum_all', 'money', 16, total=False),
    Col('Количество дней нетрудоспособности по виду выплаты', 'need_ksu', 'int', 16, total=False),
    Col('Фактическое количество дней нетрудоспособности по б/л', 'ksu', 'int', 16, total=False),
    Col('Несоответствие (абс.)', 'diff_ksu', 'int', 14, total=False),
    Col('КЗД', 'kzd', 'money', 10, total=False),
    Col('Статус ЭМД', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       mp.pc, ms.numb, ms.z_date date_address, sd.risk_date, mp.d_naz,
       mp.stopdate, ms.nsum sum_all,
       case mp.pc when '07040101' then 126 when '07040102' then 140
                  when '07040104' then 70 when '07040105' then 56
                  when '07040201' then 170 when '07040202' then 184
                  when '07040204' then 91 when '07040205' then 77 end need_ksu,
       sd.ksu,
       case mp.pc when '07040101' then abs(126 - sd.ksu)
                  when '07040102' then abs(140 - sd.ksu)
                  when '07040104' then abs(70 - sd.ksu)
                  when '07040105' then abs(56 - sd.ksu)
                  when '07040201' then abs(170 - sd.ksu)
                  when '07040202' then abs(184 - sd.ksu)
                  when '07040204' then abs(93 - sd.ksu)
                  when '07040205' then abs(79 - sd.ksu) end diff_ksu,
       sd.kzd, ms.st
  from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p
 where mp.id = ms.mpay
   and mp.pc like '0704%'
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.d_naz >= :d_from and mp.d_naz < :d_to
   and ms.id = sd.sipr_id
   and p.sicid = sd.sicp_id
   and ((mp.pc = '07040101' and sd.ksu <> 126) or
        (mp.pc = '07040102' and sd.ksu <> 140) or
        (mp.pc = '07040104' and sd.ksu <> 70) or
        (mp.pc = '07040105' and sd.ksu <> 56) or
        (mp.pc = '07040201' and sd.ksu <> 170) or
        (mp.pc = '07040202' and sd.ksu <> 184) or
        (mp.pc = '07040204' and sd.ksu <> 93) or
        (mp.pc = '07040205' and sd.ksu <> 79))
 order by ms.brid, mp.pc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
