# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3326 (процедура REP_R_3326).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения по отказным выплатам 42500 в разрезе причин по области: два этапа
обращения (первое и повторное) в одном списке, только отказы (статус 12).

Источник - `all_list_42500` (по человеку - данные 1-го и 2-го этапа:
`*_p1`, `*_p2`) + `person` + `ss_m_sol_st` (причина отказа: `ret_id`,
`ret_txt`; внешнее соединение по номеру дела и статусу). Название статуса и
причины - скалярные подзапросы `rfms_m_sol` и `s_resh_ret`, как в оригинале
(справочники по ключу, строка единственная; если когда-нибудь станет две -
запрос упадёт, а не размножит строки).

Первая часть - отказ на 1-м этапе (`st_code1 = 12`) без 2-го этапа или с
отказом на 2-м; вторая - отказ на 2-м этапе без решения на 1-м. Область -
первые два знака `rfbn_id`.

ВАЖНО, как в оригинале даты разнесены по частям: нижняя граница периода
(`date_first`) применяется только к первому этапу (`date_obr_p1 >=`), а
верхняя (`date_second`) - только ко второму (`date_obr_p2 <=`). То есть
отчёт «с даты» для 1-го этапа и «по дату» для 2-го. Перенесено буквально,
поведение стоит подтвердить у заказчика (ДМЭН): похоже на недоработку
оригинала, но менять без согласования нельзя. Верхняя граница, как всегда в
переносимых отчётах, - `< :d_to` (сутки после даты «по»).

Сортировка `order by 1, 5` относится ко всему объединению. Закомментированные
в оригинале поля второго этапа не переносятся. Заголовки - из `SetPageHead`
(латинская «C» в «Статус» исправлена).

`all_list_42500`, `rfms_m_sol`, `s_resh_ret` лежат в схеме SSWH боевой БД, в
тестовой reports_test недоступны: на данных отчёт не сверен.

ИИН: в оригинале `person.rn`, но в `person` сейчас колонка `iin` (подтверждено
Шамилем 02.10.2026), здесь `person.iin`. Оригинал с `rn` давно не выполняется
(запрос динамический, ошибка глоталась), поэтому отчёт мог не использоваться год-два:
стоит подтвердить, нужен ли он.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3326'
report_name = ('Сведения по отказным выплатам 42500 в разрезе причин '
               'с {period}\n\nКод региона: {rfbn_id}')

COLUMNS = [
    Col('Код отделения', 'rfbn_id', 'center', 12),
    Col('ИИН', 'rn', 'center', 16),
    Col('ФИО', 'fio', 'text', 40),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Дата обращения', 'date_obr_p1', 'date', 14),
    Col('Дата назначения', 'd_naz_p1', 'date', 14),
    Col('Сумма', 'sum_p1', 'money', 16),
    Col('Статус', 'st', 'text', 30),
    Col('Причина отказа', 'resh', 'text', 40),
    Col('Комментарии', 'ret_text', 'text', 40),
]

# :d_from / :d_to - период из формы, :d_to исключительная; :rfbn_id - область.
STMT = """
select /*+parallel(4)*/
       a.rfbn_id,
       p.iin rn,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename as fio,
       p.birthdate,
       a.date_obr_p1,
       a.d_naz_p1,
       a.sum_p1,
       a.st_code1 || ' - ' || (select rs.name from rfms_m_sol rs
                                where a.st_code1 = rs.id_state) st,
       (select r.name from s_resh_ret r where r.id = st.ret_id) resh,
       st.ret_txt ret_text
  from all_list_42500 a, person p, ss_m_sol_st st
 where a.sicid = p.sicid
   and st.sid(+)  = a.id_p1
   and st.s_st(+) = a.st_code1
   and a.date_obr_p1 >= :d_from
   and a.st_code1 = 12
   and coalesce(a.st_code1, 0) in (12)
   and coalesce(a.st_code2, 0) in (0, 12)
   and a.st_code2_2 is null
   and substr(a.rfbn_id, 1, 2) = substr(:rfbn_id, 1, 2)
union all
select /*+parallel(4)*/
       b.rfbn_id,
       p.iin rn,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename as fio,
       p.birthdate,
       b.date_obr_p2,
       b.d_naz_p2,
       b.sum_p2,
       b.st_code2 || ' - ' || (select rs.name from rfms_m_sol rs
                                where b.st_code2 = rs.id_state) st,
       (select r.name from s_resh_ret r where r.id = sol.ret_id) resh,
       sol.ret_txt ret_text
  from all_list_42500 b, person p, ss_m_sol_st sol
 where b.sicid = p.sicid
   and sol.sid(+)  = b.id_p2
   and sol.s_st(+) = b.st_code2
   and b.date_obr_p2 < :d_to
   and coalesce(b.st_code2, 0) in (12)
   and coalesce(b.st_code1, 0) in (0)
   and b.st_code1_2 is null
   and substr(b.rfbn_id, 1, 2) = substr(:rfbn_id, 1, 2)
 order by 1, 5
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, title_params=('rfbn_id',),
)
