# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Формы статотчётности в Мин. труд. 2014», отчёт 1366 (процедура REP_R_1366).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Список к форме «Сведения о числе получателей и суммах социальных выплат
(в разрезе принадлежности к полу)»: первые утверждённые назначения (вьюшка
`v_sipr_maket_first_approve_dn`) за период по дате утверждения, при желании
только одного вида выплаты (первые четыре знака кода). Колонки: отделение,
код выплаты, ИИН, ФИО, пол, дата риска, обращения, назначения и окончания,
назначенный размер, статус по Е-макету.

Параметр «вид выплаты» необязательный: пусто - все (в оригинале
`like nvl(pRfpm, '') || '%'`).

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(sfa.date_approve) between` заменён на `sfa.date_approve >= :d_from and sfa.date_approve < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит не все (часть в SSWH): проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '1366'
report_name = 'Список к сведениям о числе получателей и суммах социальных выплат (в разрезе принадлежности к полу), с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'rfbn_id', 'center', 10),
    Col('Код выплаты', 'rfpm_id', 'center', 14),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Пол', 'sex', 'center', 8),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата окончания', 'stopdate', 'date', 14),
    Col('Назначенный размер', 'sum_all', 'money', 16, total=False),
    Col('Статус по е-макет', 'st', 'center', 12),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select sfa.rfbn_id, sfa.rfpm_id, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       case when p.sex = 1 then 'М' else 'Ж' end sex,
       sfa.risk_date, sfa.date_address, sfa.d_naz, sfa.stopdate, sfa.sum_all,
       sfa.st
  from v_sipr_maket_first_approve_dn sfa, person p
 where p.sicid = sfa.sicp_id
   and sfa.date_approve >= :d_from and sfa.date_approve < :d_to
   and sfa.rfpm_id like :rfpm_id || '%'
 order by sfa.rfbn_id, fio
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
