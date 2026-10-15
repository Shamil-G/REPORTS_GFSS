# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 608 (процедура REP_R_608).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Сведения об уплате социальных отчислений (КНП 012, 017) по БИН за период:
платёжные поручения организации с разбивкой по месяцам, за которые уплачены
СО и (или) пеня, суммой и числом работников.

Источник - `pmpd_pay_doc` + `pmdl_doc_list` (по `mhmh_id`, только строки
реестра без работодателя `rfem_id is null`) + `tmst_state` (название
состояния); берутся платёжки в состояниях 5 и 104. Группировка по платёжке и
месяцу, сумма - `sum(dl.pay_sum)`, число работников - `count(unique sicid)`.

Месяц уплаты. В оригинале это `tlsd.to_date_def(nvl(dl.period, pd.period),
'mmyyyy', add_months(trunc(pd.pay_date, 'month'), -1))`: период строкой `ммгггг`,
а если он пуст или не разбирается - месяц перед датой платежа. Функция
(пакет `TLSD` схемы SSWH) при ошибке разбора пишет в журнал и возвращает
запасную дату; в отчёте она заменена на выражение `case`: `ммгггг` проверяется
шаблоном (месяц 01-12, год 1000-9999), иначе - запасной месяц. Условие
`between pDateFrom and pDateTo` заменено на `>= :d_from and < :d_to` (:d_to -
сутки после введённой даты «по», так что месяц, начало которого не позже
введённой даты, как в оригинале).

Проверка БИНа в оригинале была только в форме; здесь тоже ровно 12 знаков.
Подсказка `rule` оптимизатору не переносится. Итоги по колонкам в оригинале
закомментированы - не выводятся. Заголовок «Периоды за которые уплачены СО и
(или) пене» - группа из трёх колонок (период, сумма, число).

Таблицы `pmpd_pay_doc`, `pmdl_doc_list`, `tmst_state` reports_test видит -
отчёт проверен запуском на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group

report_code = '608'
report_name = ('Сведения о поступлениях СО от БИН {bin} за период с '
               '{date_from} г. по {date_to} г.')

COLUMNS = [
    Col('БИН', 'p_rnn', 'center', 16),
    Col('Наименование', 'p_name', 'text', 40),
    Col('№ платежного поручения', 'doc_nmb', 'center', 18),
    Col('Дата платежного поручения', 'doc_date', 'date', 16),
    Col('Сумма платежного поручения', 'pay_sum', 'money', 18, total=False),
    Col('КНП', 'cipher_id_knp', 'center', 8),
    Group('Периоды, за которые уплачены СО и (или) пеня', [
        Col('Период(ы)', 'pay_month', 'date', 14),
        Col('Сумма', 'sum_pay', 'money', 16, total=False),
        Col('Кол-во', 'cnt', 'int', 10, total=False),
    ]),
    Col('Статус', 'state_name', 'text', 18),
]


def _check(params):
    if len(str(params.get('bin') or '').strip()) != 12:
        raise ValueError('Введен неправильный БИН!')


# :bin - БИН; :d_from, :d_to - период (d_to исключительная).
STMT = """
select s.p_rnn, s.p_name, s.doc_nmb, s.doc_date, s.pay_sum, s.cipher_id_knp,
       s.pay_month, sum(s.sum_pay) sum_pay, count(unique s.sicid) cnt,
       s.state_name
  from (
    select dl.sicid,
           (case when regexp_like(nvl(dl.period, pd.period),
                                  '^(0[1-9]|1[0-2])[1-9][0-9]{3}$')
                 then to_date(nvl(dl.period, pd.period), 'mmyyyy')
                 else add_months(trunc(pd.pay_date, 'month'), -1) end) pay_month,
           pd.p_rnn, pd.p_name, pd.doc_nmb, pd.doc_date, pd.pay_sum,
           pd.cipher_id_knp, dl.pay_sum sum_pay, rtrim(ts.name) state_name
      from pmpd_pay_doc pd, pmdl_doc_list dl, tmst_state ts
     where pd.cipher_id_knp in ('012', '017')
       and dl.rfem_id is null
       and pd.mhmh_id = dl.mhmh_id
       and pd.tmst_id in (5, 104)
       and pd.tmst_id = ts.tmst_id
       and pd.p_rnn = trim(:bin)) s
 where s.pay_month >= :d_from and s.pay_month < :d_to
 group by s.p_rnn, s.p_name, s.doc_nmb, s.doc_date, s.pay_sum,
          s.cipher_id_knp, s.pay_month, s.state_name
 order by s.pay_month, s.doc_date
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=_check,
    title_params=('bin',),
)
