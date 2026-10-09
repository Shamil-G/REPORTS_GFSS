"""Поиск платежей напрямую в PMPD_PAY_DOC."""
import re
from datetime import datetime, timedelta
from decimal import Decimal

from db.connect import get_connection

LIMIT = 3000
COLUMNS = (
    'pay_date', 'doc_date', 'doc_nmb', 'refer', 'cipher_id_knp',
    'pay_sum', 'doc_err', 'tmst_id', 'p_name', 'p_rnn',
    'rfbk_mfo_pbank', 'p_account', 'r_name', 'r_rnn',
    'rfbk_mfo_rbank', 'r_account', 'doc_assign',
)


def build_query(filters):
    where, params = [], {}
    reference = filters.get('reference', '').strip()
    date_from = filters.get('dateFrom', '').strip()
    date_to = filters.get('dateTo', '').strip()
    date_type = filters.get('dateType', 'processedDate')
    if date_type not in ('processedDate', 'paymentDate'):
        raise ValueError('Выберите дату платежа или дату обработки.')
    if not reference and (not date_from or not date_to):
        raise ValueError('Укажите обе даты периода или референс.')
    if bool(date_from) != bool(date_to):
        raise ValueError('Укажите обе даты периода или очистите их для поиска по референсу.')
    if date_from and date_to:
        try:
            start = datetime.strptime(date_from, '%Y-%m-%d')
            end = datetime.strptime(date_to, '%Y-%m-%d')
        except ValueError:
            raise ValueError('Некорректная дата периода.') from None
        if start > end:
            raise ValueError('Дата «с» не должна быть позже даты «по».')
        try:
            end = end + timedelta(days=1)
        except OverflowError:
            raise ValueError('Некорректная конечная дата.') from None
        column = 'p.pay_date' if date_type == 'paymentDate' else 'p.doc_date'
        where += [f'{column} >= :date_from', f'{column} < :date_to']
        params.update(date_from=start, date_to=end)
    if reference:
        where.append('p.refer = :reference')
        params['reference'] = reference
    status = filters.get('status', '').strip()
    if status:
        if not re.fullmatch(r'[0-9]{1,10}', status):
            raise ValueError('Состояние должно быть числом.')
        where.append('p.tmst_id = :status')
        params['status'] = int(status)
    knp = filters.get('knp', '').strip()
    if knp:
        if not re.fullmatch(r'[0-9]{3}', knp):
            raise ValueError('КНП должен содержать три цифры, например 026.')
        where.append('p.cipher_id_knp = :knp')
        params['knp'] = knp
    amount = re.sub(r'\s+', '', filters.get('amount', '')).replace(',', '.')
    if amount:
        if not re.fullmatch(r'[0-9]{1,20}(\.[0-9]{1,2})?', amount):
            raise ValueError('Введите неотрицательную сумму с точностью до двух знаков после запятой.')
        where.append('p.pay_sum = :amount')
        params['amount'] = Decimal(amount)
    bin_value = filters.get('bin', '').strip()
    if bin_value:
        if not re.fullmatch(r'[0-9]{1,12}', bin_value):
            raise ValueError('БИН должен содержать от 1 до 12 цифр.')
        if len(bin_value) == 12:
            where.append('p.p_rnn = :bin')
            params['bin'] = bin_value
        else:
            where.append('p.p_rnn LIKE :bin')
            params['bin'] = '%' + bin_value + '%'
    # Направление пока не участвует в поиске. Лишняя строка определяет усечение.
    # Сортировка - во внутреннем запросе, до ROWNUM: при усечении остаются
    # самые свежие платежи, а не произвольные LIMIT + 1 строк.
    sql = 'SELECT ' + ', '.join('p.' + column for column in COLUMNS)
    sql += '\nFROM PMPD_PAY_DOC p\nWHERE ' + '\n  AND '.join(where)
    sql += '\nORDER BY p.pay_date DESC'
    sql = f'SELECT * FROM (\n{sql}\n)\nWHERE ROWNUM <= {LIMIT + 1}'
    return sql, params


def search_payments(filters):
    sql, params = build_query(filters)
    with get_connection() as connection:
        old_timeout = connection.call_timeout
        try:
            connection.call_timeout = 150000
            with connection.cursor() as cursor:
                cursor.arraysize = 200
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                results = []
                for row in rows[:LIMIT]:
                    item = {}
                    for key, value in zip(COLUMNS, row):
                        if hasattr(value, 'read'):
                            value = value.read()
                        if value is None:
                            item[key] = ''
                        elif key in ('pay_date', 'doc_date'):
                            item[key] = value.strftime('%d.%m.%Y')
                        else:
                            item[key] = str(value)
                    results.append(item)
        finally:
            connection.call_timeout = old_timeout
    return {'rows': results, 'truncated': len(rows) > LIMIT, 'limit': LIMIT}
