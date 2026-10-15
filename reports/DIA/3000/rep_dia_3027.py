# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3027 (процедура REP_R_3027).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Список лиц, которым назначена социальная выплата одного вида (первые четыре
знака кода, параметр «Вид выплаты») за период по дате утверждения, с учётом
ЕСП: ИИН, ФИО, пол, дата риска, СМД, КЗД, МЗП, число месяцев, назначенный
размер, дата назначения и два признака по платежам за 24 месяца до
назначения (`si_member_2`): «Есть СО» - были обычные социальные отчисления
(не ЕСП), «СО и ЕСП параллельно» - были и ЕСП, и обычные. Человек без
платежей за этот срок в список не попадает (как во внутреннем соединении
оригинала).

Рабочая таблица. Оригинал в динамическом SQL пересоздавал таблицу
`sipr_maket_list` (`drop table` + `create table as select`, ошибки глотались,
и в том числе `person.rn`, которой больше нет), а затем читал её. Отчёты
приложения читают БД только на чтение, поэтому та же выборка стоит в запросе
как `with t`.

Плательщик ЕСП: в оригинале `si.type_payer = 'Е'` (кириллическая «Е»), в
данных латинская `E` (см. 610); здесь латинская, как задумано.
`trunc(date_approve) between` заменён на `date_approve >= :d_from and
date_approve < :d_to`; граница 24 месяцев - `pay_date >= add_months(date_approve,
-24) and pay_date < trunc(date_approve) + 1` (платёж включительно по день
утверждения, как `between` оригинала). Колонки названы по `SetPageHead`
(в AddCol были цифры «0-», «1-», ...). `person.rn` заменён на `person.iin`.
Название: «c учетом» - латинская «c» исправлена. Подсказка `parallel(8)` не
переносится.

Таблицы reports_test видит; проверено запуском на данных боевой БД (только
чтение).
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3027'
report_name = ('Список лиц, которым назначена социальная выплата с учетом ЕСП '
               'с {date_from} по {date_to} года\n'
               'Вид выплаты: {rfpm}')

COLUMNS = [
    Col('Код региона', 'rfbn_id', 'center', 10),
    Col('Код выплаты', 'rfpm_id', 'center', 14),
    Col('ИИН', 'iin', 'center', 16),
    Col('ФИО', 'fio', 'text', 36),
    Col('Пол', 'sx', 'center', 6),
    Col('Дата риска', 'risk_date', 'date', 14),
    Col('СМД, тенге', 'sum_avg', 'money', 16, total=False),
    Col('КЗД', 'kzd', 'money', 10, total=False),
    Col('МЗП', 'mrzp', 'money', 12, total=False),
    Col('Количество месяцев', 'count_donation', 'int', 12, total=False),
    Col('Назначенный размер, тенге', 'sum_all', 'money', 16, total=False),
    Col('Дата назначения', 'date_approve', 'date', 14),
    Col('Есть СО', 'have_so', 'center', 10),
    Col('СО и ЕСП параллельно', 'have_parallel', 'center', 14),
]


def _check(params):
    if len(str(params.get('rfpm') or '').strip()) < 4:
        raise ValueError('Не указан вид выплаты (4 знака)!')


# :d_from, :d_to - период по дате утверждения (d_to исключительная);
# :rfpm - вид выплаты (первые 4 знака).
STMT = """
with t as (
    select s.rfbn_id, s.rfpm_id, p.iin, p.lastname, p.firstname, p.middlename,
           p.sex, s.risk_date, s.sum_avg, s.kzd, s.mrzp, s.sum_all,
           s.count_donation, p.sicid, s.date_approve
      from sipr_maket_first_approve_2 s, person p
     where s.date_approve >= :d_from and s.date_approve < :d_to
       and substr(s.rfpm_id, 1, 4) = substr(trim(:rfpm), 1, 4)
       and p.sicid = s.sicp_id
)
select rfbn_id, rfpm_id, iin,
       lastname || ' ' || firstname || ' ' || middlename fio,
       case when sex = 0 then 'Ж' else 'М' end sx,
       risk_date, sum_avg, kzd, mrzp, count_donation, sum_all, date_approve,
       case when is_no_esp > 0 then 'Да' else 'Нет' end have_so,
       case when is_esp > 0 and is_no_esp > 0 then 'Да' else 'Нет' end have_parallel
  from (select t.rfbn_id, t.rfpm_id, t.iin, t.lastname, t.firstname,
               t.middlename, t.sex, t.risk_date, t.sum_avg, t.kzd, t.mrzp,
               t.count_donation, t.sum_all, trunc(t.date_approve) date_approve,
               sum(case when si.type_payer = 'E' then 1 else 0 end) is_esp,
               sum(case when si.type_payer != 'E' or si.type_payer is null
                        then 1 else 0 end) is_no_esp
          from si_member_2 si, t
         where si.sicid = t.sicid
           and si.pay_date >= add_months(t.date_approve, -24)
           and si.pay_date <  trunc(t.date_approve) + 1
         group by t.rfbn_id, t.rfpm_id, t.iin, t.lastname, t.firstname,
                  t.middlename, t.sex, t.risk_date, t.sum_avg, t.kzd, t.mrzp,
                  t.count_donation, t.sum_all, trunc(t.date_approve)) c
 order by rfbn_id, iin
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=_check,
    title_params=('rfpm',),
)
