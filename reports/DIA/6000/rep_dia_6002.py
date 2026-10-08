# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «ДИА - квартальные отчеты», отчёт 6002
(пакет AQ_EMPLOYER_1MZP, процедура report_1).
============================================================

1 МЗП квартальный: работодатели, уплатившие за работников социальные
отчисления с дохода менее 1 МЗП. Строка - работодатель (БИН), в колонках
число работников (`count(distinct sicid)`) по каждому месяцу квартала.

Источник - `si_member_2`, КНП 012, без БИН 160440007161; МЗП с февраля 2013
(`pay_month >= 01.02.2013`). Оригинал готовил данные заданием в таблицу
`aq_employer_1_mzp` (`prepare`), здесь то же самое делает запрос:
  - aq_src - платежи квартала по дате поступления `pay_date`, месяц платежа
    раньше третьего месяца квартала (`pay_month < trunc(v_last_date,'MONTH')`,
    в оригинале с пометкой «Везде так, почему ?» - перенесено как есть);
    по месяцу поступления, участнику, БИН и периоду `sum(cnt_mzp) < 1`;
  - aq - то же, но `floor(sum(cnt_mzp))` по ВСЕМ платежам КНП 012 за этот
    период участника у этого БИН, без ограничения дат (в оригинале `update ...
    set mzp = floor(rec.c)` и затем фильтр `mzp < 1`).
В отчёт попадают только работодатели, у которых такие работники есть во всех
трёх месяцах квартала (inner join m7, m8, m9 - как в оригинале).

Наименование работодателя - `rfon_organization.nm_ru` по БИН, место - по его
КАТО (`cato_branch.code`): район - сама запись КАТО, область - запись `XX00` с
теми же первыми двумя знаками. Условие на область в оригинале без `(+)`,
поэтому работодатели, которых нет в `rfon_organization` или чей КАТО не найден,
в отчёт не попадают - сохранено.

Отличия от оригинала:
  - квартал выбирается в форме (год + квартал); оригинал брал его от sysdate
    (`floor(month/3)`: в январе-феврале - «0 квартал» = IV квартал прошлого года,
    в марте - ещё не закончившийся I квартал); в названии добавлен год;
  - в действующем `report_1` колонки места перепутаны: под «Код области /
    Область» шла запись КАТО организации (район), под «Код района / Наименование
    района» - область `XX00`. Здесь как в `report_1_old`: область - `XX00`,
    район - КАТО организации. Порядок строк тот же (область, район);
  - `between` по `pay_date` заменён на `>= :d_from and < :d_to`;
  - «Наменование предприятия» -> «Наименование предприятия»;
  - подписи «Руководитель / Исполнитель / дата и время создания» под таблицей
    не переносятся: дата формирования стоит в шапке листа.
Итоги - по трём колонкам месяцев (`SetColSumTotal(8..10)`).
Отчёт-предшественник в Python - minCO/rep_dia_co_03 (не трогали).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '6002'
report_name = '1 МЗП за {period}'

COLUMNS = [
    Col('Код области', 'obc', 'center', 10),
    Col('Область', 'obn', 'text', 36),
    Col('Код района', 'rc', 'center', 10),
    Col('Наименование района', 'rn', 'text', 36),
    Col('БИН', 'p_rnn', 'center', 16),
    Col('Наименование предприятия', 'nm', 'text', 60),
    Col('1 месяц', 'c1', 'int', 10),
    Col('2 месяц', 'c2', 'int', 10),
    Col('3 месяц', 'c3', 'int', 10),
]

# :d_from / :d_to - границы выбранного квартала, :d_to исключительная.
STMT = """
with aq_src as (
    select /*+ parallel(4) */
           trunc(pay_date, 'MM') pd, sicid, p_rnn, pay_month
      from si_member_2
     where pay_date >= :d_from
       and pay_date <  :d_to
       and pay_month < add_months(:d_from, 2)
       and pay_month >= date '2013-02-01'
       and knp in ('012')
       and p_rnn != '160440007161'
       and type_payer not in ('SZ', 'P', 'O')
     group by trunc(pay_date, 'MM'), sicid, p_rnn, pay_month
    having sum(cnt_mzp) < 1
),
aq as (
    select /*+ parallel(4) */
           m.pd, m.sicid, m.p_rnn
      from aq_src m, si_member_2 s
     where s.p_rnn = m.p_rnn
       and s.sicid = m.sicid
       and s.pay_month = m.pay_month
       and s.knp in ('012')
       and s.type_payer not in ('SZ', 'P', 'O')
     group by m.pd, m.sicid, m.p_rnn, m.pay_month
    having floor(sum(s.cnt_mzp)) < 1
)
select m7.obc, m7.obn, m7.rc, m7.rn, m7.p_rnn, m7.nm,
       m7.c c1, m8.c c2, m9.c c3
  from (select m.p_rnn,
               cb2.rfbn_id obc,
               cb2.name_ru obn,
               cb1.rfbn_id rc,
               cb1.name_ru rn,
               o.nm_ru nm,
               count(distinct m.sicid) c
          from aq m, rfon_organization o, cato_branch cb1, cato_branch cb2
         where m.p_rnn = o.bin(+)
           and o.cato = cb1.code(+)
           and substr(cb1.rfbn_id, 1, 2) = substr(cb2.rfbn_id(+), 1, 2)
           and substr(cb2.rfbn_id, 3, 2) = '00'
           and m.pd = :d_from
         group by m.p_rnn, o.nm_ru, cb1.rfbn_id, cb1.name_ru, cb2.rfbn_id, cb2.name_ru) m7,
       (select p_rnn, count(distinct sicid) c
          from aq
         where pd = add_months(:d_from, 1)
         group by p_rnn) m8,
       (select p_rnn, count(distinct sicid) c
          from aq
         where pd = add_months(:d_from, 2)
         group by p_rnn) m9
 where m7.p_rnn = m8.p_rnn
   and m8.p_rnn = m9.p_rnn
 order by m7.obc, m7.rc
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True,
    period_label=make_period_label({2: '{n} квартал {year} года'}),
)
