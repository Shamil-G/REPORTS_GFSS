# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Обороты и назначения», отчёт 6, часть 1 «Назначения»
(процедура P_ALL_INFO).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Процедура `p_all_info` строила для участника системы (по внутреннему номеру
СИК) две таблицы подряд: «Информация по назначениям социальных выплат» и
«Информация о состоянии и движении социальных отчислений» (обороты). Формат
отчётов приложения - одна таблица на листе, поэтому отчёт разделён на два:
6-1 «Назначения» (этот) и 6-2 «Обороты» (`rep_dia_6_2.py`).

Параметр. В AIS человек выбирался в картотеке (СИК). Здесь - ИИН
(`person.iin`; в оригинале `iper.rn`, причина невалидности процедуры в боевой
БД - `ORA-00904`, колонка переименована, решение Шамиля 15.10.2026).

Первые назначения. Оригинал читает `sipr_maket_first_approve`, застывшую на
28.02.2023 (последняя `date_approve`); для назначений позже оригинал печатает
«Назначения отсутствуют». Здесь актуальная `sipr_maket_first_approve_2`.

Отбор: все назначения человека - действующие (`sipr_payer` + `sifl_file`) и
макеты (`sipr_payer_maket` + `sifl_file_maket`) - с названием вида
(`rfpm_payments`) и инспектором (`s_emp`), по возрастанию даты первого
назначения (`sipr_maket_first_approve`). Если у человека нет ни одного
первого назначения, оригинал печатал «Назначения отсутствуют» вместо таблицы;
здесь то же условие в запросе, лист получается «Нет данных для отображения».

Доступ и журнал. Отчёт содержит персональные данные и помечен в
`list_reports.py` признаком `audit`: каждое обращение (запрос с ИИН, выдача,
отказ, ошибка) пишется в `log_reports` процедурой `util.log_reports`
(`util/access_audit.py`), файл формируется на каждый запрос заново с уникальным
именем и удаляется сразу после отправки. Проверка людей из `notobor` («Доступ
запрещен!»), как в оригинале, - `util/person_access.py`. Это заменило запись
оригинала в `sic_log` (автономная транзакция).

Суммы в оригинале выводились строкой в жирном; здесь числа. Таблицы reports_test
не все видит (часть в SSWH): проверено запуском на данных боевой БД (только
чтение).
"""
from db.connect import LOADER_PROFILE
from util.person_access import check_person_access
from util.xlsx_report import build_report, Col

report_code = '6-1'
report_name = ('Информация по назначениям социальных выплат\n'
               'ФИО: {fio}\n'
               'ИИН: {iin}')


COLUMNS = [
    Col('Вид риска', 'shortname', 'text', 40),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('Дата обращения', 'date_address', 'date', 14),
    Col('Дата назначения', 'approve_date', 'date', 14),
    Col('Дата первого назначения', 'date_first_approve', 'date', 14),
    Col('Дата окончания', 'stop_date', 'date', 14),
    Col('Статус', 'state', 'center', 10),
    Col('Примечание', 'notes', 'text', 30),
    Col('Расчетная сумма', 'sum_calc', 'money', 16, total=False),
    Col('Назначенная сумма', 'sum_all', 'money', 16, total=False),
    Col('Сумма доплаты', 'sum_dop', 'money', 16, total=False),
    Col('Инспектор', 'emp_name', 'text', 30),
]

# ФИО (initcap) и ИИН человека; нет человека или он в списке запрета -
# ошибка (как raise в оригинале).
TITLE_SQL = """
select initcap(p.lastname || ' ' || p.firstname || ' ' || p.middlename) fio
  from person p
 where p.iin = trim(:iin)
"""

# :iin - ИИН человека.
STMT = """
select rp.rfpm_id || ' - ' || rp.shortname shortname,
       d.risk_date, d.date_address, d.approve_date,
       (select fa.date_approve from sipr_maket_first_approve_2 fa
         where fa.sipr_id = d.sipr_id) date_first_approve,
       d.stop_date, d.state, d.notes, d.sum_calc, d.sum_all, d.sum_dop,
       se.vcusername || ' - ' || se.name emp_name
  from (select p.sipr_id, p.rfpm_id, p.emp_id, p.risk_date, p.date_address,
               p.approve_date, p.stop_date, p.state, p.notes, p.sum_calc,
               p.sum_all, p.sum_dop
          from sipr_payer p, sifl_file fl, person pr
         where fl.sipr_id = p.sipr_id and pr.sicid = fl.sicp_id
           and pr.iin = trim(:iin)
        union all
        select p.sipr_id, p.rfpm_id, p.emp_id, p.risk_date, p.date_address,
               p.approve_date, p.stop_date, p.state, p.notes, p.sum_calc,
               p.sum_all, p.sum_dop
          from sipr_payer_maket p, sifl_file_maket fl, person pr
         where fl.sipr_id = p.sipr_id and pr.sicid = fl.sicp_id
           and pr.iin = trim(:iin)) d,
       rfpm_payments rp, s_emp se
 where d.rfpm_id = rp.rfpm_id
   and d.emp_id = se.emp_id
   and exists (select 1 from sipr_maket_first_approve_2 fa, person pr
                where fa.sicp_id = pr.sicid and pr.iin = trim(:iin))
 order by date_first_approve
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=check_person_access, title_params=('iin',),
    title_sql=TITLE_SQL, title_not_found='Участник не найден!',
)
