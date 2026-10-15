# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 616 (пакет AO_ONLINE_NEW, процедура
less_1mzp_all, «Менее 1 МЗП»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Организации, платившие за прошлый месяц социальные отчисления менее 1 МЗП за
работников: область, район, БИН, наименование, число работников организации
и число работников с отчислениями менее 1 МЗП.

Рабочая таблица. Оригинал читал `tbl_less_mzp` (заполняется пакетом
`PKG_LESS_MZP.Fill`, `delete` + циклы `update`). Отчёты приложения читают БД
только на чтение и таблицы-посредника быть не должно, поэтому расчёт сделан
запросом (тот же, что в отчёте 610, но по всем организациям):
 - `t` - платежи КНП 012 за прошлый календарный месяц (`pay_date`) за более
   ранние месяцы, не раньше февраля 2013 (1 МЗП), без ЕСП (`type_payer = 'E'`)
   и единого платежа (`type_payment = 'O'`); группа работник + БИН + месяц,
   `sum(trunc(cnt_mzp, 5)) < 1`. В тексте AIS буквы кириллические, в данных
   латинские, поэтому условие оригинала ничего не отсекало; здесь латинские,
   как задумано автором пакета;
 - `a` - сколько всего внесено за этот месяц (все платежи КНП 012 с
   февраля 2013); `low` - те, у кого внесено / `min_so(месяц)` меньше 1;
 - `cnt` - число работников организации: уникальные `sicid` всех платежей
   организации за прошлый месяц (`cnt_all` пакета).

Область и район. Оригинал определял их через `rfrr_id_region` и
`nk_minfin_iin` (оба мертвы); здесь, как во всех живых отчётах, - связкой
`rfon_organization.bin = p_rnn` -> `rfon_organization.cato = cato_branch.code`
-> `cato_branch.rfbn_id` (район), область - его первые две цифры + `00`;
названия из `branch.name` (область) и `branch.short_name` (район), правило
Шамиля 14.10.2026. Организация без записи в справочнике выводится с кодами
«нет» и пустым наименованием, как в оригинале.

Прошлый месяц считается от текущей даты, как `add_months(trunc(sysdate,
'MM'), -1)` оригинала. Сортировка - по коду района и БИН. Подписи под
таблицей оригинала не переносятся.

`si_member_2`, `rfon_organization`, `cato_branch`, `branch` reports_test
видит; функция `min_so` в SSWH недоступна: запрос без неё проверен на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '616'
report_name = 'Менее 1 МЗП'

COLUMNS = [
    Col('Код области', 'rfbn_reg', 'center', 12),
    Col('Область', 'name_reg', 'text', 28),
    Col('Код района', 'rfbn_area', 'center', 12),
    Col('Район', 'name_area', 'text', 28),
    Col('БИН/ИИН предприятия', 'p_rnn', 'center', 18),
    Col('Наименование предприятия', 'name_org', 'text', 44),
    Col('Количество сотрудников', 'cnt_all', 'int', 14, total=False),
    Col('Количество сотр МЗП < 1', 'cnt_low', 'int', 14, total=False),
]

STMT = """
with t as (
    select m.sicid, m.p_rnn, m.pay_month
      from si_member_2 m
     where m.knp = '012'
       and m.pay_date >= add_months(trunc(sysdate, 'MM'), -1)
       and m.pay_date <  trunc(sysdate, 'MM')
       and m.pay_month <  add_months(trunc(sysdate, 'MM'), -1)
       and m.pay_month >= date '2013-02-01'
       and coalesce(m.type_payer, 'X') != 'E'
       and coalesce(m.type_payment, 'X') != 'O'
     group by m.sicid, m.p_rnn, m.pay_month
    having sum(trunc(m.cnt_mzp, 5)) < 1
),
low as (
    select t.sicid, t.p_rnn
      from t, si_member_2 a
     where a.sicid = t.sicid and a.p_rnn = t.p_rnn
       and a.pay_month = t.pay_month
       and a.knp = '012'
       and a.pay_date >= date '2013-02-01'
     group by t.sicid, t.p_rnn, t.pay_month
    having sum(a.sum_pay) / min_so(t.pay_month) < 1
),
org as (
    select p_rnn, count(distinct sicid) cnt_low from low group by p_rnn
),
cnt as (
    select m.p_rnn, count(distinct m.sicid) cnt_all
      from si_member_2 m
     where m.p_rnn in (select p_rnn from org)
       and m.pay_date >= add_months(trunc(sysdate, 'MM'), -1)
       and m.pay_date <  trunc(sysdate, 'MM')
     group by m.p_rnn
)
select nvl(cb.rfbn_id, 'нет') rfbn_area,
       nvl2(cb.rfbn_id, substr(cb.rfbn_id, 1, 2) || '00', 'нет') rfbn_reg,
       br.name name_reg,
       bd.short_name name_area,
       org.p_rnn,
       o.nm_ru name_org,
       cnt.cnt_all,
       org.cnt_low
  from org
  left join cnt on cnt.p_rnn = org.p_rnn
  left join rfon_organization o on o.bin = org.p_rnn
  left join cato_branch cb on cb.code = o.cato
  left join branch bd on bd.rfbn_id = cb.rfbn_id
  left join branch br on br.rfbn_id = substr(cb.rfbn_id, 1, 2) || '00'
 order by cb.rfbn_id, org.p_rnn
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE,
)
