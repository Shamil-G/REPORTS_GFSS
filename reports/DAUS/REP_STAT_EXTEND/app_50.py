# -*- coding: utf-8 -*-
"""Приложение 50. Назначенные социальные выплаты в зависимости от дохода
(доля от МЗП), по выбранному виду выплаты.

Перенос REP_STAT_EXTEND.app_50_spool + Rep_app_50 (pck_utf8.sql,
8999-9401). Реестр: группа 1500, вызов app_50_1m('m') и аналоги; третий
параметр формы (Rep.ParAsChar(3)) выбирает вид выплаты 0701-0705 - в
Python это обычный параметр формы `rfpm_id` (справочник LIST_RFPM,
model/list_reports.py), а не 5 модулей: SQL и колонки при любом виде
выплаты одинаковы, меняется только фильтр и слова в названии.

Название отчёта зависит от rfpm_id (строки 9376-9391 - "по потери
кормильца"/"по утрате трудоспособности"/...), а не только от периода -
для этого в build_report добавлен общий параметр text_params (см.
util/xlsx_report.py): подстановка вида "{имя_параметра}" в name, отдельно
от {period}.

Доход считается как отношение sum_avg (среднемесячный доход, принятый для
исчисления выплаты) к mrzp (МЗП на дату записи - уже готовое поле строки,
доп. справочник не нужен) и режется на те же 12 бакетов, что в app_47.
`app_50_spool` (не `_old`) - современная, отрефакторенная версия процедуры
в самом пакете, с чистыми границами `>= p_DatB and < p_DatE+1` - уже в
целевом виде, trunc/between отсутствуют.

Доля в % (`doly_cnt`) считается от ОБЩЕГО количества назначений по этому
виду выплаты, ВКЛЮЧАЯ не попавшие ни в один бакет (coun is null, "интервал
дохода не определен" - строка 9210) - такие записи есть в знаменателе, но
сами никогда не показываются строкой (справочник s_incominsize покрывает
только 12 значений, "00" туда не входит). Поэтому 12 видимых долей в сумме
дают немного меньше 100%, если такие записи есть - это не ошибка переноса,
а точное повторение оригинала (строка 9271: sum по value_type=55 без
фильтра по tag).

Как и app_47/48: НЕТ занижения нулей (blank_zero=False) - PrnOneGoup
печатает значения без проверки "<>0" (строки 9276-9279), а отсутствующий
бакет по умолчанию даёт 0, а не пусто (p_a/p_b инициализированы 0 до
поиска в tbl, строка 9273-9274).
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col

report_code = 'APP.50'
# cSPTitle собирается из двух частей (строки 9354-9372): общий текст +
# слова по виду выплаты. {rfpm_id} - подстановка по параметру формы (см.
# text_params ниже), а не по периоду.
report_name = ('Сведения о назначенных социальных выплатах по{rfpm_id}'
               'в зависимости от дохода{period}')

# Дословно из веток If iTypePay=... (строки 9376-9391). Пробелы по краям -
# как в оригинале (' потери кормильца ' и т.д.), чтобы стыковаться с
# соседними частями report_name без своих пробелов.
_RFPM_TEXT = {
    '0701': ' потери кормильца ',
    '0702': ' утрате трудоспособности ',
    '0703': ' потери работы ',
    '0704': (' потери дохода в связи с беременностью и родами, с '
             'усыновлением (удочерением) новорожденного ребенка (детей) '),
    '0705': (' потери дохода в связи с уходом за ребенком по достижении '
             'им возраста одного года '),
}

# Begin блок Rep_app_50 (строки 9393-9401).
_period_label = make_period_label({
    1: ', за {Month} месяц {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за 9 месяцев {year} года ',
    5: ', за {year} год ',
})

COLUMNS = [
    Col('Размер дохода', 'razmer_doh', 'text', 30),
    Col('Количество* получателей, человек', 'cnt_mz', 'int'),
    Col('Сумма назначенных СВбр, тенге', 'sum_sv', 'money', 18),
    Col('Доля в % к общему количеству получателей', 'doly_cnt', 'money', 16),
]

FOOTNOTE = (
    '* - количество человек, которым СВ утверждена Департаментами по '
    'контролю и по социльной защите в отчетном периоде'
)

# :d_from / :d_to - границы отчётного периода, :d_to исключительная.
# :rfpm_id - выбранный вид выплаты (LIST_RFPM), обязательный параметр формы.
#
# base - строки sipr_maket_first_approve_2 выбранного вида выплаты за
# период, coun - бакет дохода (доля от МЗП), null - интервал не определён
# (нет sum_avg либо mrzp пустой/нулевой, nullif защищает от деления на 0 -
# ORA-01476 в оригинале, строка 9142). person - только как фильтр
# существования (exists, не join - sicid уникален, join размножал бы
# строки, строки 9153-9159 оригинала).
STMT = """
with base as (
    select case
             when d.ratio is null then null
             when d.ratio <  1 then  1
             when d.ratio <  2 then  2
             when d.ratio <  3 then  3
             when d.ratio <  4 then  4
             when d.ratio <  5 then  5
             when d.ratio <  6 then  6
             when d.ratio <  7 then  7
             when d.ratio <  8 then  8
             when d.ratio <  9 then  9
             when d.ratio < 10 then 10
             when d.ratio = 10 then 11
             else                   12
           end coun,
           d.sum_all
      from (select s.sum_all,
                   s.sum_avg / nullif(s.mrzp, 0) ratio
              from sipr_maket_first_approve_2 s
             where s.date_approve >= :d_from
               and s.date_approve <  :d_to
               and substr(s.rfpm_id, 1, 4) = :rfpm_id
               and s.sum_all > 0
               and exists (select 1 from person pr where pr.sicid = s.sicp_id)
           ) d
),
agg as (
    select coun,
           count(1)     cnt_mz,
           sum(sum_all) sum_sv
      from base
     group by coun
),
totals as (
    select sum(cnt_mz) all_cnt from agg
)
select s.is_name                                    razmer_doh,
       nvl(a.cnt_mz, 0)                              cnt_mz,
       nvl(a.sum_sv, 0)                              sum_sv,
       case when t.all_cnt > 0
            then nvl(a.cnt_mz, 0) * 100 / t.all_cnt
            else 0 end                                doly_cnt
  from s_incominsize s, agg a, totals t
 where a.coun(+) = s.is_id
 order by s.is_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
    text_params={'rfpm_id': _RFPM_TEXT},
)
