"""model/payment_card.py - поиск получателя в LOADER.PERSON (вкладка «Карточка»)."""
import re
from datetime import datetime, timedelta

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
