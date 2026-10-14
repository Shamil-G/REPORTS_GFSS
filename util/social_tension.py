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
организаций уже стоят все 20 текущих областей. Плательщик без КАТО, с КАТО,
которого нет в `cato_branch`, или вовсе без записи в `rfon_organization`
(иностранные организации, напр. РЖД) не теряется: он идёт в «Неизвестный
регион» (область `99`, район `9999`), наименование - «Неизвестная организация».
В оригинале такой плательщик попадал в отчёт 5006 (список из `nk_minfin_iin`).

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
import datetime

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


def period_on(on):
    """Период расчёта на дату `on`: (первый день, последний день).

    Как в оригинале (`set_date`): последний месяц - предпоследний к месяцу даты
    (до 28-го числа предыдущего месяца платят за позапрошлый), первый - на
    месяц раньше. Дата 14.10.2026 -> 01.07.2026 - 31.08.2026.
    """
    y, m = on.year, on.month - 2
    if m < 1:
        y, m = y - 1, m + 12
    last = (datetime.date(y + m // 12, m % 12 + 1, 1)
            - datetime.timedelta(days=1))
    fy, fm = (y, m - 1) if m > 1 else (y - 1, 12)
    return datetime.date(fy, fm, 1), last


def _date_on(params):
    on = params.get('date_on')
    return parse_date(on) if on else datetime.date.today()


def normalize_params(params):
    """Период и признак половины месяца вместо введённой даты.

    Пользователь вводит только «На дату» (или ничего). Здесь же период
    расчёта и признак half ('1' - до 14-го числа, источник si_member_2;
    '2' - с 14-го, документы pmpd_pay_doc_s / pmdl_doc_list_s) становятся
    обычными параметрами: журнал отчётов и список выполняющихся показывают
    даты «с» и «по», а имя файла содержит период и половину - расчёт за
    один период и одну половину месяца не пересчитывается заново.
    """
    on = _date_on(params)
    first, last = period_on(on)
    params = {k: v for k, v in params.items() if k != 'date_on'}
    params['date_first'] = f'{first:%Y-%m-%d}'
    params['date_second'] = f'{last:%Y-%m-%d}'
    params['half'] = '2' if on.day >= SECOND_HALF_DAY else '1'
    return params


def check_params(params):
    """Запуск без normalize_params (напрямую): период берётся из date_on."""
    if not params.get('date_first') or not params.get('date_second'):
        n = normalize_params(params)
        params['date_first'] = n['date_first']
        params['date_second'] = n['date_second']


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
# Секция ОКЭД считается только для отчётов, где она есть в разрезе или в
# колонках (5004, 5005, 5006): BASE; BASE_NO_SECT - для 5001-5003.
UNKNOWN_OBL = '99'
UNKNOWN_RC = '9999'
UNKNOWN_NAME = 'Неизвестный регион'


# Источник платежей (оригинал: `fill`, extract(day from sysdate) < 14):
# - до 14-го числа - `si_member_2`, таблица, которую раз в месяц считают заранее
#   (prepare_first); zp - cnt_mzp * mzp;
# - с 14-го числа - документы `pmpd_pay_doc_s` + `pmdl_doc_list_s`, на которых
#   строится `si_member_2` следующего месяца (prepare_second): КНП 012 и 017
#   (017 - пеня: месяц первого платежа плательщика, min_mes, учитывает и её),
#   месяц платежа - период документа (при пустом - месяц до даты платежа),
#   zp - сумма платежа / процент `min_perc(pay_month)`.
SECOND_HALF_DAY = 14

_SRC_FIRST = """from si_member_2 s
             where s.pay_month >= trunc(:d_from, 'mm')
               and s.pay_month <  :d_to
               and s.pay_date  >  add_months(trunc(:d_from, 'mm'), -7)"""

_SRC_SECOND = """from (select pd.p_rnn,
                   tlsd.to_date_def(nvl(dl.period, pd.period), 'mmyyyy',
                                    add_months(trunc(pd.pay_date, 'month'), -1)) pay_month,
                   dl.sicid,
                   dl.pay_sum         sum_pay,
                   pd.cipher_id_knp   knp
              from pmpd_pay_doc_s pd, pmdl_doc_list_s dl
             where pd.cipher_id_knp in ('012', '017')
               and dl.rfem_id is null
               and pd.tmst_id = 5
               and pd.mhmh_id = dl.mhmh_id
               and pd.pay_date = dl.pay_date
               and pd.pay_date > add_months(trunc(:d_from, 'mm'), -7)) s
             where s.pay_month >= trunc(:d_from, 'mm')
               and s.pay_month <  :d_to"""


def second_half(params):
    """Вторая половина месяца: признак half = '2', а без него (запуск напрямую)
    день даты «на дату» (пусто - сегодня) >= 14."""
    if params.get('half'):
        return str(params['half']) == '2'
    return _date_on(params).day >= SECOND_HALF_DAY


def base_for(params, with_sect):
    """Общая часть запроса; источник платежей - по дню месяца (см. выше)."""
    return _base(with_sect, second_half(params))


def _base(with_sect, second=False):
    sect_col = (f"           {_SECT_CASE}                                         sect,\n"
                if with_sect else '')
    src = _SRC_SECOND if second else _SRC_FIRST
    zp = ('s.sum_pay * 100 / min_perc(s.pay_month)' if second
          else 's.cnt_mzp * s.mzp')
    return f"""
ppl as (
    select p_rnn, m, knp, cnt_pers, sm, zp,
           min(m) over (partition by p_rnn) min_mes
      from (select /*+ parallel(8) */
                   s.p_rnn, s.pay_month m, s.knp,
                   count(distinct s.sicid) cnt_pers,
                   sum(s.sum_pay)          sm,
                   avg({zp})  zp
              {src}
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
           nvl(o.nm_ru, 'Неизвестная организация')              nm,
           p.cnt04, round(p.zp04, 2) zp04, p.sm04,
           p.cnt05, round(p.zp05, 2) zp05, p.sm05,
           p.cnt05 - p.cnt04                                    razn,
           round(100 - p.cnt05 / p.cnt04 * 100, 2)              perc,
{sect_col}           nvl(substr(cb.rfbn_id, 1, 2), '{UNKNOWN_OBL}')       obl,
           nvl(cb.rfbn_id, '{UNKNOWN_RC}')                      rc
      from pay p, rfon_organization o, cato_branch cb
     where o.bin(+) = p.p_rnn
       and cb.code(+) = o.cato
)"""


BASE = _base(True)
BASE_NO_SECT = _base(False)

# Название области: запись КАТО XX00 с теми же первыми двумя знаками.
# Присоединяется к агрегату с колонкой obl: `from agg a, branch b where {OBL_JOIN}`;
# название - `b.name` (в `cato_branch.name_ru` у новых областей казахские формы с
# утраченными буквами: «ОБЛАСТЬ ?ЛЫТАУ»).
OBL_JOIN = "b.rfbn_id(+) = a.obl || '00'"
OBL_NAME = f"nvl(b.name, '{UNKNOWN_NAME}')"
