# -*- coding: utf-8 -*-
"""Тесты границ периода. Запуск: python -m pytest util/test_period.py -q"""
from datetime import date

import pytest

from util.period import (period_bounds, period_choices, period_label,
                         last_day, split_period, year_start)


@pytest.mark.parametrize('date_type, date_start, expected', [
    # месяц
    (1, 1,  (date(2026, 1, 1), date(2026, 2, 1))),
    (1, 2,  (date(2026, 2, 1), date(2026, 3, 1))),   # февраль невисокосного
    (1, 12, (date(2026, 12, 1), date(2027, 1, 1))),  # переход через год
    # квартал
    (2, 1, (date(2026, 1, 1), date(2026, 4, 1))),
    (2, 2, (date(2026, 4, 1), date(2026, 7, 1))),
    (2, 4, (date(2026, 10, 1), date(2027, 1, 1))),
    # полугодие
    (3, 1, (date(2026, 1, 1), date(2026, 7, 1))),
    (3, 2, (date(2026, 7, 1), date(2027, 1, 1))),
    # 9 месяцев, год
    (4, None, (date(2026, 1, 1), date(2026, 10, 1))),
    (5, None, (date(2026, 1, 1), date(2027, 1, 1))),
    # 24 месяца
    (6, 1, (date(2024, 4, 1), date(2026, 4, 1))),
    (6, 4, (date(2025, 1, 1), date(2027, 1, 1))),
    # произвольное число месяцев с начала года
    (7, 1, (date(2026, 1, 1), date(2026, 2, 1))),
    (7, 5, (date(2026, 1, 1), date(2026, 6, 1))),
    (7, 12, (date(2026, 1, 1), date(2027, 1, 1))),
])
def test_bounds(date_type, date_start, expected):
    assert period_bounds(2026, date_type, date_start) == expected


def test_leap_february():
    # d_to исключительная, поэтому високосность видна через last_day
    d_from, d_to = period_bounds(2024, 1, 2)
    assert (d_from, last_day(d_to)) == (date(2024, 2, 1), date(2024, 2, 29))


def test_half_open_no_gaps_no_overlaps():
    """Кварталы года стыкуются встык и покрывают год целиком."""
    edges = [period_bounds(2026, 2, q) for q in range(1, 5)]
    for (_, prev_to), (next_from, _) in zip(edges, edges[1:]):
        assert prev_to == next_from
    assert (edges[0][0], edges[-1][1]) == period_bounds(2026, 5, None)


def test_year_start_matches_type_5():
    assert year_start(2026) == period_bounds(2026, 5, None)[0]


@pytest.mark.parametrize('rep_year, date_type, date_start', [
    (2004, 1, 1),        # год раньше 2005
    (2999, 1, 1),        # год из будущего
    (2026, 0, 1),        # неизвестный тип
    (2026, 8, 1),        # неизвестный тип
    (2026, 1, 0),        # месяц вне 1..12
    (2026, 1, 13),
    (2026, 2, 5),        # квартал вне 1..4
    (2026, 3, 3),        # полугодие вне 1..2
    (2026, 6, 5),        # 24 месяца вне 1..4
    (2026, 7, 13),
    (2026, 1, None),     # номер обязателен для типа 1
])
def test_rejects_bad_params(rep_year, date_type, date_start):
    with pytest.raises(ValueError):
        period_bounds(rep_year, date_type, date_start)


@pytest.mark.parametrize('date_type, date_start', [(4, None), (5, None)])
def test_date_start_ignored_for_year_types(date_type, date_start):
    """Для типов 4 и 5 номера периода нет: лишний аргумент не мешает."""
    assert (period_bounds(2026, date_type, date_start)
            == period_bounds(2026, date_type, 3))


@pytest.mark.parametrize('date_type, date_start, expected', [
    (1, 3, 'март 2026 года'),
    (2, 2, 'II квартал 2026 года'),
    (3, 1, '1 полугодие 2026 года'),
    (4, None, '9 месяцев 2026 года'),
    (5, None, '2026 год'),
    (7, 5, 'с начала года по май 2026 года'),
])
def test_label(date_type, date_start, expected):
    assert period_label(2026, date_type, date_start) == expected


def test_choices_default_set():
    """Обычному отчёту предлагаются 12 месяцев, 4 квартала, 2 полугодия, 9 мес и год."""
    ch = period_choices()
    assert len(ch) == 12 + 4 + 2 + 1 + 1
    assert ch['1.3'] == 'март' and ch['2.2'] == 'II квартал' and ch['5.0'] == 'год'


@pytest.mark.parametrize('value, expected', [
    ('1.3', (1, 3)), ('2.2', (2, 2)), ('5.0', (5, 0)), ('4.0', (4, 0)),
])
def test_split_period(value, expected):
    assert split_period(value) == expected


def test_every_choice_resolves():
    """Любой пункт списка формы должен давать корректный период и подпись."""
    for value in period_choices((1, 2, 3, 4, 5, 6, 7)):
        d_type, d_start = split_period(value)
        d_from, d_to = period_bounds(2026, d_type, d_start)
        assert d_from < d_to
        assert period_label(2026, d_type, d_start)
