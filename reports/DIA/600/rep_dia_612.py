# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 612 (процедура REP_R_3317, «Макеты по ЕСП
(список)»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Макеты решений о выплате (`ss_m_sol` + `ss_m_pay`), по которым у получателя
есть отчисления плательщика ЕСП (`em5_sird_reckon_donation.is_esp = 'Y'`),
за период по дате обращения (`ms.z_date`). В последних двух колонках:
«Есть СО» - есть ли по макету отчисления не по ЕСП (`is_esp` не 'Y'), «СО и
ЕСП параллельно» - совпадает ли месяц ЕСП с месяцем обычного отчисления
(`min` по строкам: «Да», если совпало у всех).

Период. `between pDateFrom and pDateTo` оригинала заменён на
`>= :d_from and < :d_to` (введённая дата «по» входит). Название оригинала:
«Макеты по ЕСП<br>По дате обращения с ... по ...».

Ограничение по отделению пользователя (`ms.brid like <код области>%`, в
оригинале у пользователя не центрального аппарата) не переносится: у
веб-отчётов отделения пользователя нет, выводятся все. Подсказка
`first_rows` и закомментированные варианты запроса не переносятся; `unique`
при `group by` по тем же колонкам избыточен.

`p.rn` заменён на `p.iin` (колонка переименована давно). Район - `branch`
(`rfbn_id` = код отделения макета), «код - короткое название», как в
оригинале.

`ss_m_sol`, `ss_m_pay`, `person`, `branch` reports_test видит;
`em5_sird_reckon_donation` лежит в SSWH и недоступна, поэтому запрос целиком
на данных не сверен, только синтаксис.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '612'
report_name = 'Макеты по ЕСП\nПо дате обращения с {date_from} по {date_to}'

COLUMNS = [
    Col('Регион', 'region', 'text', 28),
    Col('ФИО', 'fio', 'text', 36),
    Col('ИИН', 'iin', 'center', 16),
    Col('Дата рождения', 'birthdate', 'date', 14),
    Col('Пол', 'pol', 'center', 6),
    Col('Дата обращения', 'z_date', 'date', 14),
    Col('Вид выплаты', 'pc', 'center', 12),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Сумма', 'nsum', 'money', 16, total=False),
    Col('Статус', 'st', 'center', 10),
    Col('Есть СО', 'have_so', 'center', 10),
    Col('СО и ЕСП параллельно', 'have_parallel_so', 'center', 14),
]

# :d_from, :d_to - период по дате обращения (d_to исключительная).
STMT = """
select ms.brid || ' - ' || b.short_name region,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       p.iin,
       p.birthdate,
       (case when p.sex = 1 then 'М' else 'Ж' end) pol,
       ms.z_date,
       mp.pc,
       mp.d_naz,
       mp.nsum,
       ms.st,
       (case when e2.sipr_id is not null then 'Да' else 'Нет' end) have_so,
       min(case when e.pay_month = e2.pay_month then 'Да' else 'Нет' end)
           have_parallel_so
  from ss_m_sol ms
  join ss_m_pay mp on ms.mpay = mp.id
  join person p on ms.sicid = p.sicid
  join branch b on ms.brid = b.rfbn_id
  join em5_sird_reckon_donation e
    on e.sipr_id = ms.id and nvl(e.is_esp, 'N') = 'Y'
  left join em5_sird_reckon_donation e2
    on ms.id = e2.sipr_id and nvl(e2.is_esp, 'N') = 'N'
 where ms.z_date >= :d_from and ms.z_date < :d_to
 group by ms.brid, ms.id, b.short_name, p.birthdate,
          p.lastname || ' ' || p.firstname || ' ' || p.middlename,
          p.iin, p.sex, ms.z_date, mp.pc, mp.d_naz, mp.nsum, ms.st,
          e2.sipr_id
 order by ms.brid, p.lastname || ' ' || p.firstname || ' ' || p.middlename
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
