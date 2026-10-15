# -*- coding: utf-8 -*-
"""Проверка ИИН в Active Directory (контроль доступа к отчётам по человеку).

ИИН сотрудника лежит в атрибуте `telephoneNumber` (так же его читает SSO,
GO-SSO/storage/ldap/birthdate.go). Ищем точное совпадение во всём дереве
`dc=gfss,dc=kz` служебной учёткой из `app_config`. Сотрудники из
подразделений `ldap_ignore_ou` (UVOLEN - уволенные) не считаются: в этом
случае ИИН «в AD нет».

`iin_in_ad(iin)` -> True, если есть действующий сотрудник с этим ИИН.
Любая ошибка связи или ответа сервера - `AdUnavailable`: решение о доступе
по неполным данным не принимается (вызывающий отказывает в отчёте).
"""
import re

from ldap3 import Server, Connection, SUBTREE
from ldap3.utils.conv import escape_filter_chars

from app_config import ldap_server, ldap_user, ldap_password, ldap_ignore_ou
from util.logger import log

BASE_DN = 'dc=gfss,dc=kz'
CONNECT_TIMEOUT = 5
RECEIVE_TIMEOUT = 10


class AdUnavailable(Exception):
    """Active Directory не ответил или ответил ошибкой."""


def _dismissed(dn: str) -> bool:
    """В DN есть подразделение из списка уволенных (в любом звене пути)."""
    ous = {m.upper() for m in re.findall(r'(?i)(?:^|,)\s*OU=([^,]+)', dn or '')}
    return any(x.upper() in ous for x in ldap_ignore_ou)


def iin_in_ad(iin: str) -> bool:
    iin = str(iin or '').strip()
    if not re.fullmatch(r'\d{12}', iin):
        raise ValueError('Неверно указан ИИН!')
    conn = None
    try:
        server = Server(ldap_server, connect_timeout=CONNECT_TIMEOUT)
        conn = Connection(server, user=ldap_user, password=ldap_password,
                          auto_bind=True, receive_timeout=RECEIVE_TIMEOUT,
                          raise_exceptions=True)
        conn.search(search_base=BASE_DN,
                    search_filter=f'(&(objectClass=person)(telephoneNumber={escape_filter_chars(iin)}))',
                    search_scope=SUBTREE, attributes=['distinguishedName'],
                    size_limit=20)
        dns = [str(e.entry_dn) for e in conn.entries]
    except Exception as e:
        log.exception('AD CHECK. Ошибка запроса к Active Directory')
        raise AdUnavailable(str(e)) from e
    finally:
        if conn is not None:
            try:
                conn.unbind()
            except Exception:
                pass
    active = [dn for dn in dns if not _dismissed(dn)]
    log.info(f'AD CHECK. записей: {len(dns)}, действующих: {len(active)}')
    return bool(active)
