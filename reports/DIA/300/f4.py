# -*- coding: utf-8 -*-
# ============================================================
# ЗАМЕНЁН (дублируется) - по сообщению Заказчика (02.10.2026).
# Заменяющий отчёт: консолидированные, 6CB.
# Закомментирован в model/list_reports.py (группа «Согласно Приказа Минтруда (REP_MINTRUD)»), ключ 02. Код не удалён - для итоговой сверки.
# Oracle: REP_MINTRUD.Fill_F4, Rep_4m/4k/4hy/4_9m/4y
# ============================================================
"""============================================================
REP_MINTRUD (Rep_Mintrud.pck) - см. заглавие f3.py про разделение с
REP_STAT_EXTEND.
============================================================

Форма 4 (Rep_Mintrud.Fill_F4 + Rep_4m/_4k/_4hy/_4_9m/_4y). Число
получателей и суммы социальных выплат из ГФСС, по регионам и видам СВ.

Перенос Rep_Mintrud.pck (строки 629-853 - Fill_F4/Prn_F4/Rep_4*). Реестр:
rep_mintrud.fill_f4(rep_year, date_type, date_spare) - подтверждён
сборочным логом (04.09.2026). Только типы периода 1-5 (в отличие от F3,
обёртки на 24 месяца у этой формы нет).

Источник - `cur_F4` (единственный действующий курсор; в исходнике под ним
закомментированы ещё два старых варианта через `sifl_file`/`pnpt_payment`,
не переносятся). `pnpd_document` + `pnpt_payment`, регион - по ПОСЛЕДНЕЙ
(`first_value(...) over (partition by pncd_id order by pncp_date desc)`)
записи документа на человека (`pncd_id`), а не по организации, как в
F3/REP_STAT_EXTEND - здесь регион берётся прямо из самого документа выплаты
(`substr(rfbn_id,1,2)`).

Строка "Всего" по региону - НЕ отдельный count(distinct) по всем видам
сразу, а сумма уже посчитанных по каждому виду счётчиков (как в оригинале,
строки 700-712: `tbl(region).cnt` копится при разборе КАЖДОЙ из 5
value_type=4 записей для этого региона) - если человек получает выплаты
по двум видам сразу, он в "Всего" считается дважды. Это не ошибка переноса,
а точное повторение оригинала.

Порядок видов выплат (0702,0701,0703,0704,0705) - не алфавитный, тот же,
что в app_32/55 REP_STAT_EXTEND (rvids). Занижение нулей здесь - только
по ОТСУТСТВИЮ данных (PrnOnePair проверяет `tbl.exists`, не значение,
строки 693-699) - blank_zero=False, пропуски дают NULL из LEFT JOIN.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'MINTRUD.F4'
# cF4Title дословно (строки 83-85) - используется и в F5 (там своего
# заголовка в исходнике нет, см. f5.py).
report_name = ('Сведения о числе получателей и суммах социальных выплат '
               'из АО "Государственный фонд социального страхования" за '
               '{period}')

# Дословно из Rep_4m/_4k/_4hy/_4_9m/_4y (строки 766-853) - те же фразы,
# что в f3.py (месяц строчными, с пробелом перед годом; "год", не "года").
_period_label = make_period_label({
    1: '{month} {year} года',
    2: '{n} квартал {year} года',
    3: '{n} полугодие {year} года',
    4: '9 месяцев {year} года',
    5: '{year} год',
})

_COUNT = 'Число получателей, человек'
_SUM = 'Сумма выплат, тенге'

# (код, суффикс колонки, заголовок группы) - порядок дословно из rfpms
# (строка 693: TVList('0702', '0701', '0703', '0704', '0705')).
_TYPES = [
    ('0702', 'по случаю утраты трудоспособности'),
    ('0701', 'по случаю потери кормильца'),
    ('0703', 'по случаю потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, '
             'с усыновлением (удочерением) новорожденного ребенка(детей)'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

COLUMNS = [
    Col('Регион', 'reg', 'text', 30),
    Group('Всего', [
        Col(_COUNT, 'cnt_all', 'int'),
        Col(_SUM, 'sum_all', 'money', 18),
    ]),
    Group('в том числе по видам социальных выплат', [
        Group(title, [
            Col(_COUNT, f'cnt_{code}', 'int'),
            Col(_SUM, f'sum_{code}', 'money', 18),
        ]) for code, title in _TYPES
    ]),
]

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# Регион - по последнему документу на человека (pncd_id), не по
# организации (в отличие от F3).
STMT = """
with base as (
    select substr(d.rfpm_id, 1, 4) rfpm,
           d.pncd_id,
           d.pay_sum + d.sum_debt sum_pay,
           first_value(substr(d.rfbn_id, 1, 2)) over (
               partition by d.pncd_id order by d.pncp_date desc) reg
      from pnpd_document d, pnpt_payment pp
     where d.source_id = pp.pnpt_id(+)
       and d.pncp_date >= :d_from
       and d.pncp_date <  :d_to
       and substr(d.rfpm_id, 1, 4) in ('0701', '0702', '0703', '0704', '0705')
       and d.ridt_id in (4, 6, 7, 8)
       and d.status in (0, 1, 2, 3, 5, 7)
       and d.pnsp_id > 0
),
agg as (
    select rfpm, reg,
           count(distinct pncd_id) cnt,
           sum(sum_pay)            sm
      from base
     group by rfpm, reg
),
pivot as (
    select reg,
           sum(case when rfpm = '0702' then cnt end) cnt_0702,
           sum(case when rfpm = '0702' then sm  end) sum_0702,
           sum(case when rfpm = '0701' then cnt end) cnt_0701,
           sum(case when rfpm = '0701' then sm  end) sum_0701,
           sum(case when rfpm = '0703' then cnt end) cnt_0703,
           sum(case when rfpm = '0703' then sm  end) sum_0703,
           sum(case when rfpm = '0704' then cnt end) cnt_0704,
           sum(case when rfpm = '0704' then sm  end) sum_0704,
           sum(case when rfpm = '0705' then cnt end) cnt_0705,
           sum(case when rfpm = '0705' then sm  end) sum_0705,
           sum(cnt) cnt_all,
           sum(sm)  sum_all
      from agg
     group by reg
)
select rr.rfrg_id || ' - ' || rr.name reg,
       p.cnt_all, p.sum_all,
       p.cnt_0702, p.sum_0702,
       p.cnt_0701, p.sum_0701,
       p.cnt_0703, p.sum_0703,
       p.cnt_0704, p.sum_0704,
       p.cnt_0705, p.sum_0705
  from RFRG_REGION rr, pivot p
 where rr.rfrg_id != '00'
   and p.reg(+) = rr.rfrg_id
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label,
)
