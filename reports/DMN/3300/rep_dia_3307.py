# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3307 (процедура REP_R_3307).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатели СВут (0702) с назначением за период, у которых дата окончания
выплаты (`mp.stopdate`) позже положенной по возрасту. Положенная дата - день
перед достижением пенсионного возраста: мужчины 63 года; женщины, родившиеся
до 01.07.1960, - 58,5 лет, далее возраст растёт на полгода за каждые полгода
года рождения (01.07.1960-31.12.1960 - 59, ... с 01.07.1964 - 63 года).
«Возраст» - полных лет на положенную дату окончания. Последнее назначение по
делу. В оригинале даты границ были строками (`'01.01.1960'`), зависящими от
формата даты сессии; здесь `date '...'`, а `between` заменён на `>= и <`.
Колонки «Дата окончания» оригинала названы по смыслу (`SetPageHead`): «по
ЭМД» и «по получателю». В названии латинские «c» исправлены.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `trunc(mp.d_naz) between` заменён на `>= :d_from and < :d_to` (введённая дата «по» входит). Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы reports_test видит - отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3307'
report_name = 'Список получателей СВут с неверной датой окончания с {date_from} по {date_to} года'

COLUMNS = [
    Col('Код отделения', 'brid', 'center', 10),
    Col('ИИН получателя', 'iin', 'center', 16),
    Col('ФИО получателя', 'fio', 'text', 36),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Пол', 'sex', 'center', 10),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата окончания по ЭМД', 'stopdate', 'date', 14),
    Col('Дата окончания по получателю', 'need_stopdate', 'date', 14),
    Col('Возраст', 'let', 'money', 10, total=False),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select t.brid, t.iin, t.fio, t.birthdate, t.sex, t.pc, t.date_address,
       t.d_naz, t.stopdate, t.need_stopdate,
       round(months_between(t.need_stopdate, t.birthdate) / 12, 2) let
  from (
    select ms.brid, p.iin,
           p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
           p.birthdate,
           case when p.sex = 1 then 'Мужской' else 'Женский' end sex,
           mp.pc, ms.z_date date_address, mp.d_naz, mp.stopdate,
           case
             when p.sex = 0 and p.birthdate >= date '1960-01-01' and p.birthdate < date '1960-07-01' then add_months(p.birthdate, 58*12+6) - 1
             when p.sex = 0 and p.birthdate >= date '1960-07-01' and p.birthdate < date '1961-01-01' then add_months(p.birthdate, 59*12) - 1
             when p.sex = 0 and p.birthdate >= date '1961-01-01' and p.birthdate < date '1961-07-01' then add_months(p.birthdate, 59*12+6) - 1
             when p.sex = 0 and p.birthdate >= date '1961-07-01' and p.birthdate < date '1962-01-01' then add_months(p.birthdate, 60*12) - 1
             when p.sex = 0 and p.birthdate >= date '1962-01-01' and p.birthdate < date '1962-07-01' then add_months(p.birthdate, 60*12+6) - 1
             when p.sex = 0 and p.birthdate >= date '1962-07-01' and p.birthdate < date '1963-01-01' then add_months(p.birthdate, 61*12) - 1
             when p.sex = 0 and p.birthdate >= date '1963-01-01' and p.birthdate < date '1963-07-01' then add_months(p.birthdate, 61*12+6) - 1
             when p.sex = 0 and p.birthdate >= date '1963-07-01' and p.birthdate < date '1964-01-01' then add_months(p.birthdate, 62*12) - 1
             when p.sex = 0 and p.birthdate >= date '1964-01-01' and p.birthdate < date '1964-07-01' then add_months(p.birthdate, 62*12+6) - 1
             when p.sex = 0 and p.birthdate >= date '1964-07-01' then add_months(p.birthdate, 63*12) - 1
             when p.sex = 1 then add_months(p.birthdate, 63*12) - 1
           end need_stopdate
      from ss_m_sol ms, ss_m_pay mp, ss_data sd, person p
     where mp.id = ms.mpay
       and mp.pc like '0702%'
       and mp.id = (select max(id) from ss_m_pay where soliray_id = mp.soliray_id)
       and mp.d_naz >= :d_from and mp.d_naz < :d_to
       and ms.id = sd.sipr_id
       and p.sicid = sd.sicp_id) t
 where t.stopdate > t.need_stopdate
 order by t.brid
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
