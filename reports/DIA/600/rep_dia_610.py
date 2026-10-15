# -*- coding: utf-8 -*-
"""============================================================
AIS_GFSS, группа «Справки», отчёт 610 (процедура REP_SITE_610).
Список работ: rep_stat_extend/docs/TASKS_2026-10-02.md.
============================================================

Работники организации (БИН), по которым в прошлом месяце поступили
социальные отчисления, рассчитанные от дохода менее 1 МЗП: ИИН, ФИО, сумма
отчисления, месяц, за который уплачено.

Рабочая таблица. Оригинал читал `tbl_less_mzp`, которую заполнял пакет
`PKG_LESS_MZP.Fill` (с `delete`, циклами `update` и т.п.). Отчёты приложения
читают БД только на чтение, и таблицы-посредника быть не должно, поэтому
расчёт пакета выполнен запросом прямо по `si_member_2`:
 - платежи КНП 012 за прошлый календарный месяц (`pay_date`), уплаченные за
   более ранние месяцы (`pay_month < первое число прошлого месяца`) и не
   раньше февраля 2013 (с него действует 1 МЗП);
 - ЕСП (`type_payer = 'E'`) и единый платёж (`type_payment = 'O'`)
   исключены; в тексте AIS буквы кириллические (`'Е'`, `'О'`), а в данных
   латинские, так что условие оригинала ничего не отсекало. Здесь
   используются латинские, как задумано автором пакета;
 - группировка по работнику, БИНу и месяцу, `sum(sum_pay)`, отбор
   `sum(trunc(cnt_mzp, 5)) < 1`;
 - `mzp` - всего уплачено за этот месяц (все платежи КНП 012 с февраля 2013),
   делённое на размер 1 МЗП `min_so(pay_month)` (функция SSWH, ступенчатая
   таблица размеров по годам); остаются те, у кого `mzp < 1`, как фильтр
   оригинала `mzp < 1`.

Название. Наименование организации берётся из `rfon_organization.nm_ru` по
БИНу (в оригинале `nk_minfin_iin`, справочник мёртв); нет организации - отчёт
не строится (в оригинале процедура просто выходила). Период в названии -
прошлый месяц, как `pDateFrom := trunc(add_months(sysdate, -1), 'MM')`.

Проверка БИНа: 12 знаков, иначе «Неправильный БИН!». `p.rn` заменён на
`p.iin`. Сортировка - по ФИО и месяцу, как `order by 2, 4`.

`si_member_2`, `person`, `rfon_organization` reports_test видит; функция
`min_so` в SSWH и reports_test недоступна: запрос без неё проверен на данных.
"""
from db.connect import LOADER_PROFILE
from util.xlsx_report import build_report, Col

report_code = '610'
report_name = ('Список работников {name}, БИН - {bin}, по которым с {d_from} '
               'по {d_to} года поступили социальные отчисления, рассчитанные '
               'от дохода в сумме менее 1 МЗП')

COLUMNS = [
    Col('ИИН работника', 'iin', 'center', 16),
    Col('ФИО работника', 'fio', 'text', 40),
    Col('Сумма социального отчисления, тенге', 'sum_pay', 'money', 20),
    Col('Период', 'pay_month', 'date', 14),
]


def _check(params):
    if len(str(params.get('bin') or '').strip()) != 12:
        raise ValueError('Неправильный БИН!')


TITLE_SQL = """
select o.nm_ru name,
       to_char(trunc(add_months(sysdate, -1), 'MM'), 'dd.mm.yyyy') d_from,
       to_char(last_day(add_months(sysdate, -1)), 'dd.mm.yyyy') d_to
  from rfon_organization o
 where o.bin = trim(:bin) and rownum = 1
"""

# :bin - БИН. Прошлый месяц считается от текущей даты, как в оригинале.
STMT = """
select p.iin,
       p.lastname || ' ' || p.firstname || ' ' || p.middlename fio,
       t.sum_pay,
       t.pay_month
  from (select m.sicid, m.p_rnn, m.pay_month, sum(m.sum_pay) sum_pay
          from si_member_2 m
         where m.knp = '012'
           and m.p_rnn = trim(:bin)
           and m.pay_date >= add_months(trunc(sysdate, 'MM'), -1)
           and m.pay_date <  trunc(sysdate, 'MM')
           and m.pay_month <  add_months(trunc(sysdate, 'MM'), -1)
           and m.pay_month >= date '2013-02-01'
           and coalesce(m.type_payer, 'X') != 'E'
           and coalesce(m.type_payment, 'X') != 'O'
         group by m.sicid, m.p_rnn, m.pay_month
        having sum(trunc(m.cnt_mzp, 5)) < 1) t,
       person p
 where t.sicid = p.sicid
   and (select sum(a.sum_pay)
          from si_member_2 a
         where a.knp = '012'
           and a.sicid = t.sicid
           and a.p_rnn = t.p_rnn
           and a.pay_month = t.pay_month
           and a.pay_date >= date '2013-02-01') / min_so(t.pay_month) < 1
 order by fio, t.pay_month
"""

do_report, thread_report = build_report(
    code=report_code, name=report_name, columns=COLUMNS, stmt=STMT,
    profile=LOADER_PROFILE, check_params=_check, title_params=('bin',),
    title_sql=TITLE_SQL, title_not_found='Организация с таким БИН не найдена!',
)
