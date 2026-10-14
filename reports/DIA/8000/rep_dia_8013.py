# -*- coding: utf-8 -*-
"""8013. Плательщики СО и работники, за которых СО рассчитаны от дохода менее
1 МЗП.

Перенос WEB_REP_R_8013 (AIS 8013, группа 8000 «Паспорт СОСС», «составлен без
технического задания»). Образец - `docs/8000/Rep__8013.xlsx`.

Источник - снимок `min_so_history`: на каждую контрольную дату (`ctrl_date`)
в нём платёжные месяцы, по которым участнику перечислено СО от суммы дохода
менее 1 МЗП. Контрольная дата - месяц, выбранный в форме (в оригинале зашит
август 2025). Берутся платёжные месяцы не раньше чем за 13 месяцев до
контрольного. Строка - платёжный месяц: число различных плательщиков
(`p_rnn`) и различных работников (ИИН по `person`); последняя строка -
различные по всем месяцам сразу, не сумма. Номер строки у итога пустой.

Отличие от образца: подпись месяца - «за июль 2024» (оригинал: «за июль     2024»
- название месяца дополнено пробелами до самого длинного, Oracle `month`);
в заголовке образца стояла устаревшая фраза «по состоянию на 01 марта 2024
года», здесь дата - первое число выбранного месяца.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = '8013'
report_name = ('Сведения по плательщикам СО с указанием количества\n'
               'участников (работников), за которых плательщиками\n'
               'перечислены СО, рассчитанные от суммы дохода за\n'
               'календарный месяц менее 1 МЗП,\n'
               'по состоянию на {date_from} года (8013)')

COLUMNS = [
    Col('период', 'period', 'text', 22),
    Col('кол-во предприятий (уникальных)', 'cnt_p', 'int', 20),
    Col('кол-во сотрудников (уникальных)', 'cnt_m', 'int', 20),
]

STMT = """
with s as (
    select /*+parallel(4)*/
           m.pay_month, m.p_rnn, p.iin
      from min_so_history m, person p
     where m.ctrl_date >= :d_from
       and m.ctrl_date <  :d_to
       and m.pay_month >= add_months(:d_from, -13)
       and m.sicid = p.sicid
)
select period, cnt_p, cnt_m, bold
  from (
    select s.pay_month ord,
           'за ' || to_char(s.pay_month, 'fmmonth yyyy', 'NLS_DATE_LANGUAGE=RUSSIAN') period,
           count(distinct s.p_rnn) cnt_p, count(distinct s.iin) cnt_m, 0 bold
      from s
     group by s.pay_month
    union all
    select date '9999-01-01', 'Итого уникальных',
           count(distinct s.p_rnn), count(distinct s.iin), 1
      from s
  )
 order by ord
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, bold_key='bold',
)
