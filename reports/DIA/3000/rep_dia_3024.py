# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3024 (процедура REP_R_3024).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Задержка выплат СВбр (0704): макеты, обращение по которым пришлось на
период (`ms.z_date`), а выплата получателю прошла позже конца периода
(`dl.pay_date >= :d_to`). Для каждого: код региона, ИИН, ФИО, дата назначения
и решения, назначенная сумма по макету, выплаченная сумма по документу
выплаты (`pmdl_doc_list_s`), дата выплаты. Платёж ищется по ИИНу получателя в
списке платежа (`dl.rnn = p.iin`).

Период. В оригинале параметр один - дата начала месяца, а конец считался как
`last_day(v_mnth)` («Задержка БИР за <дата>»). Здесь, как у остальных отчётов
группы, - период из двух дат; для оригинального месяца вводится первое и
последнее число месяца.

Причина невалидности процедуры в боевой БД - `ORA-00904: "P.RN"`: колонка
`person.rn` переименована в `person.iin` (решение Шамиля 15.10.2026: везде
меняем на `iin`). Здесь `p.iin`. Период: `z_date between v_mnth and last_day(...)` заменён на `z_date >= :d_from and z_date < :d_to`, `pay_date > last_day(...)` - на `pay_date >= :d_to`. Подписи под таблицей
оригинала («Руководитель / Исполнитель / дата и время создания») и подсказки
оптимизатору не переносятся.

Таблицы `ss_*`, `person` reports_test видит, часть остальных (вьюшки SSWH) нет: проверено запуском на данных боевой БД (только чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3024'
report_name = 'Задержка БИР с {date_from} по {date_to}'

COLUMNS = [
    Col('Код региона', 'brid', 'center', 10),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Дата назначения', 'd_naz', 'date', 14),
    Col('Дата решения', 'd_resh', 'date', 14),
    Col('Назначенная сумма по макету', 'nsum', 'money', 18, total=False),
    Col('Выплаченная сумма', 'pay_sum', 'money', 18, total=False),
    Col('Дата выплаты', 'pay_date', 'date', 14),
]

# :d_from, :d_to - период (d_to исключительная).
STMT = """
select ms.brid, p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       mp.d_naz, ms.d_resh, ms.nsum, sum(dl.pay_sum) pay_sum, dl.pay_date
  from ss_m_sol ms, ss_m_pay mp, person p, pnpd_document pd,
       pmdl_doc_list_s dl
 where ms.id = mp.sid
   and substr(mp.pc, 1, 4) = '0704'
   and mp.soliray_id = pd.source_id
   and p.sicid = ms.sicid
   and pd.mhmh_id = dl.mhmh_id
   and p.iin = dl.rnn
   and dl.pay_date >= :d_to
   and ms.z_date >= :d_from and ms.z_date < :d_to
 group by ms.brid, p.iin,
          p.lastname || ' ' || p.firstname || ' ' || p.middlename,
          mp.d_naz, ms.d_resh, ms.nsum, dl.pay_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True,
)
