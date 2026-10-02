# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Формы статотчётности в Мин. труд. 2014», подгруппа «Получатели
СВ из ГФСС в разрезе регионов и стажа участия», отчёт 1426 «Новый»
(процедура REP_R_1426).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения по количеству получателей и суммам социальных выплат в разрезе
регионов и стажа участия: по виду выплаты и периоду назначения - по региону,
коэффициенту стажа участия (КСУ) и возрастной группе число получателей и сумма
выплаты.

Источник - `sipr_maket_first_approve` (макеты первого назначения), отбор по дате
утверждения `date_approve` в периоде и виду выплаты (`substr(rfpm_id, 1, 4)`;
в оригинале этот параметр назван `v_rfbn`, но это код выплаты, в названии он
печатается как «Код выплаты»). Регион получателя - филиал по самому свежему
макету (`first_value(substr(rfbn_id, 1, 2) || '00') over (partition by sicp_id
order by trunc(date_approve) desc)`), название - `rfbn_branch`. Возраст -
полных лет на дату формирования (`months_between(sysdate, birthdate) / 12`),
группы от «до 20» до «180 и выше» как в оригинале (границы дословно, включая
необычные 65-72, 72-84 и далее с шагом 12). Число получателей - `count(unique
sicp_id)`; итоги по колонкам «Кол-во» и «Сумма, тенге» (`SetColSumTotal(5)`,
`(6)`); итог по КСУ не печатается.

Сортировка в оригинале - по региону, возрастной группе (текстом: «20-24» после
«180 и выше», как и было) и КСУ; сохранена. Название дословно, без `<br>`
(перенос строки); даты - «с ... по ... года».

`sipr_maket_first_approve` лежит в схеме SSWH боевой БД, в тестовой reports_test
недоступна: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '1426'
report_name = ('Сведения по количеству получателей и суммам социальных выплат '
               'в разрезе регионов и стажа участия с {period} года\n'
               'Код выплаты: {rfpm_id}')

COLUMNS = [
    Col('Код региона', 'rfbn', 'center', 12),
    Col('Регион', 'name', 'text', 36),
    Col('КСУ', 'ksu', 'money', 12, total=False),
    Col('Возраст', 'staj_age', 'center', 14),
    Col('Кол-во', 'cnt', 'int', 12),
    Col('Сумма, тенге', 'sm', 'money', 20),
]

# :d_from / :d_to - период из формы по date_approve, :d_to исключительная;
# :rfpm_id - код выплаты (4 знака).
STMT = """
select rfbn,
       name,
       ksu,
       staj_age,
       count(unique sicp_id) cnt,
       sum(sm) sm
  from (select rfbn,
               br.name,
               ksu,
               case when age < 20 then 'до 20'
                    when age >= 20 and age < 25 then '20-24'
                    when age >= 25 and age < 30 then '25-29'
                    when age >= 30 and age < 35 then '30-34'
                    when age >= 35 and age < 40 then '35-39'
                    when age >= 40 and age < 45 then '40-44'
                    when age >= 45 and age < 50 then '45-49'
                    when age >= 50 and age < 55 then '50-54'
                    when age >= 55 and age < 60 then '55-59'
                    when age >= 60 and age < 65 then '60-64'
                    when age >= 65 and age < 72 then '65-72'
                    when age >= 72 and age < 84 then '72-84'
                    when age >= 84 and age < 96 then '84-96'
                    when age >= 96 and age < 108 then '96-108'
                    when age >= 108 and age < 120 then '108-120'
                    when age >= 120 and age < 132 then '120-132'
                    when age >= 132 and age < 144 then '132-144'
                    when age >= 144 and age < 156 then '144-156'
                    when age >= 156 and age < 168 then '156-168'
                    when age >= 168 and age < 180 then '168-180'
                    when age >= 180 then '180 и выше'
               end staj_age,
               sicp_id,
               sm
          from (select s.ksu,
                       floor(months_between(sysdate, s.birthdate) / 12) age,
                       s.sicp_id,
                       s.sum_all sm,
                       first_value(substr(s.rfbn_id, 1, 2) || '00')
                           over (partition by s.sicp_id
                                 order by trunc(s.date_approve) desc) rfbn
                  from sipr_maket_first_approve s
                 where s.date_approve >= :d_from
                   and s.date_approve <  :d_to
                   and substr(s.rfpm_id, 1, 4) = :rfpm_id) a,
               rfbn_branch br
         where a.rfbn = br.rfbn_id) q
 group by rfbn, name, ksu, staj_age
 order by rfbn, staj_age, ksu
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
    title_params=('rfpm_id',),
)
