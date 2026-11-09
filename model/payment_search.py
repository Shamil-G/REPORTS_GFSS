"""Поиск платежей напрямую в PMPD_PAY_DOC."""
import re
from datetime import datetime, timedelta
from decimal import Decimal

from db.connect import get_connection
from util.access import is_admin
from util.ad_check import iin_in_ad, AdUnavailable

# Наибольшее число платежей одного поиска и одной выгрузки в Excel. Больше -
# приложение зависает, поэтому поиск показывает первые LIMIT, а выгрузка при
# превышении отказывает (неполный файл молча отдавать нельзя).
LIMIT = 15000
PAGE_SIZE = 200              # строк на странице экрана
EXPORT_TIMEOUT_MS = 170000   # меньше timeout gunicorn (180 с)
COLUMNS = (
    'pay_date', 'doc_date', 'doc_nmb', 'refer', 'cipher_id_knp',
    'pay_sum', 'rfem_id', 'tmst_id', 'p_name', 'p_rnn',
    'rfbk_mfo_pbank', 'p_account', 'r_name', 'r_rnn',
    'rfbk_mfo_rbank', 'r_account', 'doc_assign', 'doc_err', 'mhmh_id',
)

# Платёжная система хранит казахские буквы подменёнными на похожие из CP1251
# (ЖЎМАЄАЛИЎЛЫ, Маќтажан). Таблица выверена по PMDL_DOC_LIST и PMPD_PAY_DOC,
# правильных казахских букв там нет, поэтому замена однозначна. І - уже верная.
KZ_FIX = str.maketrans('ЈЄЌЅҐЎЇЋјєќѕґўїћ', 'ӘҒҚҢӨҰҮҺәғқңөұүһ')


def fix_kz(text):
    return text.translate(KZ_FIX)


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
    # БИН плательщика (p_rnn) и БИН получателя (r_rnn) - одна и та же проверка
    for key, column in (('bin', 'p_rnn'), ('rbin', 'r_rnn')):
        bin_value = filters.get(key, '').strip()
        if not bin_value:
            continue
        # Меньше 6 цифр - слишком широкая выборка: сортировка по дате читает
        # почти всю таблицу и упирается в таймаут.
        if not re.fullmatch(r'[0-9]{6,12}', bin_value):
            raise ValueError('БИН должен содержать от 6 до 12 цифр.')
        if len(bin_value) == 12:
            # 12 цифр - это может быть ИИН сотрудника: данные сотрудников не
            # выдаются, кроме роли Admin. AD недоступен - поиск не выполняется.
            if not is_admin():
                try:
                    if iin_in_ad(bin_value):
                        raise ValueError('Доступ запрещен!')
                except AdUnavailable:
                    raise ValueError('Не удалось проверить данные в Active Directory. Попробуйте позже.') from None
            where.append(f'p.{column} = :{key}')
            params[key] = bin_value
        else:
            # По началу номера: шаблон без ведущего % может использовать индекс,
            # с '%...%' запрос читает всю таблицу и упирается в таймаут.
            where.append(f'p.{column} LIKE :{key}')
            params[key] = bin_value + '%'
    # Направление пока не участвует в поиске. Лишняя строка определяет усечение.
    # Сортировка - во внутреннем запросе, до ROWNUM: при усечении остаются
    # самые свежие платежи, а не произвольные LIMIT + 1 строк.
    sql = 'SELECT ' + ', '.join('p.' + column for column in COLUMNS)
    sql += '\nFROM PMPD_PAY_DOC p\nWHERE ' + '\n  AND '.join(where)
    # mhmh_id - второй ключ, чтобы страницы не «плавали» при равных датах
    sql += '\nORDER BY p.pay_date DESC, p.mhmh_id'
    sql = f'SELECT * FROM (\n{sql}\n)\nWHERE ROWNUM <= {LIMIT + 1}'
    return sql, params


def _to_item(row):
    """Строка курсора -> словарь с текстовыми значениями (как их видит экран)."""
    item = {}
    for key, value in zip(COLUMNS, row):
        if hasattr(value, 'read'):
            value = value.read()
        if value is None:
            item[key] = ''
        elif key in ('pay_date', 'doc_date'):
            item[key] = value.strftime('%d.%m.%Y')
        else:
            item[key] = fix_kz(str(value))
    return item


def search_payments(filters):
    """Одна страница результатов поиска + общее число и сумма найденного.

    Число и сумма считаются оконными функциями по тем же LIMIT + 1 строкам,
    что отбирает build_query, поэтому отдельного запроса COUNT нет. Если
    найдено больше LIMIT, truncated=True, а точная сумма не определена.
    """
    sql, params = build_query(filters)
    try:
        page = max(1, int(filters.get('page') or 1))
    except ValueError:
        raise ValueError('Некорректный номер страницы.') from None
    low = (page - 1) * PAGE_SIZE
    high = min(page * PAGE_SIZE, LIMIT)
    cols = ', '.join(COLUMNS)
    sql = (
        f'SELECT {cols}, total_cnt, total_sum FROM (\n'
        f'  SELECT a.*, ROWNUM rn FROM (\n'
        f'    SELECT {cols}, COUNT(*) OVER () total_cnt, SUM(pay_sum) OVER () total_sum\n'
        f'    FROM (\n{sql}\n)\n'
        f'    ORDER BY pay_date DESC, mhmh_id\n'
        f'  ) a WHERE ROWNUM <= :page_high\n'
        f') WHERE rn > :page_low'
    )
    params.update(page_high=high, page_low=low)
    with get_connection() as connection:
        old_timeout = connection.call_timeout
        try:
            connection.call_timeout = 150000
            with connection.cursor() as cursor:
                cursor.arraysize = PAGE_SIZE
                cursor.execute(sql, params)
                rows = cursor.fetchall()
        finally:
            connection.call_timeout = old_timeout
    n = len(COLUMNS)
    results = [_to_item(row[:n]) for row in rows]
    found = int(rows[0][n]) if rows else 0
    truncated = found > LIMIT
    total = min(found, LIMIT)
    total_sum = None if truncated or not rows else float(rows[0][n + 1] or 0)
    return {'rows': results, 'truncated': truncated, 'limit': LIMIT,
            'page': page, 'page_size': PAGE_SIZE, 'total': total,
            'pages': max(1, -(-total // PAGE_SIZE)), 'total_sum': total_sum}


def iter_payments(filters):
    """Все найденные платежи подряд для выгрузки в Excel (не более LIMIT).

    Читает курсор пачками, не складывая результат в память. Если платежей
    больше LIMIT, бросает ValueError: выгрузка не должна молча терять строки.
    """
    sql, params = build_query(filters)
    with get_connection() as connection:
        old_timeout = connection.call_timeout
        try:
            connection.call_timeout = EXPORT_TIMEOUT_MS
            with connection.cursor() as cursor:
                cursor.arraysize = 2000
                cursor.execute(sql, params)
                count = 0
                while True:
                    batch = cursor.fetchmany(2000)
                    if not batch:
                        break
                    for row in batch:
                        count += 1
                        if count > LIMIT:
                            raise ValueError(
                                f'Найдено более {LIMIT:_} платежей: выгрузка невозможна. '
                                'Уточните фильтры.'.replace('_', ' '))
                        yield _to_item(row)
        finally:
            connection.call_timeout = old_timeout
