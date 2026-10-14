# -*- coding: utf-8 -*-
"""8024. Информация о плательщиках (со штатной численностью 50 и более человек),
допустивших снижение количества участников СОСС.

Перенос WEB_REP_R_8024 (AIS 8024, группа 8000 «Паспорт СОСС», «ДРП»). Образец -
`docs/8000/Rep__8024.xlsx`.

Оригинал читал таблицу `social_tension_calculate_all` (её строит задание
`run` пакета SOCIAL_TENSION, то же, что для 5001-5006), группировал по названию
региона и печатал в заголовке пустой шаблон «в ____ 20___ года по отношению к
_____ 20___ года» - месяцы дописывали руками. Здесь расчёт тот же, что у 5001
(`util/social_tension.py`: плательщики со штатной численностью не менее 50
человек в базовом месяце - месяце даты «с», сравнение с месяцем даты «по»), а
пропуски заголовка заполняются датами формы.

Колонки, как в оригинале: число плательщиков; сколько участников они уплатили в
отчётном месяце (`cnt05`); число плательщиков со снижением (`perc > 0`) и
сколько участников за них не уплатили (`-razn`); то же для снижения на 50 % и
более. Строки - области (название КАТО, как в 5001), по алфавиту названия, как
`order by 1` в оригинале.
"""
from db.connect import LOADER_PROFILE
from util.social_tension import BASE, check_params
from util.xlsx_report import build_report, Col, Group

report_code = '8024'
report_name = ('Информация о плательщиках (со штатной\n'
               'численностью 50 и более человек), допустивших снижение '
               'количества участников системы\n'
               'обязательного социального страхования в {m_to} {y_to} года по '
               'отношению к {m_from} {y_from}\n'
               'года (8024, ДРП)')

# месяц даты «по» в предложном падеже, месяц даты «с» - в дательном
TITLE_SQL = """
select decode(extract(month from :d_to - 1), 1, 'январе', 2, 'феврале', 3, 'марте',
              4, 'апреле', 5, 'мае', 6, 'июне', 7, 'июле', 8, 'августе',
              9, 'сентябре', 10, 'октябре', 11, 'ноябре', 'декабре') m_to,
       extract(year from :d_to - 1) y_to,
       decode(extract(month from :d_from), 1, 'январю', 2, 'февралю', 3, 'марту',
              4, 'апрелю', 5, 'маю', 6, 'июню', 7, 'июлю', 8, 'августу',
              9, 'сентябрю', 10, 'октябрю', 11, 'ноябрю', 'декабрю') m_from,
       extract(year from :d_from) y_from
  from dual
"""

_PAYERS = 'Кол-во плательщиков'

COLUMNS = [
    Col('Регион', 'reg', 'text', 36),
    Group('Количество плательщиков, уплативших социальные отчисления', [
        Group('Всего', [
            Col(_PAYERS, 'cnt_all', 'int', 14),
            Col('Уплатили\nсоциальные\nотчисления за\nучастников СОСС\nза '
                'отчетный\nмесяц чел.', 'cnt05', 'int', 18),
        ]),
        Group('в том числе', [
            Group('со снижением', [
                Col(_PAYERS, 'cnt_dis', 'int', 14),
                Col('Не уплатили\nсоциальные\nотчисления за\nучастников '
                    'СОСС\nза отчетный\nмесяц чел.', 'sum_dis', 'int', 18),
            ]),
            Group('со снижением на 50% и более', [
                Col(_PAYERS, 'cnt50', 'int', 14),
                Col('Не уплатили\nсоциальные\nотчисления за\nучастников '
                    'СОСС\nза отчетный\nмесяц чел.', 'sum50', 'int', 18),
            ]),
        ]),
    ]),
]

STMT = f"""
with {BASE.lstrip()},
agg as (
    select c.obl,
           count(*) cnt_all,
           sum(c.cnt05) cnt05,
           count(case when c.perc > 0 then 1 end) cnt_dis,
           sum(case when c.perc > 0 then -c.razn end) sum_dis,
           count(case when c.perc >= 50 then 1 end) cnt50,
           sum(case when c.perc >= 50 then -c.razn end) sum50
      from calc c
     group by c.obl
)
select reg, cnt_all, cnt05, cnt_dis, sum_dis, cnt50, sum50, bold
  from (
    select b.name_ru reg, a.cnt_all, a.cnt05, a.cnt_dis, a.sum_dis,
           a.cnt50, a.sum50, 0 bold, 0 grp
      from agg a, cato_branch b
     where substr(b.rfbn_id, 1, 2) = a.obl
       and substr(b.rfbn_id, 3, 2) = '00'
    union all
    select null, sum(cnt_all), sum(cnt05), sum(cnt_dis), sum(sum_dis),
           sum(cnt50), sum(sum50), 1, 1
      from agg
  )
 order by grp, reg
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, date_range=True, check_params=check_params,
    title_sql=TITLE_SQL, bold_key='bold',
)
