# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «ДИА - квартальные отчеты», отчёт 6001
(пакет AQ_EMPLOYER_BIR, процедура report_1).
============================================================

Сведения о количестве работодателей у лиц, которым назначена социальная
выплата по беременности и родам (СВбр, 0704): назначения разложены по размеру
выплаты (строки - группы) и по числу работодателей получателя (колонки -
1, 2, 3, 4, 5, 6 и более), в каждой клетке число назначений и их сумма.
Период - с начала года по конец выбранного квартала (в пакете «Отчет
квартальный с накоплением с начала года»).

Оригинал готовил данные заданием в три таблицы (`prepare_bir`), здесь то же
делает запрос:
  - mk - макеты первого назначения `sipr_maket_first_approve_2`, `rfpm_id like
    '0704%'`, по дате утверждения `date_approve`;
  - emp - число работодателей получателя (в оригинале `aq_employer_bir_all` ->
    `aq_employer_bir_count`): плательщики `pmpd_pay_doc.p_rnn` взносов КНП 012,
    учтённых в расчёте выплаты (`em5_sird_reckon_donation`, `nvl(is_calc,'x') !=
    'N'`; в оригинале через вьюшку `v_reckon_donation` - это выборка колонок из
    этой таблицы без условий с подсказкой `index(s XN1_SIRD_SIPR_ID)`, вьюшка
    убрана, подсказка перенесена),
    по макетам с `sum_all > 0`. Считаются только плательщики, найденные в
    справочнике организаций: `rfon_organization.bin = p_rnn` и её КАТО в
    `cato_branch` (`rfon_organization.cato = cato_branch.code`) - та же связка,
    что в остальных отчётах. В оригинале здесь был `nk_minfin_iin` (`update ...
    set iin` по совпадению `iin = p_rnn`, затем `count(unique iin)`), справочник
    мёртвый (Шамиль, 07.10.2026). Плательщиков КНП 012 за 06.2026 связка
    находит 98,8 %. Разбивка по году платежа (`god`) на счёт не влияет и не
    переносится;
  - target (в оригинале `aq_employer_bir_target`) - группа размера
    `width_bucket(sum_all, 0, 2500000, 25)` (шаг 100 000 тенге: 1 - меньше
    100 000, ..., 25 - от 2 400 000), всё от 2 500 000 - группа 26; число
    работодателей `greatest(1, least(6, nvl(cnt_iin, 0)))`: получатель без
    найденных работодателей попадает в «1 работодатель», как в оригинале.
Количество - число макетов (`count(1)`), сумма - `sum(sum_all)`. Пустая
клетка - нет назначений (в оригинале скалярный подзапрос давал NULL).

Отличия от оригинала:
  - период: год + квартал из формы. Оригинал брал квартал от sysdate (формула
    закомментирована, сейчас в `set_date` зашито 01.01.2026 - 30.06.2026);
  - `trunc(date_approve) between` заменён на `>= :y_from and < :d_to`;
  - «Кол-во, выплат» -> «Кол-во выплат», двойной пробел в «6 и более
    работодателей» убран, «СВбр» в названии оставлено;
  - итог по колонке «Группа» (номера групп) не печатается: в оригинале
    `SetColSumTotal(2)` складывал номера групп;
  - подписи «Руководитель / Исполнитель / дата и время создания» под таблицей
    не переносятся: дата формирования стоит в шапке листа.

`em5_sird_reckon_donation` (схема SSWH) в тестовой reports_test недоступна: на
данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.period import period_bounds, year_start, last_day
from util.xlsx_report import build_report, Col, Group

report_code = '6001'
report_name = ('Сведения о количестве работодателей лицам, которым назначено '
               'СВбр за период {period} года')

_CNT = 'Кол-во выплат'
_SUM = 'Сумма, тенге'


def _pair(title, n):
    return Group(title, [Col(_CNT, f'cnt{n}', 'int', 12),
                         Col(_SUM, f'sum{n}', 'money', 18)])


COLUMNS = [
    Col('Группа', 'sum_group', 'center', 10),
    _pair('1 работодатель', 1),
    _pair('2 работодателя', 2),
    _pair('3 работодателя', 3),
    _pair('4 работодателя', 4),
    _pair('5 работодателей', 5),
    _pair('6 и более работодателей', 6),
]


def _label(rep_year, date_type, date_start=None):
    """"01.01.2026 - 30.06.2026": с начала года по конец квартала,
    как `v_first_date||' - '||v_last_date` в оригинале."""
    _, d_to = period_bounds(rep_year, date_type, date_start)
    return f'{year_start(rep_year):%d.%m.%Y} - {last_day(d_to):%d.%m.%Y}'


def _cell(n):
    return (f"sum(case when coun = {n} then 1 end) cnt{n},\n"
            f"       sum(case when coun = {n} then sum_all end) sum{n}")


# :y_from - 1 января года, :d_to - начало следующего квартала (исключительная).
STMT = f"""
with mk as (
    select /*+ parallel(4) */
           p.sipr_id, p.sum_all
      from sipr_maket_first_approve_2 p
     where p.rfpm_id like '0704%'
       and p.date_approve >= :y_from
       and p.date_approve <  :d_to
),
emp as (
    select /*+ parallel(8) index(d XN1_SIRD_SIPR_ID) */
           d.sipr_id, count(unique pd.p_rnn) cnt_iin
      from mk p, em5_sird_reckon_donation d, pmpd_pay_doc pd
     where p.sum_all > 0
       and p.sipr_id = d.sipr_id
       and nvl(d.is_calc, 'x') != 'N'
       and d.mhmh_id = pd.mhmh_id
       and pd.cipher_id_knp = '012'
       and exists (select 1
                     from rfon_organization o, cato_branch cb
                    where o.bin = pd.p_rnn
                      and o.cato = cb.code)
     group by d.sipr_id
),
target as (
    select /*+ parallel(4) */
           case when m.sum_all > 2500000 then 26
                else width_bucket(m.sum_all, 0, 2500000, 25) end sum_group,
           greatest(1, least(6, nvl(e.cnt_iin, 0))) coun,
           m.sum_all
      from mk m, emp e
     where m.sipr_id = e.sipr_id(+)
       and m.sum_all is not null
)
select /*+ parallel(4) */
       sum_group,
       {_cell(1)},
       {_cell(2)},
       {_cell(3)},
       {_cell(4)},
       {_cell(5)},
       {_cell(6)}
  from target
 group by sum_group
 order by sum_group
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, period_label=_label,
)
