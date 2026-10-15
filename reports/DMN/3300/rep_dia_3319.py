# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3319 (процедура REP_R_3319).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Дела, у которых отделение в Е-макете (`brid`) и отделение в ЦБД
(`rfbn_id`) относятся к разным областям (первые две цифры различаются):
первые утверждённые назначения (вьюшка `v_sipr_maket_first_approve_dn`) за
период по дате утверждения. Колонки: код выплаты, ИИН, ФИО, дата решения
(утверждения), дата риска, код отделения в Е-макете и в ЦБД.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(v.date_approve) between` заменён на `v.date_approve >= :d_from and v.date_approve < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_*`, `person` reports_test видит, часть остальных (вьюшки SSWH) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3319'
report_name = 'Отчет список по движению (переносу) карточки назначенных социальных выплат из Е-макета в ЦБД с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код выплаты', 'rfpm_id', 'center', 14),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО получателя', 'fio', 'text', 36),
    Col('Дата решения (утверждения)', 'date_approve', 'date', 16),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Код в Е-макет', 'brid', 'center', 12),
    Col('Код в ЦБД', 'rfbn_id', 'center', 12),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select v.rfpm_id, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       v.date_approve, v.risk_date, v.brid, v.rfbn_id
  from v_sipr_maket_first_approve_dn v, person p
 where v.date_approve >= :d_from and v.date_approve < :d_to
   and p.sicid = v.sicp_id
   and substr(v.brid, 1, 2) <> substr(v.rfbn_id, 1, 2)
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
