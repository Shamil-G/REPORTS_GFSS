"""model/payment_card.py - поиск получателя в LOADER.PERSON (вкладка «Карточка»)."""
import re
from datetime import datetime, timedelta
from decimal import Decimal

from db.connect import get_connection
from util.access import is_admin
from util.ad_check import iin_in_ad, AdUnavailable

# Список короткий: для каждой строки без роли Admin проверяется AD (см. _hide_employees)
LIMIT = 100

# ключ в JSON -> колонка PERSON (ключи - имена колонок в нижнем регистре, их же ждёт data-f в card_panel.html)
COLUMNS = {
    'sicid': 'SICID',
    'iin': 'IIN',
    'lastname': 'LASTNAME',
    'firstname': 'FIRSTNAME',
    'middlename': 'MIDDLENAME',
    'birthdate': 'BIRTHDATE',
    'rnn': 'RNN',
    'regdate': 'REGDATE',
    'birthplace': 'BIRTHPLACE',
    'address': 'ADDRESS',
    'branchid': 'BRANCHID',
    'doctype': 'DOCTYPE',
    'rlastname': 'RLASTNAME',
    'rfirstname': 'RFIRSTNAME',
    'rmiddlename': 'RMIDDLENAME',
    'workplace': 'WORKPLACE',
    'rbranchid': 'RBRANCHID',
}
DATE_KEYS = ('birthdate', 'regdate')

# Та же подмена символов CP1251, что и в model/payment_search.py (на нормальных данных не мешает)
KZ_FIX = str.maketrans('ЈЄЌЅҐЎЇЋјєќѕґўїћ', 'ӘҒҚҢӨҰҮҺәғқңөұүһ')


def fix_kz(text):
    return text.translate(KZ_FIX)


def _prefix(value):
    """Шаблон «начинается с»: без ведущего %, чтобы работал индекс. % и _ из ввода экранируем."""
    escaped = value.strip().upper().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    return escaped + '%'


def build_query(filters):
    where, params = [], {}

    iin = filters.get('iin', '').strip()
    lastname = filters.get('lastname', '').strip()
    firstname = filters.get('firstname', '').strip()
    middlename = filters.get('middlename', '').strip()
    birthdate = filters.get('birthdate', '').strip()

    if not iin and not lastname:
        raise ValueError('Укажите ИИН или фамилию.')

    if iin:
        if not re.fullmatch(r'[0-9]{12}', iin):
            raise ValueError('ИИН должен содержать 12 цифр.')
        # данные сотрудников не выдаются, кроме роли Admin (как и в поиске платежей по ИИН)
        if not is_admin():
            try:
                if iin_in_ad(iin):
                    raise ValueError('Доступ запрещен!')
            except AdUnavailable:
                raise ValueError('Не удалось проверить данные в Active Directory. Попробуйте позже.') from None
        where.append('IIN = :iin')
        params['iin'] = iin

    for key, value in (('lastname', lastname), ('firstname', firstname), ('middlename', middlename)):
        if value:
            if len(value) > 60:
                raise ValueError('Слишком длинное значение в ФИО.')
            # значения в PERSON - заглавными; без UPPER() по колонке, чтобы работал индекс
            where.append(f"{COLUMNS[key]} LIKE :{key} ESCAPE '\\'")
            params[key] = _prefix(value)

    if birthdate:
        try:
            day = datetime.strptime(birthdate, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Некорректная дата рождения.') from None
        where += ['BIRTHDATE >= :birth_from', 'BIRTHDATE < :birth_to']
        params.update(birth_from=day, birth_to=day + timedelta(days=1))

    cols = ', '.join(COLUMNS.values())
    sql = (f'SELECT {cols}\nFROM LOADER.PERSON\nWHERE ' + '\n  AND '.join(where) +
           '\nORDER BY LASTNAME, FIRSTNAME, MIDDLENAME')
    # лишняя строка определяет усечение; сортировка - во внутреннем запросе, до ROWNUM
    sql = f'SELECT * FROM (\n{sql}\n)\nWHERE ROWNUM <= {LIMIT + 1}'
    return sql, params


def _hide_employees(items):
    """Без роли Admin сотрудников в списке не показываем (проверка по ИИН в AD)."""
    if is_admin():
        return items
    try:
        return [it for it in items if not (it['iin'] and iin_in_ad(it['iin']))]
    except AdUnavailable:
        raise ValueError('Не удалось проверить данные в Active Directory. Попробуйте позже.') from None


def search_card(filters):
    sql, params = build_query(filters)
    with get_connection() as connection:
        old_timeout = connection.call_timeout
        try:
            connection.call_timeout = 40000
            with connection.cursor() as cursor:
                cursor.arraysize = 100
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        finally:
            connection.call_timeout = old_timeout

    items = []
    for row in rows[:LIMIT]:
        item = {}
        for key, value in zip(COLUMNS, row):
            if hasattr(value, 'read'):
                value = value.read()
            if value is None:
                item[key] = ''
            elif key in DATE_KEYS:
                item[key] = value.strftime('%d.%m.%Y') if hasattr(value, 'strftime') else str(value)
            else:
                item[key] = fix_kz(str(value))
        # «ФИО при регистрации» собираем из трёх колонок
        item['regfio'] = ' '.join(x for x in (item['rlastname'], item['rfirstname'], item['rmiddlename']) if x)
        items.append(item)
    return {'items': _hide_employees(items), 'truncated': len(rows) > LIMIT, 'limit': LIMIT}


# ---------------------------------------------------------------------------
# «Информация участнику системы обязательного социального страхования»:
# платежи человека из SI_MEMBER_2 + реквизиты платёжного документа из PMPD_PAY_DOC
# ---------------------------------------------------------------------------
MEMBER_TABLE = 'LOADER.SI_MEMBER_2'  # если таблица в другой схеме - укажите 'SCHEMA.SI_MEMBER_2'
INFO_LIMIT = 3000
RECEIVER = 'Гос.фонд социального страхования'

TMST_STATUSES = {
    1: '1 — Поступил', 2: '2 — Брак', 4: '4 — Не рассчитанные', 5: '5 — Обработанные',
    6: '6 — Сторнированные', 7: '7 — Проведен сторн.', 8: '8 — Проведен', 9: '9 — Аннулирован',
    65: '65 — Провед. раздел.', 66: '66 — Сторн. разделен.', 101: '101 — Сформированные',
    102: '102 — Не доставленные', 103: '103 — Доставленные', 104: '104 — Возвращенные',
    105: '105 — Рабочий', 106: '106 — Аннулированные',
}

INFO_SQL = f"""SELECT * FROM (
    SELECT m.pay_date, m.pay_date_gfss, d.doc_nmb, d.doc_date, m.knp, d.p_name, m.p_rnn,
           d.pay_sum, m.sum_pay, d.tmst_id, m.period
    FROM {MEMBER_TABLE} m
    LEFT JOIN LOADER.PMPD_PAY_DOC d ON d.mhmh_id = m.mhmh_id
    WHERE m.sicid = :sicid
    ORDER BY m.pay_date DESC, m.period DESC
)
WHERE ROWNUM <= :lim"""


def _money(value):
    if value is None or value == '':
        return ''
    return format(Decimal(str(value)), ',.2f').replace(',', '\u00a0').replace('.', ',')


def _date(value):
    return value.strftime('%d.%m.%Y') if hasattr(value, 'strftime') else ('' if value is None else str(value))


def _text(value):
    if hasattr(value, 'read'):
        value = value.read()
    return '' if value is None else fix_kz(str(value))


def get_card_info(sicid):
    """Данные для таба «Информация участнику». None - человека нет в PERSON.
    PermissionError - человек является сотрудником (данные только для роли Admin)."""
    with get_connection() as connection:
        old_timeout = connection.call_timeout
        try:
            connection.call_timeout = 40000
            with connection.cursor() as cursor:
                cursor.execute('SELECT IIN, LASTNAME, FIRSTNAME, MIDDLENAME FROM LOADER.PERSON WHERE SICID = :sicid',
                               {'sicid': sicid})
                person = cursor.fetchone()
                if person is None:
                    return None
                iin = _text(person[0])
                # ИИН берём из БД, а не из запроса: проверка сотрудников не обходится подменой sicid
                if iin and not is_admin():
                    try:
                        if iin_in_ad(iin):
                            raise PermissionError('Доступ запрещен!')
                    except AdUnavailable:
                        raise ValueError('Не удалось проверить данные в Active Directory. Попробуйте позже.') from None
                cursor.arraysize = 200
                cursor.execute(INFO_SQL, {'sicid': sicid, 'lim': INFO_LIMIT + 1})
                rows = cursor.fetchall()
        finally:
            connection.call_timeout = old_timeout

    result, total = [], Decimal(0)
    for (pay_date, pay_date_gfss, doc_nmb, doc_date, knp, p_name, p_rnn,
         pay_sum, sum_pay, tmst_id, period) in rows[:INFO_LIMIT]:
        if sum_pay is not None:
            total += Decimal(str(sum_pay))
        result.append({
            'pay_date': _date(pay_date), 'pay_date_gfss': _date(pay_date_gfss),
            'doc_nmb': _text(doc_nmb), 'doc_date': _date(doc_date), 'knp': _text(knp),
            'p_name': _text(p_name), 'p_rnn': _text(p_rnn), 'receiver': RECEIVER,
            'pay_sum': _money(pay_sum), 'sum_pay': _money(sum_pay),
            'status': '' if tmst_id is None else TMST_STATUSES.get(int(tmst_id), str(tmst_id)),
            'period': _text(period),
        })
    return {
        'person': {'sicid': sicid, 'iin': iin, 'lastname': _text(person[1]),
                   'firstname': _text(person[2]), 'middlename': _text(person[3])},
        'rows': result, 'total': _money(total),
        'truncated': len(rows) > INFO_LIMIT, 'limit': INFO_LIMIT,
    }
