# -*- coding: utf-8 -*-
"""Журнал доступа к отчётам с персональными данными.

Каждое обращение к отчёту, помеченному в `list_reports.py` признаком
`"audit": True` (сейчас 6-1 и 6-2 «Обороты и назначения»), записывается в
таблицу `log_reports` схемы SSWH процедурой `util.log_reports` (автономная
транзакция, commit внутри): время, объект `REPORT_ACCESS`, событие и код отчёта
в `ACTION` (до 256 знаков), в `INFO` - пользователь SSO, IP, параметры и
сообщение (до 4000 знаков).

События: ЗАПРОС (до всякой проверки, с введённым ИИН), ВЫДАН, ОТКАЗ (в том
числе «не найден», «доступ запрещён», неверный ИИН), ОШИБКА.

Запись обязательна: если журнал недоступен, отчёт не формируется
(`AuditError`). Дополнительно строка идёт в общий лог приложения с префиксом
`AUDIT`.
"""
from db.connect import get_connection, LOADER_PROFILE
from util.logger import log

AUDIT_OBJECT = 'REPORT_ACCESS'


class AuditError(Exception):
    """Не удалось записать в журнал доступа."""


def current_user():
    try:
        from flask import session
        return session.get('username') or '?'
    except Exception:
        return '?'


def current_ip():
    try:
        from util.ip_addr import ip_addr
        return ip_addr() or '?'
    except Exception:
        return '?'


def write(event, code, details='', user=None, ip=None):
    """Записать событие. Бросает AuditError, если запись не удалась."""
    user = user if user is not None else current_user()
    ip = ip if ip is not None else current_ip()
    action = f'{event} {code}'[:256]
    info = f'user={user}; ip={ip}; {details}'[:4000]
    log.info(f'AUDIT. {action}. {info}')
    try:
        with get_connection(LOADER_PROFILE) as conn:
            with conn.cursor() as cur:
                cur.callproc('util.log_reports', [AUDIT_OBJECT, action, info])
    except Exception as e:
        log.exception('AUDIT. Не удалось записать в журнал доступа')
        raise AuditError(str(e)) from e
