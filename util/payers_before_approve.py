# -*- coding: utf-8 -*-
"""Общая сборка отчётов «Социальные выплаты на случай потери дохода ...»:
AIS 3322 (пакет PKG_SVBR_ALL, СВбр, 0704) и 3323 (PKG_SVUR_ALL, СВур, 0705).

Пакеты отличаются только видом выплаты, числом месяцев назад (13 и 25), полом
получателя (СВур - только мужчины, `p.sex = 1`) и дополнительным отбором
платежей СВур по дате платёжки. Модули `reports/DMN/3300/rep_dia_3322.py`,
`rep_dia_3323.py` только задают эти значения.

Что делает отчёт. Получатели, которым назначена выплата (первое назначение,
`sipr_maket_first_approve_2`) за период по дате утверждения в выбранной
области, и плательщики, за которых до месяца назначения платили социальные
отчисления (`em5_sird_reckon_donation` + `pmpd_pay_doc`, месяцы платежа за
13 или 25 месяцев до месяца утверждения): по получателю и плательщику - число
месяцев с платежами. Колонка «Период, учтенный при определении СМД» -
границы окна, как в оригинале.

Рабочие таблицы. Оригинал строил две таблицы (`sipp_payout_period`,
`sipp_payout_payer`; у СВур `sbpp_...`) заданием планировщика
(`rptb_schedule_status`, `DBMS_SCHEDULER`), пока отчёт показывал «Идет
подготовка данных». Отчёты приложения читают БД только на чтение, поэтому та
же выборка стоит в запросе, подготовки и расписания нет.

Источник первых назначений. Оригинал читает `sipr_maket_first_approve`, но эта
таблица в боевой БД не пополняется с 28.02.2023 (проверено 15.10.2026: последняя
`date_approve` - 2023-02-28), актуальная - `sipr_maket_first_approve_2` (её
читают 3027, 6001, 3162 и др.). За периоды после февраля 2023 оригинал
возвращает пустой отчёт; здесь взята `_2`.

Отличия. `person.rn` -> `person.iin`; название района - `branch.name` по коду
отделения получателя (в оригинале `rfbn_branch.name`); `date_approve between`
-> `>= :d_from and < :d_to`; `em.pay_month between ... -13 and ... -1` ->
`>= ... -13 and < trunc(date_approve, 'month')` (pay_month - первое число
месяца). В подписи окна оригинал печатал даты в формате сессии; здесь
`dd.mm.yyyy`. В оригинале конец подписи окна - последний день месяца за два
месяца до утверждения (`add_months(trunc(d,'month')-1,-1)`), а платежи берутся
по месяц до утверждения включительно: подпись на месяц короче реального
окна. Сохранено как есть.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

COLUMNS = [
    Col('Наименование района', 'region', 'text', 36),
    Col('ФИО', 'fio', 'text', 36),
    Col('ИИН', 'iin', 'center', 16),
    Col('ИИН/БИН плательщика', 'rnn', 'center', 18),
    Col('Наименование плательщика', 'org_name', 'text', 44),
    Col('Количество выплат', 'cnt', 'int', 12),
    Col('Период учтенный при определении СМД', 'period', 'center', 26),
]

_STMT = """
select b.name region, s.fio, s.iin, pd.p_rnn rnn, pd.p_name org_name,
       count(distinct em.pay_month) cnt,
       to_char(add_months(trunc(s.date_approve, 'month'), -{months}), 'dd.mm.yyyy')
         || '-' ||
       to_char(add_months(trunc(s.date_approve, 'month') - 1, -1), 'dd.mm.yyyy') period
  from (select a.date_approve, a.rfbn_id, a.sipr_id, a.sicp_id,
               p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
               p.iin
          from sipr_maket_first_approve_2 a, person p
         where a.date_approve >= :d_from and a.date_approve < :d_to
           and substr(a.rfpm_id, 1, 4) = '{rfpm}'
           and substr(a.rfbn_id, 1, 2) = :rfbn_id
           and p.sicid = a.sicp_id{sex}) s,
       em5_sird_reckon_donation em, pmpd_pay_doc pd, branch b
 where em.pay_month >= add_months(trunc(s.date_approve, 'month'), -{months})
   and em.pay_month <  trunc(s.date_approve, 'month')
   and s.sicp_id = em.sicp_id
   and s.sipr_id = em.sipr_id
   and em.mhmh_id = pd.mhmh_id{paydate}
   and s.rfbn_id = b.rfbn_id
 group by b.name, s.fio, s.iin, pd.p_rnn, pd.p_name,
          trunc(s.date_approve, 'month')
 order by b.name, s.fio, pd.p_name
"""


def make_report(code, name, rfpm, months, men_only=False, pay_date_limit=False):
    stmt = _STMT.format(
        rfpm=rfpm, months=months,
        sex='\n           and p.sex = 1' if men_only else '',
        paydate=("\n   and pd.pay_date >= add_months(trunc(s.date_approve, 'month'), -%d)" % months)
        if pay_date_limit else '')
    return build_report(code=code, name=name, columns=COLUMNS, stmt=stmt,
                        profile=LOADER_PROFILE, date_range=True)
