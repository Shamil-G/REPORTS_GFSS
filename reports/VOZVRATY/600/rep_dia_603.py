# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 603 (процедура REP_PROT_NEW).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Протокол операций по делу получателя: обращение и все действия над макетом
дела (`siap_action_protocol`) в хронологическом порядке, с исполнителем,
отделением и IP компьютера.

Параметры. В AIS дело выбиралось в картотеке и в процедуру уходил внутренний
`sipr_id`. Пользователю отчётов он неизвестен, поэтому форма принимает ИИН
получателя и номер дела (`sifl_file.file_numb`); `sipr_id` находится по ним.
Дело не найдено - ошибка. Как в оригинале, сначала ищется
действующее дело (`sipr_payer`, `sifl_file`), при отсутствии - макет
(`sipr_payer_maket`, `sifl_file_maket`).

Название: ФИО и дата рождения получателя, номер дела, вид выплаты (код и
название). В оригинале «Протокол операций получателя ... года рождения»;
опечатка названия списка («Потокол») исправлена.

Строки: первая - «Обращение, подача заявления» с датой обращения дела
(`date_address`), остальные - действия по архивам дела (`sipr_payer_maket_arc`
и `sipr_payer_arc`). Текст операции: для действия 101 - примечание без «№»,
иначе «состояние - название состояния». Исполнитель и отделение выбираются
по состоянию дела: департамент МТиСЗН (состояния 2-5), контролёр ГЦВП
(2, 3, 6-8), специалист ГЦВП; имена сотрудников и отделений - функции схемы
SSWH `emp_name1`, `branch_name`, `s_region_name2`, `rfpm_name` (как в
оригинале).

Шапка - из `SetPageHead` (пять колонок). Дата операции содержит время,
выводится текстом `dd.mm.yyyy hh24:mi:ss`. Колонка «IP компьютера» в
оригинале числовая (`'N'`), IP - строка, выводится текстом.

Все таблицы лежат в схеме SSWH боевой БД, в тестовой reports_test
недоступны: на данных отчёт не сверен (типы колонок взяты из слепка
`prod_tab_columns`).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '603'
report_name = ('Протокол операций получателя {fio}\n'
               'Номер дела - {file_numb}\n'
               'Вид выплаты - {rfpm}')

COLUMNS = [
    Col('Дата операции', 'date_calc', 'center', 20),
    Col('Наименование операции', 'rname', 'text', 56),
    Col('Исполнитель операции', 'insp', 'text', 40),
    Col('Отделение', 'otd', 'text', 40),
    Col('IP компьютера', 'ip_pc', 'center', 18),
]

# Дело по ИИНу и номеру: сначала действующее (src 1), при отсутствии - макет
# (src 2), как два select ... into в оригинале. Подставляется в начало запроса.
_WITH = """
with found as (
  select fl.sipr_id, p.lastname, p.firstname, p.middlename, p.birthdate,
         sn.file_numb, fl.rfpm_id, 1 src
    from sipr_payer fl, person p, sifl_file sn
   where fl.sipr_id = sn.sipr_id and fl.sicp_id = p.sicid
     and p.iin = :iin and sn.file_numb = :file_numb
  union all
  select fl.sipr_id, p.lastname, p.firstname, p.middlename, p.birthdate,
         sn.file_numb, fl.rfpm_id, 2 src
    from sipr_payer_maket fl, person p, sifl_file_maket sn
   where fl.sipr_id = sn.sipr_id and fl.sicp_id = p.sicid
     and p.iin = :iin and sn.file_numb = :file_numb),
f as (select * from found where src = (select min(src) from found))
"""

TITLE_SQL = _WITH + """
select lastname || ' ' || firstname || ' ' || middlename
       || ' ' || to_char(birthdate, 'dd.mm.yyyy') || ' года рождения' fio,
       file_numb,
       rfpm_id || ' ' || rfpm_name(rfpm_id) rfpm
  from f
 where rownum = 1
"""


def _check(params):
    if len(str(params.get('iin') or '').strip()) != 12:
        raise ValueError('Неверно указан ИИН!')
    if not str(params.get('file_numb') or '').strip():
        raise ValueError('Не указан номер дела!')


# :iin, :file_numb - форма. Архивы дела (макет и действующее) объединены,
# как в оригинале.
STMT = _WITH + """
select to_char(x.date_calc, 'dd.mm.yyyy hh24:mi:ss') date_calc,
       x.rname, x.insp, x.otd, x.ip_pc
  from (
    select d.date_address date_calc, 'Обращение, подача заявления' rname,
           null insp, null otd, null ip_pc
      from sipr_payer d
     where d.sipr_id in (select sipr_id from f)
    union all
    select si.date_calc,
           (case when si.act_id = 101 then replace(si.notes, '№', '')
                 else d.state || ' - ' || ms.name_ru end) rname,
           (case when d.id_department is not null
                      and d.state in (2, 3, 4, 5) and si.act_id != 101
                 then 'Департамент МТиСЗН -  ' || emp_name1(d.id_department)
                 when d.cntrl_id is not null
                      and d.state in (2, 3, 6, 7, 8) and si.act_id != 101
                 then 'Контролер ГЦВП -  ' || emp_name1(d.cntrl_id)
                 when d.emp_id is not null and si.act_id != 101
                 then 'Специалист ГЦВП - ' || emp_name1(d.emp_id)
                 when si.act_id = 101
                 then 'Специалист ГЦВП - ' || emp_name1(si.emp_id)
                 else null end) insp,
           (case when d.id_department is not null
                      and d.state in (2, 3, 4, 5)
                 then 'Департамент МТиСЗН по ' || s_region_name2(si.rfbn_id)
                 else branch_name(si.rfbn_id) end) otd,
           si.ip_pc
      from (select * from sipr_payer_maket_arc
             where sipr_id in (select sipr_id from f)
            union all
            select * from sipr_payer_arc
             where sipr_id in (select sipr_id from f)) d,
           siap_action_protocol si, srms_maket_state ms
     where d.actp_id = si.actp_id
       and d.state = ms.state) x
 order by x.date_calc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check,
    title_sql=TITLE_SQL,
    title_not_found='Дело получателя не найдено!',
)
