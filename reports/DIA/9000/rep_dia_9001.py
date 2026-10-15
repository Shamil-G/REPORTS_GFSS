# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Список плательщиков без подтверждения трудовых отношений с получателями СВбр, СВур», отчёт 9001 (процедура REP_R_9001).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Договоры ИП (`contract_9001`) с лицами из таблицы `non_employee_9001` по ИИН ИП: № и
дата заключения, ФИО и ИИН ИП, регион (`branch.short_name` по `payer_region`), ИИН,
ФИО и статус лица на момент заявления. «Лица, не являющиеся наемными работниками у ИП» - группа колонок.

Название. Заголовок оригинала был скопирован из отчёта «Сведения из реестра
беременных и женщин фертильного возраста» (605) и к содержанию не относился;
здесь название - как в списке отчётов AIS. ФИО в названии - `initcap`. Нет
человека по ИИНу - «Не найдена информация по ИИН» (в оригинале
`raise_application_error` с ИИН).

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит не все (часть в SSWH): проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '9001'
report_name = 'Список лиц, не являющихся наемными работниками\nИИН ИП: {iin}\nФИО: {fio}'


def _check(params):
    if len(str(params.get('iin') or '').strip()) != 12:
        raise ValueError('Введен неправильный ИИН!')


TITLE_SQL = """
select initcap(lastname || ' ' || firstname || ' ' || middlename) fio
  from person
 where iin = trim(:iin)
"""

COLUMNS = [
    Col('№ Заключения', 'contract_id', 'center', 14),
    Col('Дата заключения', 'contract_date', 'date', 14),
    Col('ФИО ИП', 'payer_name', 'text', 36),
    Col('ИИН ИП', 'payer_iin', 'center', 16),
    Col('Регион', 'short_name', 'text', 24),
    Group('Лица, не являющиеся наемными работниками у ИП', [
        Col('ИИН', 'iin', 'center', 16),
        Col('ФИО', 'name', 'text', 36),
        Col('Статус на момент заявления', 'status', 'center', 14),
    ]),
]

# :iin - ИИН ИП (форма).
STMT = """
select c.contract_id, c.contract_date, c.payer_name, c.payer_iin,
       b.short_name, e.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename name, e.status
  from contract_9001 c, non_employee_9001 e, branch b, person p
 where c.contract_id = e.contract_id
   and c.payer_iin = trim(:iin)
   and b.rfbn_id = c.payer_region
   and p.iin = e.iin
 order by c.contract_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('iin',), title_sql=TITLE_SQL,
    title_not_found='Не найдена информация по ИИН!',
)
