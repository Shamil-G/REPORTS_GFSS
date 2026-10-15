# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3308 (процедура REP_R_3308).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатели СВпк (0701) с назначением за период, у которых иждивенцу
старше 23 лет (`trunc(months_between(sysdate, pch.birthdate) / 12) > 23`)
выплата всё ещё идёт (`mp.stopdate > sysdate`) и при этом нет другого
иждивенца до 3 лет. «Дата окончания до 23 лет» - день перед 23-летием
иждивенца. Последнее назначение по делу. Иждивенцы - `ss_m_child` и `person`
(`pch`), тип - `srdc_dependant_category`. В названии латинские «c»
исправлены.

Причина невалидности процедуры в боевой БД - `ORA-00904: "PCH.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `pch.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3308'
report_name = 'Список получателей СВпк с неверной датой окончания с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('ИИН получателя', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Пол', 'sex', 'center', 10),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('ИИН иждивенца', 'chiin', 'center', 16),
    Col('ФИО иждивенца', 'chfio', 'text', 36),
    Col('Дата рождения иждивенца', 'chbirthdate', 'date', 14),
    Col('Назначенная сумма', 'nsum', 'money', 16, total=False),
    Col('Дата окончания в ЭМД', 'stopdate', 'date', 14),
    Col('Дата окончания до 23 лет', 'need_stopdate', 'date', 14),
    Col('Тип иждивенца', 'tip', 'center', 10),
    Col('Наименование типа', 'name_ru', 'text', 28),
    Col('Статус', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       p.birthdate,
       case when p.sex = 1 then 'Мужской' else 'Женский' end sex,
       mp.pc, pch.iin chiin,
       pch.lastname || ' ' || pch.firstname || ' ' || pch.middlename chfio,
       pch.birthdate chbirthdate, ms.nsum, mp.stopdate,
       add_months(pch.birthdate, 23*12) - 1 need_stopdate,
       ch.tip, dc.name_ru, ms.st
  from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p, ss_m_child ch,
       person pch, srdc_dependant_category dc
 where mp.id = ms.mpay
   and mp.pc like '0701%'
   and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
   and mp.d_naz >= :d_from and mp.d_naz < :d_to
   and ms.id = sd.sipr_id
   and p.sicid = sd.sicp_id
   and mp.id = ch.id_pay
   and ch.sicid = pch.sicid
   and ch.tip = dc.srdc_id(+)
   and trunc(months_between(sysdate, pch.birthdate) / 12) > 23
   and not exists (select 1 from ss_m_child ch2, person p3
                    where ch2.id_pay = mp.id
                      and ch2.sicid <> ch.sicid
                      and p3.sicid = ch2.sicid
                      and trunc(months_between(sysdate, p3.birthdate)) / 12 <= 3)
   and mp.stopdate > sysdate
 order by ms.brid
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
