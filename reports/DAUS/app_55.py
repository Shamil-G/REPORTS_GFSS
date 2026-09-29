# -*- coding: utf-8 -*-
"""Приложение 55. Средний размер назначенных социальных выплат по регионам
и видам риска (все 5 видов СВ сразу, без фильтра).

Перенос REP_STAT_EXTEND.app_55_spool + Rep_app_55 (pck_utf8.sql,
11447-11899). Реестр: группа 1550, вызов app_55_1m('m') и аналоги.

app_55_spool - уже отрефакторенная версия (см. комментарии в самом
пакете, строки 11519-11524): динамический SQL с четырьмя уровнями
вложенности заменён статикой в два уровня, `trunc(date_approve) between`
заменён на `>= and <` (не блокирует индекс). Год для "с начала года"
считается от p_DatB (начала периода), а не от p_DatE, как в app_32/f3 -
явно отмечено в исходнике как сознательно сохранённое отличие (строки
11491-11493). Для обычных типов периода (1-5) это не имеет значения:
границы периода всегда лежат в одном календарном году.

Порядок видов риска (rvids, строка 11732) - 0702,0701,0703,0704,0705, тот
же не алфавитный порядок, что и в app_32.

Зануление - НЕ через "если ноль то пусто": Rep_app_55.PrnOneGoup вообще не
вызывает Rep.td, если для (регион,вид) не нашлось ни одной строки в EAV за
весь год (строки 11753-11774, нет else-ветки). Но spool ВСЕГДА пишет в EAV
запись, если для (регион,вид) была хоть одна СВ за год, даже если в САМОМ
периоде их не было (decode(cnt_r,0,0,...) даёт 0, а не null, и "0 is not
null" истинно - строка 11556) - то есть 0 показывается как 0, а не пусто,
и пусто получается только когда данных нет вообще ни за период, ни за год.
Поэтому здесь blank_zero=False, а "пусто" получается из настоящего SQL
NULL (регион+вид не встретились в данных за год вообще), не из flag'а.

СОЗНАТЕЛЬНОЕ ОТСТУПЛЕНИЕ (по прецеденту app_32/38, согласовано 28.09.2026):
оригинал требует Rep.SetColSumTotal на всех 10 колонках среднего - то есть
итоговая строка суммирует средние по регионам, что арифметически неверно.
Здесь итог считается правильно - через avg_of (сумма/количество), как и
везде в проекте.
"""
from db.connect import LOADER_PROFILE
from util.period import make_period_label
from util.xlsx_report import build_report, Col, Group

report_code = 'APP.55'
# cSPTitle дословно (строки 11719-11720, перенос строки - артефакт
# форматирования кода, в HTML схлопывался в пробел).
report_name = ('Сведения о средних размерах назначенных социальных выплат '
               'из АО "Государственный фонд социального страхования"'
               '{period}')

# Begin блок Rep_app_55 (строки 11886-11898).
_period_label = make_period_label({
    1: ', за {Month} {year} года ',
    2: ', за {n} квартал {year} года ',
    3: ', за {n} полугодие {year} года ',
    4: ', за  9 месяцев {year} года ',
    5: ', за {year} год ',
})

_PERIOD = 'за отчетный  период.'  # двойной пробел и точка - дословно
_YEAR = 'с начала года'

# (код, заголовок группы) - порядок как в rvids оригинала (не алфавитный).
_TYPES = [
    ('0702', 'на случай утраты трудоспособности'),
    ('0701', 'на случай потери кормильца'),
    ('0703', 'на случай потери работы'),
    ('0704', 'на случай потери дохода в связи с беременностью и родами, '
             'с усыновлением (удочерением) новорожденного ребенка (детей)'),
    ('0705', 'на случай потери дохода в связи с уходом за ребенком по '
             'достижении им возраста 1 года'),
]

COLUMNS = [
    Col('Области', 'reg', 'text', 30),
    Group('Средний размер назначенных социальных выплат*, (тенге)', [
        Group(label, [
            Col(_PERIOD, f'avgp_{code}', 'avg', 16,
                avg_of=(f'sum_r_{code}', f'cnt_r_{code}')),
            Col(_YEAR, f'avgy_{code}', 'avg', 16,
                avg_of=(f'sum_y_{code}', f'cnt_y_{code}')),
        ]) for code, label in _TYPES
    ]),
]

FOOTNOTE = ('* средний размер выплат определяется как средний назначенный '
           'размер социальных выплат')

# :d_from / :d_to - границы отчётного периода, :d_to исключительная;
# :y_from - начало года (см. docstring про p_Dat1 := trunc(p_DatB,'YEAR')).
# Фильтра по видам выплат нет и не было в оригинале - берутся все.
_CODES = [c for c, _ in _TYPES]


def _join_block():
    """Пять внешних соединений agg x agg x ... по виду выплаты, старым
    синтаксисом Oracle: запятая + (+), без ANSI JOIN."""
    aliases = ', '.join(f'agg a{i}' for i in range(1, 6))
    conds = '\n   and '.join(
        f"a{i}.obl(+) = rr.rfrg_id and a{i}.rfpm(+) = '{code}'"
        for i, code in enumerate(_CODES, start=1)
    )
    cols = ',\n       '.join(
        f'a{i}.avg_om avgp_{code}, a{i}.sum_r sum_r_{code}, a{i}.cnt_r cnt_r_{code}, '
        f'a{i}.avg_by avgy_{code}, a{i}.sum_y sum_y_{code}, a{i}.cnt_y cnt_y_{code}'
        for i, code in enumerate(_CODES, start=1)
    )
    return aliases, conds, cols


_ALIASES, _CONDS, _COLS = _join_block()

STMT = f"""
with agg as (
    select substr(s.rfbn_id, 1, 2) obl,
           substr(s.rfpm_id, 1, 4) rfpm,
           sum(case when s.date_approve >= :d_from then 1 else 0 end)         cnt_r,
           sum(case when s.date_approve >= :d_from then s.sum_all else 0 end) sum_r,
           count(1)       cnt_y,
           sum(s.sum_all) sum_y,
           decode(sum(case when s.date_approve >= :d_from then 1 else 0 end), 0, 0,
                  sum(case when s.date_approve >= :d_from then s.sum_all else 0 end)
                  / sum(case when s.date_approve >= :d_from then 1 else 0 end)) avg_om,
           decode(count(1), 0, 0, sum(s.sum_all) / count(1))                    avg_by
      from sipr_maket_first_approve_2 s
     where s.date_approve >= :y_from
       and s.date_approve <  :d_to
     group by substr(s.rfbn_id, 1, 2), substr(s.rfpm_id, 1, 4)
)
select rr.name reg,
       {_COLS}
  from RFRG_REGION rr, {_ALIASES}
 where {_CONDS}
 order by rr.rfrg_id
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, period=True, totals=True, blank_zero=False,
    period_label=_period_label, footnote=FOOTNOTE,
)
