# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 602 (процедура REP_R_602).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Справка о доходах за период: выплаты из ГФСС по получателю помесячно.

Параметр. В AIS получатель выбирался в окне поиска по картотеке, номер
(`sicid`, третий параметр) уходил в процедуру; период - два первых параметра.
Здесь получатель задаётся ИИНом (`person.iin`; в оригинале `rn`, такой колонки сейчас нет - оригинал давно не выполняется, отчёт мог не использоваться) - `sicid` пользователю
неизвестен. Нет человека с таким ИИН - ошибка «Пенсионер не выбран», как
при пустом выборе в оригинале.

Источник - `pnpd_document`: документы с видом риска 07 (`rfpm_id like '07%'`),
типы документа 1, 6, 4, 9, 10, состояния 1 и 2, месяц выплаты `pncp_date`
в периоде. Сумма - `pay_sum + nvl(sum_debt, 0)` (в оригинале условный `case`
по тому же `like '07%'` - тот же результат). Подпись месяца -
`initcap(yyyy || '-' || month)` по-русски («2026-Сентябрь»). Итог по колонке
«ВЫПЛАТЫ ИЗ ГФСС» (`SetColSumTotal`).

Проверка периода как в оригинале: даты заданы, начало не позже конца. Название:
«СПРАВКА О ДОХОДАХ в период: с <дата>г. по <дата>г. выдана: <ФИО> СИК:
<СИК>», «с» перед датой кириллическая (в оригинале латинская «c»); наименование филиала пользователя
(`setup.branchname`) у веб-отчётов недоступно и не выводится.

Колонки «МЕСЯЦ» и «ВЫПЛАТЫ ИЗ ГФСС» - дословно. Формат даты в названии -
`dd-mm-yyyy`, как у оригинала.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, parse_date

report_code = '602'
report_name = ('СПРАВКА О ДОХОДАХ\n'
               'в период: с {date_from_dash}г. по {date_to_dash}г.\n'
               'выдана: {fio}\n'
               'СИК: {sic}')

COLUMNS = [
    Col('МЕСЯЦ', 'month', 'text', 24),
    Col('ВЫПЛАТЫ ИЗ ГФСС', 'sum_soc', 'money', 22),
]


def _check(params):
    first, second = params.get('date_first'), params.get('date_second')
    if not first and not second:
        raise ValueError('Дата не введена')
    if parse_date(first) > parse_date(second):
        raise ValueError('Период указан не верно')


# ФИО (initcap, как InitCap(pFIO) в оригинале) и СИК получателя.
TITLE_SQL = """
select initcap(lastname || ' ' || firstname || ' ' || middlename) fio, sic
  from person
 where iin = :iin
"""

# :d_from / :d_to - период из формы по pncp_date, :d_to исключительная.
STMT = """
select initcap(to_char(pncp_date, 'yyyy') || '-'
               || trim(to_char(pncp_date, 'month', 'nls_date_language=russian'))) month,
       sum(case when rfpm_id like '07%'
                then pay_sum + nvl(sum_debt, 0) else 0 end) sum_soc
  from pnpd_document d
 where pncd_id = (select p.sicid from person p where p.iin = :iin)
   and ridt_id in (1, 6, 4, 9, 10)
   and status in (1, 2)
   and rfpm_id like '07%'
   and pncp_date >= :d_from
   and pncp_date <  :d_to
 group by pncp_date
 order by pncp_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, totals=True,
    check_params=_check,
    title_sql=TITLE_SQL, title_not_found='Пенсионер не выбран',
)
