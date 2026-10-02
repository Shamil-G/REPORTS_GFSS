# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3328 (процедура REP_R_3328).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения по выплатам 42500 по области: два этапа обращения (первое и
повторное) в одном списке, решения со статусами отказа и назначения.

Источник и колонки те же, что в 3326 (`all_list_42500` + `person` +
`ss_m_sol_st`). Отличия от 3326 - в отборе:
  - 1-й этап: `st_code1 in (12, 37, 20)`, 2-й этап не в отказе
    (`st_code2` пусто, 0, 12 или 20); дата обращения в периоде;
  - 2-й этап: `st_code2 in (12, 20)`, на 1-м этапе пусто, 0, 37 или 12;
    дата обращения 2-го этапа в периоде.
В отличие от 3326 здесь период применяется к обоим этапам одинаково
(`between :первая and :вторая` в обеих частях).

Название: «Сведения по выплатам 42500», «с» перед датой кириллическая (в оригинале
латинская «c»); в справочнике AIS отчёт назван «Сведения выплатам 42500 в разрезе
причин» (пропущено «по», в списке исправлено).
Сортировка `order by 1, 5` относится ко всему объединению. Скалярные
подзапросы справочников - как в оригинале. Заголовки - из `SetPageHead`
(латинская «C» в «Статус» исправлена). Закомментированный первый вариант запроса
оригинала не переносится.

`all_list_42500`, `rfms_m_sol`, `s_resh_ret` лежат в схеме SSWH боевой БД, в
тестовой reports_test недоступны: на данных отчёт не сверен.

ИИН: в оригинале `person.rn`, но в `person` сейчас колонка `iin` (подтверждено
Шамилем 02.10.2026), здесь `person.iin`. Оригинал с `rn` давно не выполняется
(запрос динамический, ошибка глоталась), поэтому отчёт мог не использоваться год-два:
стоит подтвердить, нужен ли он.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3328'
report_name = 'Сведения по выплатам 42500 с {period}\n\nКод региона: {rfbn_id}'

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
select a.rfbn_id,
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
   and a.date_obr_p1 <  :d_to
   and a.st_code1 in (12, 37, 20)
   and coalesce(a.st_code2, 0) in (0, 12, 20)
   and substr(a.rfbn_id, 1, 2) = substr(:rfbn_id, 1, 2)
union all
select b.rfbn_id,
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
   and b.date_obr_p2 >= :d_from
   and b.date_obr_p2 <  :d_to
   and b.st_code2 in (12, 20)
   and coalesce(b.st_code1, 0) in (0, 37, 12)
   and substr(b.rfbn_id, 1, 2) = substr(:rfbn_id, 1, 2)
 order by 1, 5
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, title_params=('rfbn_id',),
)
