# -*- coding: utf-8 -*-
"""Общая часть отчётов 5001-5006 «Социальная напряженность» (AIS, пакет
SOCIAL_TENSION схемы DASORP).

Оригинал считал всё заранее: задание `run` строило три таблицы
(`social_tension_all_people` -> `social_tension_50` -> `social_tension_calculate_all`),
а шесть процедур `report_1..report_6` читали последнюю. Здесь три таблицы -
три CTE (`ppl`, `pay`, `calc`), общие для всех шести отчётов; каждый отчёт
дописывает к ним свою группировку.

Что считается. Берутся плательщики, у которых в БАЗОВОМ месяце (месяц даты «с»)
КНП 012 уплачен не менее чем за 50 участников (`count(distinct sicid)` по
`si_member_2`); для каждого сравнивается число участников в базовом и в
последнем месяце (месяц даты «по»): `cnt04` и `cnt05`; `perc = round(100 -
cnt05/cnt04*100, 2)` - снижение в процентах.

Плательщик и место - `rfon_organization` и `cato_branch` (решение Шамиля
13.10.2026): `rfon_organization.bin = p_rnn`, `rfon_organization.cato =
cato_branch.code`; область - первые два знака `cato_branch.rfbn_id`, район -
весь `rfbn_id` (код отделения). Оригинал брал отделение из `rfrr_id_region` и
делил старые 14, 05, 03, 08 на новые области вручную; в `cato_branch` у
организаций уже стоят все 20 текущих областей. Плательщик без КАТО или с КАТО,
которого нет в `cato_branch`, в расчёт не попадает - как плательщик без записи
в `rfrr_id_region` в оригинале.

Секция ОКЭД (A..U) - по первым двум знакам `rfon_organization.oked` (разделы
ОКЭД, диапазоны те же, что в `OKED1510544.sect_oked`); нет ОКЭД - `ZZ` «Без
секции». Оригинал брал секцию из `OKED1510544` по БИН, но она устарела и
неполна: покрывает 0,77 млн из 3,28 млн организаций, у 40 % общих БИН раздел
ОКЭД другой, БИН в ней повторяются (размножали плательщика при `select unique`).

Наименование плательщика - `rfon_organization.nm_ru` (оригинал - `nk_minfin_iin`,
мёртвый справочник).

Первый месяц и «горизонт» -7 месяцев: `pay_date > add_months(базовый месяц, -7)`
оставлено как в prepare_all_people_first (ветка «лёгкого плана» через
`si_member_2`; ветка второй половины месяца через `pmpd_pay_doc_s` /
`pmdl_doc_list_s` не переносилась).
"""
from util.xlsx_report import Col, parse_date

# Штатная численность, с которой плательщик попадает в расчёт (prepare_50).
MIN_STAFF = 50
# Снижение числа участников в процентах, с которого плательщик «допустил
# снижение в 2 и более раза» (perc >= 50): отчёты 5003, 5004, 5005.
CUT_PERC = 50
# Граница МСБ / крупные предприятия по числу работников в базовом месяце.
MSB_LIMIT = 250

# нижняя граница, верхняя граница, подпись; у последней верхней границы нет
BANDS = [
    (0, 10, 'до 10%'),
    (10, 20, 'от 10% до 20%'),
    (20, 30, 'от 20% до 30%'),
    (30, 40, 'от 30% до 40%'),
    (40, 50, 'от 40% до 50%'),
    (50, 60, 'от 50% до 60%'),
    (60, 70, 'от 60% до 70%'),
    (70, 80, 'от 70% до 80%'),
    (80, 90, 'от 80% до 90%'),
    (90, None, 'от 90% и более'),
]

# секция ОКЭД, наименование (дословно из шапки report_5; в D лишний пробел
# убран)
SECTIONS = [
    ('A', 'Сельское, лесное и рыбное хозяйство'),
    ('B', 'Горнодобывающая промышленность и разработка карьеров'),
    ('C', 'Обрабатывающая промышленность'),
    ('D', 'Электроснабжение, подача газа, пара и воздушное кондиционирование'),
    ('E', 'Водоснабжение; канализационная система, контроль над сбором и '
          'распределением отходов'),
    ('F', 'Строительство'),
    ('G', 'Оптовая и розничная торговля; ремонт автомобилей и мотоциклов'),
    ('H', 'Транспорт и складирование'),
    ('I', 'Услуги по проживанию и питанию'),
    ('J', 'Информация и связь'),
    ('K', 'Финансовая и страховая деятельность'),
    ('L', 'Операции с недвижимым имуществом'),
    ('M', 'Профессиональная, научная и техническая деятельность'),
    ('N', 'Деятельность в области административного и вспомогательного '
          'обслуживания'),
    ('O', 'Государственное управление и оборона; обязательное социальное '
          'обеспечение'),
    ('P', 'Образование'),
    ('Q', 'Здравоохранение и социальные услуги'),
    ('R', 'Искусство, развлечения и отдых'),
    ('S', 'Предоставление прочих видов услуг'),
    ('T', 'Деятельность домашних хозяйств, нанимающих домашнюю прислугу и '
          'производящих товары и услуги для собственного потребления'),
    ('U', 'Деятельность экстерриториальных организаций и органов'),
    ('ZZ', 'Без секции'),
]

# разделы ОКЭД (первые два знака кода) -> секция
_OKED_SECTIONS = [
    ('A', '01', '03'), ('B', '05', '09'), ('C', '10', '33'), ('D', '35', '35'),
    ('E', '36', '39'), ('F', '41', '43'), ('G', '45', '47'), ('H', '49', '53'),
    ('I', '55', '56'), ('J', '58', '63'), ('K', '64', '66'), ('L', '68', '68'),
    ('M', '69', '75'), ('N', '77', '82'), ('O', '84', '84'), ('P', '85', '85'),
    ('Q', '86', '88'), ('R', '90', '93'), ('S', '94', '96'), ('T', '97', '98'),
    ('U', '99', '99'),
]



def _sect_when(s, lo, hi):
    """Раздел ОКЭД [lo, hi] двумя операторами: >= lo and < следующий раздел."""
    cond = f"substr(o.oked, 1, 2) >= '{lo}'"
    if hi != '99':      # '99' - последний раздел, верхней границы нет
        cond += f" and substr(o.oked, 1, 2) < '{int(hi) + 1:02d}'"
    return f"when {cond} then '{s}'"


_SECT_CASE = 'case ' + ' '.join(
    _sect_when(s, lo, hi) for s, lo, hi in _OKED_SECTIONS) + " else 'ZZ' end"


def check_params(params):
    """Месяц даты «по» должен быть позже месяца даты «с»."""
    first = parse_date(params['date_first'])
    second = parse_date(params['date_second'])
    if (first.year, first.month) >= (second.year, second.month):
        raise ValueError('Месяц даты «по» должен быть позже месяца даты «с»: '
                         'сравниваются первый и последний месяцы периода')


def band_columns():
    """Десять колонок полос снижения b0..b9."""
    return [Col(title, f'b{i}', 'int', 12) for i, (_, _, title) in enumerate(BANDS)]


def band_sql(alias='c'):
    """count(...) по полосам снижения: b0 - perc > 0 и < 10, ... b9 - >= 90."""
    parts = []
    for i, (lo, hi, _) in enumerate(BANDS):
        low = f'{alias}.perc > 0' if lo == 0 else f'{alias}.perc >= {lo}'
        cond = low if hi is None else f'{low} and {alias}.perc < {hi}'
        parts.append(f'count(case when {cond} then 1 end) b{i}')
    return ',\n           '.join(parts)


# :d_from / :d_to - границы периода, :d_to исключительная (дата «по» + сутки).
# Базовый месяц - trunc(:d_from, 'mm'), последний - trunc(:d_to - 1, 'mm').
#
# ppl: в оригинале `Min(pay_month) Over(Partition By p_rnn)` считался по
# платежам ВСЕХ КНП, затем отбирались плательщики, чей самый ранний месяц в
# окне равен базовому, и лишь потом шёл отбор КНП 012. Здесь тот же порядок:
# min_mes по агрегату без отбора КНП, фильтр knp = '012' - в pay.
# zp - средняя «зарплата по платежу» cnt_mzp * mzp (в ветке si_member_2),
# sm - сумма перечисленных отчислений.
#
# calc: cnt05, zp05, sm05 - 0, если в последнем месяце платежей нет;
# razn = cnt05 - cnt04 (отрицательная - снижение); sect - 'ZZ' без ОКЭД.
BASE = f"""
ppl as (
    select p_rnn, m, knp, cnt_pers, sm, zp,
           min(m) over (partition by p_rnn) min_mes
      from (select /*+ parallel(8) */
                   s.p_rnn, s.pay_month m, s.knp,
                   count(distinct s.sicid) cnt_pers,
                   sum(s.sum_pay)          sm,
                   avg(s.cnt_mzp * s.mzp)  zp
              from si_member_2 s
             where s.pay_month >= trunc(:d_from, 'mm')
               and s.pay_month <  :d_to
               and s.pay_date  >  add_months(trunc(:d_from, 'mm'), -7)
             group by s.knp, s.p_rnn, s.pay_month)
),
pay as (
    select p_rnn,
           max(case when m = trunc(:d_from, 'mm') then cnt_pers end)    cnt04,
           max(case when m = trunc(:d_from, 'mm') then zp end)          zp04,
           max(case when m = trunc(:d_from, 'mm') then sm end)          sm04,
           nvl(max(case when m = trunc(:d_to - 1, 'mm') then cnt_pers end), 0) cnt05,
           nvl(max(case when m = trunc(:d_to - 1, 'mm') then zp end), 0)       zp05,
           nvl(max(case when m = trunc(:d_to - 1, 'mm') then sm end), 0)       sm05
      from ppl
     where knp = '012'
       and min_mes = trunc(:d_from, 'mm')
     group by p_rnn
    having max(case when m = trunc(:d_from, 'mm') then cnt_pers end) >= {MIN_STAFF}
),
calc as (
    select p.p_rnn,
           o.nm_ru                                              nm,
           p.cnt04, round(p.zp04, 2) zp04, p.sm04,
           p.cnt05, round(p.zp05, 2) zp05, p.sm05,
           p.cnt05 - p.cnt04                                    razn,
           round(100 - p.cnt05 / p.cnt04 * 100, 2)              perc,
           {_SECT_CASE}                                         sect,
           substr(cb.rfbn_id, 1, 2)                             obl,
           cb.rfbn_id                                           rc
      from pay p, rfon_organization o, cato_branch cb
     where p.p_rnn = o.bin
       and o.cato = cb.code
)"""

# Название области: запись КАТО XX00 с теми же первыми двумя знаками.
# Присоединяется к агрегату с колонкой obl: `from agg a, cato_branch b where {OBL_JOIN}`.
OBL_JOIN = ("substr(b.rfbn_id, 1, 2) = a.obl\n"
            "   and substr(b.rfbn_id, 3, 2) = '00'")
