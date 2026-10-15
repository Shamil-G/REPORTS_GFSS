# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3314 (процедура REP_R_3314).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Первые утверждённые назначения (`sipr_maket_first_approve_2`) за период по
дате утверждения получателям не с гражданством 105 (Казахстан): гражданство
(`dic_country.ru_name`), вид и номер документа, вид выплаты, даты обращения,
назначения (утверждения) и риска, статус ЭМД.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(sfa.date_approve) between` заменён на `sfa.date_approve >= :d_from and sfa.date_approve < :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_m_*`, `ss_z_doc`, `person` reports_test видит, часть остальных (вьюшка SSWH.V_REFUSE, `dic_country`) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3314'
report_name = 'Список дел социальных выплат назначенных иностранным гражданам с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'rfbn_id', 'center', 10),
    Col('ИИН получателя', 'iin', 'center', 16),
    Col('ФИО получателя', 'fio', 'text', 36),
    Col('Дата рождения получателя', 'birthdate', 'date', 14),
    Col('Гражданство', 'country', 'text', 24),
    Col('Вид документа', 'doc_type', 'text', 24),
    Col('Номер документа', 'docnum', 'center', 16),
    Col('Вид выплаты', 'rfpm_id', 'center', 12),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата назначения', 'date_approve', 'date', 14),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Статус ЭМД', 'st', 'center', 10),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select sfa.rfbn_id, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       p.birthdate, dc.ru_name country, dt.name doc_type, p.docnum,
       sfa.rfpm_id, sfa.date_address, sfa.date_approve, sfa.risk_date,
       (select st from ss_m_sol where id = sfa.sipr_id) st
  from sipr_maket_first_approve_2 sfa, person p, rfdt_doc_type dt,
       dic_country dc
 where p.sicid = sfa.sicp_id
   and p.doctype = dt.rfdt_id
   and p.citizenship_id <> 105
   and sfa.date_approve >= :d_from and sfa.date_approve < :d_to
   and p.citizenship_id = dc.id
 order by sfa.rfbn_id, fio
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
