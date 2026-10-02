# -*- coding: utf-8 -*-
"""Границы отчётного периода. Порт REP_STAT_EXTEND.SetDateBound.

Интервал полуоткрытый: [d_from, d_to), верхняя граница исключительная.
В SQL отчётов всегда `>= :d_from and < :d_to` - форма `between d_from and d_to`
не даёт Oracle использовать индекс по дате и в переносимых отчётах заменяется.

Одна эта функция заменяет ~135 процедур-обёрток app_NN_1m / _2k / _3hy /
_4_9m / _5y: в PL/SQL тип периода был зашит в имя процедуры, здесь это параметр.
"""
from datetime import date, timedelta

# Нумерацию менять нельзя: она зашита в параметры запуска у пользователей.
PERIOD_NAMES = {
    1: 'месяц',
    2: 'квартал',
    3: 'полугодие',
    4: '9 месяцев',
    5: 'год',
    6: '24 месяца',
    7: 'месяцев',
}

_LIMITS = {1: 12, 2: 4, 3: 2, 6: 4, 7: 12}   # допустимый date_start по типу
_STEP = {1: 1, 2: 3, 3: 6}                   # длина периода в месяцах

_MONTHS_RU = ('январь', 'февраль', 'март', 'апрель', 'май', 'июнь',
              'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь')
_ROMAN = ('I', 'II', 'III', 'IV')

STD_TYPES = (1, 2, 3, 4, 5)      # набор периодов, доступный обычному отчёту


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    return date(d.year + m // 12, m % 12 + 1, 1)


def period_bounds(rep_year, date_type, date_start=None):
    """Год + тип периода + номер -> (d_from, d_to), d_to исключительная."""
    y, t = int(rep_year), int(date_type)
    s = int(date_start) if date_start not in (None, '') else 0

    if not 2005 <= y <= date.today().year:
        raise ValueError(f'Неправильное значение года: {rep_year}')
    if t not in PERIOD_NAMES:
        raise ValueError(f'Неправильный тип периода: {date_type}')
    if t in _LIMITS and not 1 <= s <= _LIMITS[t]:
        raise ValueError(f'Неправильный номер периода: {date_start} '
                         f'(тип {t}, допустимо 1..{_LIMITS[t]})')

    jan = date(y, 1, 1)
    if t in _STEP:
        d_from = _add_months(jan, (s - 1) * _STEP[t])
        return d_from, _add_months(d_from, _STEP[t])
    if t == 4:
        return jan, _add_months(jan, 9)
    if t == 5:
        return jan, _add_months(jan, 12)
    if t == 6:
        d_from = _add_months(jan, 3 * s - 24)
        return d_from, _add_months(d_from, 24)
    return jan, _add_months(jan, s)          # t == 7


def year_start(rep_year) -> date:
    """Начало года для колонок «с начала года». В PL/SQL: trunc(p_DatE,'YEAR')."""
    return date(int(rep_year), 1, 1)


def last_day(d_to: date) -> date:
    """Последний день периода - только для показа в шапке, не для SQL."""
    return d_to - timedelta(days=1)


def period_choices(types=STD_TYPES) -> dict:
    """Готовый список конкретных периодов для выпадающего списка формы.

    Ключ - "<тип>.<номер>", то есть сразу пара аргументов period_bounds().
    Два поля ("тип периода" и отдельно "номер периода") пользователю показывать
    нельзя: номер сам по себе ничего не значит и читается как загадка.
    """
    out = {}
    for t in types:
        if t == 1:
            out.update({f'1.{m}': _MONTHS_RU[m - 1] for m in range(1, 13)})
        elif t == 2:
            out.update({f'2.{q}': f'{_ROMAN[q - 1]} квартал' for q in range(1, 5)})
        elif t == 3:
            out.update({f'3.{h}': f'{h} полугодие' for h in (1, 2)})
        elif t == 4:
            out['4.0'] = '9 месяцев'
        elif t == 5:
            out['5.0'] = 'год'
        elif t == 6:
            out.update({f'6.{q}': f'24 месяца по {_ROMAN[q - 1]} квартал включительно'
                        for q in range(1, 5)})
        elif t == 7:
            out.update({f'7.{m}': f'с начала года по {_MONTHS_RU[m - 1]}'
                        for m in range(1, 13)})
    return out


_ALL_CHOICES = period_choices(tuple(PERIOD_NAMES))


def split_period(value):
    """"2.3" -> (2, 3). Разбор значения из выпадающего списка формы."""
    t, _, s = str(value).partition('.')
    return int(t), int(s or 0)


def period_name(date_type, date_start=None) -> str:
    """Короткое имя периода без года: "сентябрь", "II квартал", "год"."""
    t = int(date_type)
    s = int(date_start) if date_start not in (None, '') else 0
    name = _ALL_CHOICES.get(f'{t}.{s}')
    if name is None:
        raise ValueError(f'Неправильный период: тип {date_type}, номер {date_start}')
    return name


# Предложный падеж для подзаголовков вида "в отчетном ...".
# В PL/SQL стояло жёсткое "в отчетном месяце" - других периодов у отчётов
# не было. Раз периоды теперь любые, слово согласуется с выбранным.
_PERIOD_WORD = {1: 'месяце', 2: 'квартале', 3: 'полугодии',
                4: 'периоде', 5: 'году', 6: 'периоде', 7: 'периоде'}


def period_word(date_type) -> str:
    """Слово для подзаголовка "в отчетном ...": месяце, квартале, году."""
    return _PERIOD_WORD[int(date_type)]


# Формулировка подписи периода у каждого отчёта своя: у приложения 32 это
# "Август месяц 2026 года", у 52-го - ", за Август2026 года" (пробела перед
# годом в оригинале нет). Тексты официальной отчётности согласованы, поэтому
# шаблоны задаются в самом отчёте и копируются из исходника дословно.
# Здесь - формулировки приложения 32, они же значения по умолчанию.
PERIOD_LABEL_DEFAULT = {
    1: '{Month} месяц {year} года',
    2: '{roman} квартал {year} года',
    3: '{n} полугодие {year} года',
    4: '9 месяцев {year} года',
    5: '{year} год',
    6: '24 месяца по {roman} квартал {year} года',
    7: 'с начала года по {month} {year} года',
}


def make_period_label(overrides=None):
    """Возвращает функцию подписи периода по шаблонам отчёта.

    Подстановки: {year} - 2026, {month} - август, {Month} - Август,
    {n} - номер периода цифрой, {roman} - I..IV.
    overrides перекрывает нужные типы периода, остальные берутся по умолчанию.
    """
    tpl = {**PERIOD_LABEL_DEFAULT, **(overrides or {})}

    def label(rep_year, date_type, date_start=None) -> str:
        y, t = int(rep_year), int(date_type)
        s = int(date_start) if date_start not in (None, '') else 0
        if t not in tpl:
            raise ValueError(f'Нет шаблона подписи для типа периода {date_type}')
        month = _MONTHS_RU[s - 1] if 1 <= s <= 12 else ''
        return tpl[t].format(year=y, n=s, month=month,
                             Month=month.capitalize(),
                             roman=_ROMAN[s - 1] if 1 <= s <= 4 else '')
    return label


period_label = make_period_label()


def dates_label(rep_year, date_type, date_start=None) -> str:
    """"01.09.2026 по 30.09.2026" - для отчётов, где в оригинале период
    печатался парой дат (с первого по последний день), а не словами.
    Последний день - включительно, d_to в SQL при этом исключительная."""
    d_from, d_to = period_bounds(rep_year, date_type, date_start)
    return f'{d_from:%d.%m.%Y} по {last_day(d_to):%d.%m.%Y}'


def first_date_label(rep_year, date_type, date_start=None) -> str:
    """"01.09.2026" - первое число периода: так печатался параметр-дата
    в названиях старых отчётов (`... за ' || pdate || ' г.'`)."""
    d_from, _ = period_bounds(rep_year, date_type, date_start)
    return f'{d_from:%d.%m.%Y}'
