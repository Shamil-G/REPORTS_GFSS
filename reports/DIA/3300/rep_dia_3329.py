# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДМЭН», отчёт 3329 (процедура REP_R_3329).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Получатель выплаты 42500 тенге (виды 0706 и 0709) по ИИН: все документы
выплат человека с этим ИИН.

Источник - `pnpd_document` + `pnpt_payment` (внешнее) + `rfds_doc_status` +
`person` (`p.iin = ИИН`). ФИО и ИИН берутся из документов выплаты, как в
оригинале (`d.lastname...`, `d.rnn`). Колонки те же, что в 3324.

Проверка ИИНа как в оригинале: ровно 12 знаков, иначе «Введен неправильный
ИИН!». Название дословно (`<br><br>` оригинала - пустая строка).
Динамический SQL оригинала с ИИН в тексте запроса заменён на бинд `:iin`.

ИИН: в оригинале `person.rn`, но в `person` сейчас колонка `iin` (подтверждено
Шамилем 02.10.2026), здесь `person.iin`. Оригинал с `rn` давно не выполняется
(запрос динамический, ошибка глоталась), поэтому отчёт мог не использоваться год-два:
стоит подтвердить, нужен ли он.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '3329'
report_name = 'Получатель выплаты 42500 тенге\n\nИИН: {iin}'

COLUMNS = [
    Col('Код района', 'rfbn_id', 'center', 10),
    Col('ФИО', 'fio', 'text', 40),
    Col('ИИН', 'rnn', 'center', 16),
    Col('КНП', 'knp', 'center', 8),
    Col('Сумма', 'all_sum', 'money', 16),
    Col('Дата назначения выплаты', 'appointdate', 'date', 14),
    Col('Дата утверждения', 'approvedate', 'date', 14),
    Col('Дата окончания выплаты', 'stopdate', 'date', 14),
    Col('Месяц выплаты', 'pncp_date', 'date', 14),
    Col('Статус', 'status', 'text', 36),
]


def _check(params):
    if len(str(params.get('iin') or '').strip()) != 12:
        raise ValueError('Введен неправильный ИИН!')


STMT = """
select d.rfbn_id,
       d.lastname || ' ' || d.firstname || ' ' || d.middlename fio,
       d.rnn,
       d.knp,
       d.pay_sum + d.sum_debt all_sum,
       pp.appointdate,
       pp.approvedate,
       pp.stopdate,
       d.pncp_date,
       d.status || ' - ' || st.name as status
  from pnpd_document d, pnpt_payment pp, rfds_doc_status st, person p
 where d.pncd_id = p.sicid
   and d.source_id = pp.pnpt_id(+)
   and substr(d.rfpm_id, 1, 4) in ('0706', '0709')
   and st.status = d.status
   and p.iin = trim(:iin)
 order by d.pncp_date, d.rfbn_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('iin',),
)
