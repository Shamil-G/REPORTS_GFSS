# -*- coding: utf-8 -*-
"""Контроль доступа к отчётам: признаки пользователя против ключа `access`.

Доступ описывается только признаками, которые приходят из SSO
(`sso/sso_login.py`): `roles`, `post`, `ou_name`, `rfbn_id`. В реестре
`dict_reports` группа или отчёт несёт такой же набор признаков в ключе
`access`:

    "access": {"roles": ["*"], "rfbn_id": "*"}   # всем
    "access": {"rfbn_id": "0000"}                # только центральный аппарат
    "access": {"ou_name": "DITiTO"}              # только ДИТиТО
    "access": {"post": ["*"], "ou_name": "DAUS"} # любая должность ДАУС
    "access": {"rfbn_id": "own"}                 # любой филиал, разрез - свой

Правила: несколько признаков - И, значения внутри признака - ИЛИ, `"*"`
равносилен отсутствию признака. Группа без ключа `access` получает
`DEFAULT_ACCESS`, то есть остаётся там, где была до филиалов - в центральном
аппарате: иначе в день первого входа филиала ему достался бы весь каталог.

`"rfbn_id": "own"` видимость не ограничивает - отчёт виден сотруднику любого
филиала, - но область ему подставляет сервер (`forced_rfbn`), а не выбирает он
сам в форме. Область пользователя при этом обязана быть известна.

Код области в признаке `rfbn_id` четырёхзначный ("0000" - центр, "0100" -
Акмола), и **область - это первые два знака**: так его отдаёт SSO, так устроен
`regions.py`. В реестре отчётов те же области двузначные ("01", см.
`LIST_REGION` в `model/list_reports.py`). Поэтому обе стороны сравнения
приводятся к первым двум знакам, и в `access` можно писать и `"0100"`, и
`"01"` - разницы нет.

У параметра отчёта `rfbn_id` пустое значение значит "вся республика", поэтому
центральному аппарату `forced_rfbn` отдаёт пусто.

Пустой `rfbn_id` у пользователя - это не центр, а "неизвестно": такой
пользователь не проходит ни один фильтр по области.
"""

# Признаки, по которым разрешён отбор. Ключ `access`, которого здесь нет,
# закрывает группу всем: опечатка в реестре не должна открывать доступ шире,
# а так она видна на первой же попытке.
FEATURES = ('roles', 'post', 'ou_name', 'rfbn_id')

ANY = '*'
OWN = 'own'
CENTRAL_REGION = '00'

# Группы без ключа `access`: только центральный аппарат (см. ACCESS-PLAN.md).
DEFAULT_ACCESS = {'rfbn_id': '0000'}

# Имя подразделения сравниваем без учёта регистра, должность и роль - как пришли.
_NOCASE = ('ou_name',)


def current_user():
    """Пользователь текущего запроса (`g.user`); вне запроса - None."""
    try:
        from flask import g
        return getattr(g, 'user', None)
    except Exception:
        return None


def _values(raw) -> list:
    """Значение признака - строка или список; пустые отбрасываем."""
    items = raw if isinstance(raw, (list, tuple, set)) else [raw]
    return [str(v).strip() for v in items if str(v).strip()]


def _region(value) -> str:
    """Код области - первые два знака кода отделения ("0100" -> "01")."""
    return str(value or '').strip()[:2]


def _user_values(user, feature: str) -> list:
    if feature == 'roles':
        return _values(list(getattr(user, 'roles', None) or []))
    return _values(getattr(user, feature, ''))


def effective_access(group: dict, report: dict = None) -> dict:
    """Какой `access` действует: у отчёта, иначе у группы, иначе по умолчанию.

    Пустой словарь (`"access": {}`) - сознательное "всем", он не подменяется
    на DEFAULT_ACCESS.
    """
    if report is not None and 'access' in report:
        return report['access'] or {}
    if 'access' in group:
        return group['access'] or {}
    return DEFAULT_ACCESS


def allowed(user, access: dict) -> bool:
    """Проходит ли пользователь фильтр `access`."""
    if set(access) - set(FEATURES):
        return False
    for feature in FEATURES:
        if feature not in access:
            continue
        wanted = _values(access[feature])
        if not wanted or ANY in wanted:
            continue
        if feature == 'rfbn_id':
            mine = _user_values(user, 'rfbn_id')
            if OWN in wanted:
                # own - разрез данных, а не фильтр видимости; но область должна
                # быть известна, иначе подставлять в отчёт нечего.
                if not mine:
                    return False
                continue
            # Область - первые два знака с обеих сторон: в access можно писать
            # и "0100", и "01".
            if not mine or _region(mine[0]) not in {_region(v) for v in wanted}:
                return False
            continue
        mine = _user_values(user, feature)
        if feature in _NOCASE:
            wanted = [v.lower() for v in wanted]
            mine = [v.lower() for v in mine]
        if not set(wanted) & set(mine):
            return False
    return True


def is_central(rfbn_id) -> bool:
    return _region(rfbn_id) == CENTRAL_REGION


def forced_rfbn(user, access: dict):
    """Область, которую сервер обязан подставить в параметры отчёта при `own`.

    Филиал получает двузначный код своей области. `None` значит "подставлять
    нечего, выбор за пользователем": так у центрального аппарата (он работает
    по всей республике и область выбирает сам, как сейчас), у `access` без
    `own` и у пользователя с неизвестной областью.
    """
    if OWN not in _values(access.get('rfbn_id', '')):
        return None
    mine = _user_values(user, 'rfbn_id')
    if not mine or is_central(mine[0]):
        return None
    return _region(mine[0])
