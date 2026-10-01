# -*- coding: utf-8 -*-
"""Приложение 53. Количество плательщиков по БИН и ИИН в разрезе регионов.

Перенос REP_STAT_EXTEND.app_53_spool + Rep_app_53 (pck_utf8.sql, 10467-10925).
Протокол: app_53_spool запускается ежемесячно, 104 запуска, последний 09.2026.

Что не переносится и почему:
  - PF_plUchSoss53r_2 (строки 10530-10560) нигде не вызывается - мёртвая
    копия; живая только PF_plUchSoss53r (вызов в строке 10587);
  - промежуточная таблица FF_SECTION_SO (truncate + insert + commit) -
    становится CTE `so`; период в ней больше не хранится (dtr_beg/dtr_end),
    потому что срез теперь живёт только внутри запроса;
  - колонка rfbk_mfo_pbank: в отчёте не используется;
  - num_month: у одного запуска период один, колонка была константой;
  - ветка шапки 'f' ("Форма № 25/1"): отдельно не вызывалась.

Отличия SQL от оригинала, не меняющие цифры:
  - в срезе оставлен только knp = '012'. Оригинал брал 012 и 017, но
    first_value упорядочен decode(knp,'012',0,1), то есть для sicid, у которого
    есть 012, last_rnn/last_date берутся из 012, а sicid без 012 отсекаются
    условием knp = '012' при чтении среза. Строки 017 ни на что не влияют
    (вывод подтверждён разбором данных 01.10.2026, сверка с PL/SQL ещё впереди);
  - границы периода полуоткрытые (>= :d_from and < :d_to) вместо
    `between i_DatB and i_DatE`: between - потенциальная беда (блокирует индекс
    и теряет конец периода, если в дате есть время), от неё избавляемся во всех
    отчётах. Если в pay_date_gfss, pay_date есть время суток, оригинал терял
    последний день периода после полуночи, а здесь он учитывается.

Соединение с pmpd_pay_doc оставлено как в оригинале: его колонка не нужна, но
оно фильтр (платёжный документ в окне периода). mhmh_id в pmpd_pay_doc - уникальный
ключ (подтверждено 01.10.2026), поэтому join строки не размножает и эквивалентен
exists; суммы не задваиваются.

Строки - все регионы справочника плюс "Регион не определен" последней, как
в Rep_app_53 (union all 'ZZ', order by rfrg_id). Если для региона вообще нет
данных, ячейки пустые, а три итоговые колонки 0 (в оригинале Rep.td для
отсутствующей записи не вызывался, итоги печатались всегда). Нулевое количество
внутри региона с данными печатается нулём, сумма без плательщиков - пусто
(spool вставлял только не-NULL значения).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.53'
report_name = 'Количество плательщиков по БИН и ИИН в разрезе регионов{period}'

# PH_per (строки 10911-10921), как у app_52/app_55.
_period_label = make_period_label({
    1: ', за {Month} {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за  9 месяцев {year} года ',
    5: ', за {year} год ',
})

# cColHeadText (строка 10750) дословно, включая "*" и отсутствие пробела
# перед скобкой.
_CNT = 'количество участников*, за которых перечислены СО(чел)'
_SUM = 'сумма СО(тенге)'

COLUMNS = [
    Col('Регион', 'reg', 'text', 36),
    Group('Участники СОСС', [
        Group('по БИН', [
            Col(_CNT, 'cnt_u', 'int', 18),
            Col(_SUM, 'sm_u', 'money', 18),
        ]),
        Group('по БИН и по ИИН', [
            Col(_CNT, 'cnt_uf', 'int', 18),
            Col(_SUM, 'sm_uf', 'money', 18),
        ]),
        Group('по ИИН', [
            Col(_CNT, 'cnt_f', 'int', 18),
            Col(_SUM, 'sm_f', 'money', 18),
        ]),
        Group('Итого', [
            Col(_CNT, 'cnt_all', 'int', 18),
            Col(_SUM, 'sm_all', 'money', 18),
        ]),
    ]),
    Group('Плательщики СО', [
        Col('по БИН', 'cnt_u_rnn', 'int', 14),
        Col('по ИИН', 'cnt_f_rnn', 'int', 14),
        Col('Итого', 'cnt_rnn', 'int', 14),
    ]),
]

FOOTNOTE = ('* - участники системы обязательного социального страхования - '
            'лица, за которых в отчетном периоде была произведена уплата '
            'социальных отчислений, учтенные хотя бы 1 раз')

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
#
# so  - бывшая FF_SECTION_SO: срез СО за период (см. docstring про knp).
# reg - справочник rfrr_id_region с областями 17..20, вынесенными из
#       rfbn_id (четыре списка из оригинала, строки 10589-10639, повторяются в запросе трижды). Для
#       платёжного идентификатора без записи в справочнике регион '00'.
# g   - по одному ряду на участника (sicid): сумма СО, число БИН- и
#       ИИН-перечислений. Тип перечисления определяет 5-й символ РНН.
# w   - участники по региону последнего РНН. Ярлык 'R'/'I' в соединении с
#       справочником зависит от даты: до 01.01.2013 запись старого типа.
# d,v - плательщики: уникальные РНН по региону самого РНН.
# Регионы w и v соединяются внутренним соединением, как в оригинале.
STMT = """
with so as (
    select m.sicid,
           m.p_rnn,
           m.pay_date,
           m.sum_pay sm,
           first_value(m.p_rnn) over (partition by m.sicid
                 order by m.pay_date desc
                 rows between unbounded preceding and unbounded following) last_rnn,
           first_value(m.pay_date) over (partition by m.sicid
                 order by m.pay_date desc
                 rows between unbounded preceding and unbounded following) last_date
      from si_member_2 m, pmpd_pay_doc pdi
     where m.knp = '012'
       and m.pay_date_gfss >= :d_from
       and m.pay_date_gfss <  :d_to
       and m.mhmh_id = pdi.mhmh_id
       and m.pay_date  >= add_months(:d_from, -1)
       and m.pay_date  <  :d_to
       and pdi.pay_date >= add_months(:d_from, -1)
       and pdi.pay_date <  :d_to
),
reg as (
    select r.id,
           r.typ,
           nvl(case when r.rfbn_id in ('1403', '1416', '1417', '1418') then '17'
                    when r.rfbn_id in ('0503', '0504', '0505', '0506', '0507',
                                       '0508', '0510', '0518') then '18'
                    when r.rfbn_id in ('0303', '0304', '0305', '0306', '0311',
                                       '0313', '0314', '0315', '0317', '0318') then '19'
                    when r.rfbn_id in ('0802', '0804', '0812', '0816', '0818') then '20'
                    else r.rfrg_id
               end, '00') reg_id
      from rfrr_id_region r
),
g as (
    select distinct
           t.sicid,
           sum(t.sm) over (partition by t.sicid) sum_sic,
           t.last_rnn,
           t.last_date,
           count(case when substr(t.p_rnn, 5, 1) not in ('0', '1', '2', '3')
                      then 'U' end) over (partition by t.sicid) cnt_u,
           count(case when substr(t.p_rnn, 5, 1) in ('0', '1', '2', '3')
                      then 'F' end) over (partition by t.sicid) cnt_f
      from so t
),
w as (
    select nvl(r.reg_id, '00') reg_id,
           count(distinct case when g.cnt_u > 0 and g.cnt_f = 0 then g.sicid end) cnt_sic_u,
           sum(case when g.cnt_u > 0 and g.cnt_f = 0 then g.sum_sic end)          sm_u12,
           count(distinct case when g.cnt_u > 0 and g.cnt_f > 0 then g.sicid end) cnt_sic_uf,
           sum(case when g.cnt_u > 0 and g.cnt_f > 0 then g.sum_sic end)          sm_uf12,
           count(distinct case when g.cnt_u = 0 and g.cnt_f > 0 then g.sicid end) cnt_sic_f,
           sum(case when g.cnt_u = 0 and g.cnt_f > 0 then g.sum_sic end)          sm_f12
      from g, reg r
     where (case when g.last_date < to_date('01.01.2013', 'dd.mm.yyyy')
                 then 'R' else 'I' end) = r.typ(+)
       and g.last_rnn = r.id(+)
     group by nvl(r.reg_id, '00')
),
d as (
    select distinct
           t.p_rnn,
           max(t.pay_date) over (partition by t.p_rnn) py_dt,
           case when substr(t.p_rnn, 5, 1) not in ('0', '1', '2', '3') then 'U'
                when substr(t.p_rnn, 5, 1) in ('0', '1', '2', '3') then 'F'
           end rnn_fl
      from so t
),
v as (
    select nvl(r.reg_id, '00') reg_id,
           count(distinct case when d.rnn_fl = 'U' then d.p_rnn end) cnt_u_rnn,
           count(distinct case when d.rnn_fl = 'F' then d.p_rnn end) cnt_f_rnn
      from d, reg r
     where (case when d.py_dt < to_date('01.01.2013', 'dd.mm.yyyy')
                 then 'R' else 'I' end) = r.typ(+)
       and d.p_rnn = r.id(+)
     group by nvl(r.reg_id, '00')
),
dt as (
    select w.reg_id,
           w.cnt_sic_u, w.sm_u12, w.cnt_sic_uf, w.sm_uf12, w.cnt_sic_f, w.sm_f12,
           v.cnt_u_rnn, v.cnt_f_rnn
      from w, v
     where w.reg_id = v.reg_id
),
rg as (
    select tr.rfrg_id reg_id, tr.name reg, 1 ord from rfrg_region tr
    union all
    select '00', 'Регион не определен', 2 from dual
)
select rg.reg                                                      reg,
       dt.cnt_sic_u                                                cnt_u,
       dt.sm_u12                                                   sm_u,
       dt.cnt_sic_uf                                               cnt_uf,
       dt.sm_uf12                                                  sm_uf,
       dt.cnt_sic_f                                                cnt_f,
       dt.sm_f12                                                   sm_f,
       nvl(dt.cnt_sic_u, 0) + nvl(dt.cnt_sic_uf, 0) + nvl(dt.cnt_sic_f, 0) cnt_all,
       nvl(dt.sm_u12, 0)    + nvl(dt.sm_uf12, 0)    + nvl(dt.sm_f12, 0)    sm_all,
       dt.cnt_u_rnn                                                cnt_u_rnn,
       dt.cnt_f_rnn                                                cnt_f_rnn,
       nvl(dt.cnt_u_rnn, 0) + nvl(dt.cnt_f_rnn, 0)                 cnt_rnn
  from rg, dt
 where dt.reg_id(+) = rg.reg_id
 order by rg.ord, rg.reg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
