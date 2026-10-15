# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 605 (процедура REP_R_605_RB).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения из реестра беременных и женщин фертильного возраста по ИИН:
строки реестра `preg_registry` по женщине - наблюдение, роды, больничные
листы по беременности.

Источник - `preg_registry`, отбор по `iin`, сортировка по дате взятия на
учёт. Название - «Сведения из реестра беременных и женщин фертильного
возраста» с ИИН и ФИО (`initcap`) получателя из `person`; нет человека -
«Не найдена информация по ИИН: <...>!», неверная длина - «Неверно указан
ИИН!» (оба текста как в оригинале).

Процедура AIS написана на отдельном пакете `rep_web` (не `rep`) - логика та
же. Шапка - из `SetPageHead`: после десяти общих колонок группа «Сведения о
больничном» из восьми (серия, номер листа, дата выдачи, с какого и по какое
число, диагноз, место работы, должность).

`preg_registry` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна: на данных отчёт не сверен (типы колонок взяты из слепка
`prod_tab_columns`: все даты реестра - `DATE`).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '605'
report_name = ('Сведения из реестра беременных и женщин фертильного возраста\n'
               'ИИН: {iin}\n'
               'ФИО: {fio}')

COLUMNS = [
    Col('Область', 'region', 'text', 22),
    Col('ФИО пациента', 'fio', 'text', 34),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('ИИН', 'iin', 'center', 16),
    Col('Адрес проживания регистрации', 'reg_address', 'text', 40),
    Col('Наименование медицинской организации, которая ведет наблюдение '
        'пациента', 'med_org', 'text', 40),
    Col('Дата взятия на учет по беременности и родам', 'p_reg_date',
        'date', 18),
    Col('Дата родов', 'newborn_date', 'date', 14),
    Col('Исход беременности', 'outcome', 'text', 24),
    Col('Дата снятия с учета после родов', 'p_dereg_date', 'date', 18),
    Group('Сведения о больничном', [
        Col('Серия', 'sl_series', 'center', 10),
        Col('№ листка нетрудоспособности по беременности', 'sl_number',
            'center', 20),
        Col('Дата выдачи', 'sl_issue_date', 'date', 14),
        Col('С какого числа', 'sl_start_date', 'date', 14),
        Col('По какое число', 'sl_finish_date', 'date', 14),
        Col('Диагноз', 'sl_diagnosis', 'text', 30),
        Col('Место работы', 'sl_work_place', 'text', 30),
        Col('Должность', 'sl_work_position', 'text', 24),
    ]),
]


def _check(params):
    if len(str(params.get('iin') or '').strip()) != 12:
        raise ValueError('Неверно указан ИИН!')


# Реквизиты в названии: ФИО человека по ИИН (initcap, как в оригинале).
TITLE_SQL = """
select initcap(lastname || ' ' || firstname || ' ' || middlename) fio
  from person
 where iin = :iin
"""

# :iin - ИИН из формы.
STMT = """
select region, fio, birthdate, iin, reg_address, med_org, p_reg_date,
       newborn_date, outcome, p_dereg_date, sl_series, sl_number,
       sl_issue_date, sl_start_date, sl_finish_date, sl_diagnosis,
       sl_work_place, sl_work_position
  from preg_registry
 where iin = :iin
 order by p_reg_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('iin',),
    title_sql=TITLE_SQL,
    title_not_found='Не найдена информация по ИИН!',
)
