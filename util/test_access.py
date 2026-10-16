# -*- coding: utf-8 -*-
"""Тесты контроля доступа. Запуск: python -m pytest util/test_access.py -q"""
import pytest

from util.access import (DEFAULT_ACCESS, allowed, effective_access,
                         forced_rfbn, is_central, payments_allowed)


class User:
    """Признаки пользователя так, как их выставляет SSO_User.init_user."""
    def __init__(self, roles=('User',), post='', ou_name='', rfbn_id=''):
        self.roles = set(roles)
        self.post = post
        self.ou_name = ou_name
        self.rfbn_id = rfbn_id


# Ответ SSO на живой учётке (см. ACCESS-PLAN.md): центральный аппарат, ДИТиТО.
# Роль у него Admin, но сами фильтры проверяются на обычном пользователе:
# Admin проходит любой из них.
ADMIN = User(roles=('Admin',), post='Главный разработчик',
             ou_name='DITiTO', rfbn_id='0000')
CENTER = User(post='Главный разработчик', ou_name='DITiTO', rfbn_id='0000')
# Сотрудник филиала по Акмолинской области
AKMOLA = User(post='Главный специалист', ou_name='AKMOLA', rfbn_id='0100')
# Пользователь, которому SSO не отдал область
NOWHERE = User(post='Главный специалист', ou_name='DAUS', rfbn_id='')


@pytest.mark.parametrize('access, who, expected', [
    # примеры из плана
    ({'roles': ['*'], 'rfbn_id': '*'}, CENTER, True),
    ({'roles': ['*'], 'rfbn_id': '*'}, AKMOLA, True),
    ({'rfbn_id': '0000'}, CENTER, True),
    ({'rfbn_id': '0000'}, AKMOLA, False),
    ({'ou_name': 'DITiTO'}, CENTER, True),
    ({'ou_name': 'DITiTO'}, AKMOLA, False),
    ({'post': ['*'], 'ou_name': 'DITiTO'}, CENTER, True),
    # несколько признаков - И
    ({'ou_name': 'DITiTO', 'post': 'Директор'}, CENTER, False),
    ({'ou_name': 'DITiTO', 'roles': ['User']}, CENTER, True),
    # значения внутри признака - ИЛИ
    ({'rfbn_id': ['0100', '1500']}, AKMOLA, True),
    ({'rfbn_id': ['0200', '1500']}, AKMOLA, False),
    # область - первые два знака: в access можно писать и "0100", и "01"
    ({'rfbn_id': '01'}, AKMOLA, True),
    ({'rfbn_id': '00'}, CENTER, True),
    ({'rfbn_id': '00'}, AKMOLA, False),
    ({'rfbn_id': ['01', '15']}, AKMOLA, True),
    ({'rfbn_id': '0199'}, AKMOLA, True),
    # коды - без учёта регистра
    ({'ou_name': 'ditito'}, CENTER, True),
    # пустой access - всем
    ({}, AKMOLA, True),
    # неизвестный признак закрывает группу (опечатка вместо rfbn_id)
    ({'branch': '0000'}, CENTER, False),
])
def test_allowed(access, who, expected):
    assert allowed(who, access) is expected


def test_admin_passes_any_filter():
    """Администратор отчётности видит весь каталог."""
    assert allowed(ADMIN, {'ou_name': 'DAUiS'}) is True
    assert allowed(ADMIN, {'rfbn_id': '01'}) is True
    assert allowed(ADMIN, {'post': 'Директор', 'ou_name': 'DpRsP'}) is True
    # а вот опечатка в ключе закрывает группу и ему: иначе её никто не заметит
    assert allowed(ADMIN, {'branch': '0000'}) is False


def test_effective_access_dep_rule():
    """Раздел каталога - третий уровень, между группой и значением по умолчанию."""
    dep = {'ou_name': 'DAUiS'}
    plain_group = {'live_time': 0}
    assert effective_access(plain_group, None, dep) == dep
    # группа со своим access раздел не наследует - её правило заменяет его целиком
    assert effective_access({'access': {'rfbn_id': 'own'}}, None, dep) == {'rfbn_id': 'own'}
    # отчёт важнее и группы, и раздела
    assert effective_access(plain_group, {'access': {}}, dep) == {}
    # раздела без access касается значение по умолчанию
    assert effective_access(plain_group, None, None) == DEFAULT_ACCESS


def test_default_access_leaves_reports_in_center():
    """Группа без ключа access остаётся там, где была до филиалов."""
    assert allowed(CENTER, DEFAULT_ACCESS) is True
    assert allowed(AKMOLA, DEFAULT_ACCESS) is False


def test_unknown_rfbn_passes_nothing():
    """Пустая область - это не центр, а 'неизвестно'."""
    assert allowed(NOWHERE, {'rfbn_id': '0000'}) is False
    assert allowed(NOWHERE, {'rfbn_id': 'own'}) is False
    assert allowed(NOWHERE, {'ou_name': 'DAUS'}) is True


def test_own_does_not_limit_visibility():
    """own - разрез данных: отчёт виден и центру, и любому филиалу."""
    assert allowed(CENTER, {'rfbn_id': 'own'}) is True
    assert allowed(AKMOLA, {'rfbn_id': 'own'}) is True


@pytest.mark.parametrize('who, expected', [
    (CENTER, None),    # центр работает по всей республике и выбирает сам
    (AKMOLA, '01'),    # филиалу 4 знака признака -> 2 знака параметра отчёта
    (NOWHERE, None),   # область неизвестна - подставлять нечего
])
def test_forced_rfbn(who, expected):
    assert forced_rfbn(who, {'rfbn_id': 'own'}) == expected


def test_forced_rfbn_only_for_own():
    assert forced_rfbn(AKMOLA, {'rfbn_id': '0100'}) is None
    assert forced_rfbn(AKMOLA, {}) is None


def test_effective_access():
    group = {'access': {'ou_name': 'DAUS'}}
    report = {'access': {'rfbn_id': 'own'}}
    # у отчёта приоритет над группой
    assert effective_access(group, report) == {'rfbn_id': 'own'}
    assert effective_access(group, {'name': 'без access'}) == {'ou_name': 'DAUS'}
    # ни у отчёта, ни у группы - значение по умолчанию
    assert effective_access({'live_time': 0}) == DEFAULT_ACCESS
    # пустой access - сознательное "всем", не подменяется
    assert effective_access({'access': {}}) == {}


def test_is_central():
    assert is_central('0000') and is_central(' 0000 ') and is_central('00')
    assert not is_central('0100') and not is_central('')


def test_payments_allowed():
    dauis = User(post='Ведущий специалист', ou_name='DAUiS', rfbn_id='0000')
    assert payments_allowed(ADMIN)
    assert payments_allowed(dauis)
    assert not payments_allowed(CENTER)      # ДИТиТО без роли Admin
    assert not payments_allowed(AKMOLA)
    assert not payments_allowed(User(ou_name='DAUiS', rfbn_id='0100'))
    assert not payments_allowed(User(ou_name='DAUiS', rfbn_id=''))
