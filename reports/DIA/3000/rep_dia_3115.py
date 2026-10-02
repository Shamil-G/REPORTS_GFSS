# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Отчеты ДИА», отчёт 3115 «График выплаты социальных выплат»
(процедура REP_R_3115, «rep_nnn_2017»).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

График выплаты социальных выплат из ГФСС (уточнённый) на день выплаты: по типу
документа, отделению, этапу, получателю (банк / пенсионный фонд) и, для типа
графика 1, способу выплаты - суммы и число по видам (0701-0705) и всего.

Параметры оригинала: 1 - день выплаты (`pndy_daypay.pay_day`), 2 - тип
графика (1 - выплаты, удержания и недополученное: документы типов 6, 8, 4; 2 -
перечисления в НПФ: тип 7), 3 - область (в оригинале закомментирована:
фактически брался филиал пользователя `setup.Branch`; здесь это параметр
«область», «00» - вся республика).

Месяц и этапы выплаты находятся по календарю выплат `pndy_daypay` по дню
выплаты (`stagebegin`, `stageend`, `pay_month`); нет такого дня - ошибка «Нет
такого дня выплаты!». Источник - `pnpd_document` (месяц `pncp_date =
pay_month`, этапы `pnsp_id between stagebegin and stageend`, виды `07%`,
состояния 0, 1, 2, 5, 3, 7). Сумма - `pay_sum + sum_debt`, число - документы
типа 6. Для типа 1 получатель - `rfrc_recipient_last`, для типа 2 - `rfpf_pensfund`
(`код - название`); способ выплаты (`rfpw_id`) только у типа 1. Сортировка -
тип документа (6, 4, 8, 7), отделение, этап, способ, получатель.

Холостой цикл оригинала (выборка всех строк в `PNPD_DOCUMENT%ROWTYPE` без
вывода) не переносится. Первая строка названия оригинала («код филиала
пользователя - название») у центральных отчётов не выводится. `<br>` в
заголовках заменены пробелами. Итоги по всем числовым колонкам
(`SetColSumTotal` после каждой).

Колонки зависят от типа графика (есть ли «Способ выплаты»), поэтому
модуль собирает отчёт под нужный тип при первом обращении
(`_variant`), а `do_report` / `thread_report` просто выбирают его.

`pndy_daypay`, `rfrc_recipient_last`, `rfpf_pensfund` лежат в схеме SSWH боевой БД,
в тестовой reports_test недоступны: на данных отчёт не сверен.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col, Group, parse_date

report_code = '3115'
report_name = ('График выплаты социальных выплат из ГФСС на день выплаты '
               '{pay_day_text} года (уточненный)')

_SUM = 'Сумма'
_CNT = 'Кол-во'
_KINDS = (
    ('0701', 'Соцвыплата страхования на случай утраты кормильца'),
    ('0702', 'Соцвыплата страхования на случай утраты трудоспособности'),
    ('0703', 'Соцвыплата страхования на случай потери работы'),
    ('0704', 'Соцвыплата страхования по беременности и родам'),
    ('0705', 'Соцвыплата страхования по уходу за ребенком до 1 года'),
    ('all', 'Всего'),
)


def _columns(pay_type):
    cols = [
        Col('Тип выплаты', 'pay_type', 'text', 26),
        Col('Код отделения', 'rfbn_id', 'center', 10),
        Col('Наименование отделения', 'rfbn_name', 'text', 30),
        Col('Этап', 'pnsp_id', 'center', 8),
        Col('Получатель (банк)', 'rfrc_name', 'text', 36),
    ]
    if pay_type == '1':
        cols.append(Col('Способ выплаты', 'rfpw_id', 'center', 10))
    for code, title in _KINDS:
        cols.append(Group(title, [Col(_SUM, f'sum_{code}', 'money', 18),
                                  Col(_CNT, f'cnt_{code}', 'int', 12)]))
    return cols


def _stmt(pay_type):
    if pay_type == '1':
        ridt = 'dt.ridt_id in (6, 8, 4)'
        recipient = ("(select a.rfrc_id || ' - ' || rc.name from rfrc_recipient_last rc "
                     "where rc.rfrc_id = a.rfrc_id) rfrc_name")
        rfpw_in, rfpw_out = 'dt.rfpw_id', 'dt.rfpw_id'
    else:
        ridt = 'dt.ridt_id = 7'
        recipient = ("(select pf.id || ' - ' || pf.shortname from rfpf_pensfund pf "
                     "where pf.id = a.rfrc_id) rfrc_name")
        rfpw_in, rfpw_out = 'null rfpw_id', 'null'
    sums = []
    for code, _ in _KINDS[:5]:
        sums.append(f"sum(case when dt.rfpm_id like '{code}%' then dt.pay_sum + dt.sum_debt else 0 end) sum_{code}")
        sums.append(f"sum(case when dt.rfpm_id like '{code}%' and dt.ridt_id = 6 then 1 else 0 end) cnt_{code}")
    sums_text = ',\n               '.join(sums)
    return f"""
with dd as (
    select stagebegin, stageend, pay_month
      from pndy_daypay
     where pay_day = :pay_day
       and rownum = 1
)
select rt.name pay_type,
       a.rfbn_id,
       bn.name rfbn_name,
       a.pnsp_id,
       {recipient},
       a.rfpw_id,
       sum_0701, cnt_0701, sum_0702, cnt_0702, sum_0703, cnt_0703,
       sum_0704, cnt_0704, sum_0705, cnt_0705,
       sum_0701 + sum_0702 + sum_0703 + sum_0704 + sum_0705 sum_all,
       cnt_0701 + cnt_0702 + cnt_0703 + cnt_0704 + cnt_0705 cnt_all
  from (select dt.ridt_id,
               dt.rfbn_id,
               dt.pnsp_id,
               dt.rfrc_id,
               {rfpw_in},
               {sums_text}
          from pnpd_document dt, dd
         where dt.pncp_date = dd.pay_month
           and dt.rfbn_id like case when :rfbn_id like '00%' then '%'
                                    else substr(:rfbn_id, 1, 2) || '%' end
           and dt.pnsp_id between dd.stagebegin and dd.stageend
           and dt.rfpm_id like '07%'
           and dt.status in (0, 1, 2, 5, 3, 7)
           and {ridt}
         group by dt.ridt_id, dt.rfbn_id, dt.pnsp_id, dt.rfrc_id, {rfpw_out}) a,
       rfbn_branch bn, ridt_doc_type rt
 where a.rfbn_id = bn.rfbn_id
   and a.ridt_id = rt.ridt_id
 order by decode(a.ridt_id, 6, 1, 4, 2, 8, 3, 7, 4, 5), a.rfbn_id, a.pnsp_id,
          a.rfpw_id, a.rfrc_id
"""


# Дата выплаты и её заголовок: нет в календаре - ошибка, как в оригинале.
TITLE_SQL = """
select to_char(pay_day, 'dd.mm.yyyy') pay_day_text
  from pndy_daypay
 where pay_day = :pay_day
   and rownum = 1
"""


def _check(params):
    # дата из формы (строка) -> date: бинд :pay_day должен быть датой
    params['pay_day'] = parse_date(params['pay_day'])
    if str(params.get('pay_type') or '1') not in ('1', '2'):
        raise ValueError('Недопустимый тип графика!')


_variants = {}


def _variant(params):
    pay_type = str(params.get('pay_type') or '1')
    if pay_type not in _variants:
        _variants[pay_type] = build_report(
            code=report_code, name=report_name, columns=_columns(pay_type),
            stmt=_stmt(pay_type), profile=LOADER_PROFILE, totals=True,
            check_params=_check, title_sql=TITLE_SQL,
            title_not_found='Нет такого дня выплаты!')
    return _variants[pay_type]


def do_report(file_name, **params):
    return _variant(params)[0](file_name, **params)


def thread_report(file_name, **params):
    return _variant(params)[1](file_name, **params)
