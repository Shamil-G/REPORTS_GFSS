# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3116 (процедура REP_R_3116).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатели СВут и СВпр (0702, 0703), у которых в месяце выплаты (документ
выплаты `pnpd_document.pncp_date`) наступает пенсионный возраст (мужчины 63,
женщины 58 полных лет на месяц позже `pncp_date`) и дата окончания выплаты
(`pnpt_payment.stopdate`) не раньше достижения этого возраста: отделение,
номер дела, ИИН, ФИО, дата рождения, пол, вид выплаты, дата окончания.

Период. В оригинале параметр один - месяц (`pncp_date = pMonth`, первое число
месяца), здесь, как у остальных отчётов, - период из двух дат: берутся все
месяцы выплат с `pncp_date` в [дата с, дата по]; для одного месяца вводится
его первое и последнее число. Заголовок оригинала «за <дата>» заменён на «за
период». Отделение - `branch.name` (в оригинале `rfbn_branch.name`).

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `pncp_date = pMonth` заменён на `pncp_date >= :d_from and pncp_date < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит не все (часть в SSWH): проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '3116'
report_name = 'Список получателей социальных выплат на случай утраты трудоспособности и на случай потери работы, достигающих пенсионного возраста (58/63), за период с {date_from} по {date_to}'

COLUMNS = [
    Col('Код отделения', 'rfbn_id', 'center', 10),
    Col('Отделение', 'name', 'text', 30),
    Col('Номер дела', 'file_numb', 'center', 14),
    Col('ИИН', 'iin', 'center', 16),
    Col('Фамилия', 'lastname', 'text', 22),
    Col('Имя', 'firstname', 'text', 20),
    Col('Отчество', 'middlename', 'text', 22),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Пол', 'sx', 'center', 10),
    Col('Код выплаты', 'rfpm_id', 'center', 14),
    Col('Дата окончания выплаты', 'stopdate', 'date', 14),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select distinct br.rfbn_id, br.name, pf.file_numb, p.iin, p.lastname,
       p.firstname, p.middlename, p.birthdate,
       case when p.sex = 0 then 'Женский' else 'Мужской' end sx,
       pd.rfpm_id, pt.stopdate
  from pnpd_document pd, person p, branch br, pnpt_payment pt, pnfl_file pf
 where pd.pncp_date >= :d_from and pd.pncp_date < :d_to
   and substr(pd.rfpm_id, 1, 4) in ('0702', '0703')
   and pd.pncd_id = p.sicid
   and br.rfbn_id = pd.rfbn_id
   and pd.source_id = pt.pnpt_id
   and pt.pnfl_id = pf.pnfl_id
   and ((p.sex = 1 and trunc(months_between(add_months(pd.pncp_date, 1), p.birthdate) / 12) >= 63)
        or (p.sex = 0 and trunc(months_between(add_months(pd.pncp_date, 1), p.birthdate) / 12) >= 58))
   and ((p.sex = 1 and trunc(months_between(pt.stopdate, p.birthdate) / 12) >= 63)
        or (p.sex = 0 and trunc(months_between(pt.stopdate, p.birthdate) / 12) >= 58))
 order by br.rfbn_id, p.lastname
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
