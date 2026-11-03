"""model/payment_card.py - поиск получателя в LOADER.PERSON (вкладка «Карточка»)."""
import re
from io import BytesIO
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
            'pay_sum_num': None if pay_sum is None else float(pay_sum),   # числа - для Excel
            'sum_pay_num': None if sum_pay is None else float(sum_pay),
            'status': '' if tmst_id is None else TMST_STATUSES.get(int(tmst_id), str(tmst_id)),
            'period': _text(period),
        })
    return {
        'person': {'sicid': sicid, 'iin': iin, 'lastname': _text(person[1]),
                   'firstname': _text(person[2]), 'middlename': _text(person[3])},
        'rows': result, 'total': _money(total), 'total_num': float(total),
        'truncated': len(rows) > INFO_LIMIT, 'limit': INFO_LIMIT,
    }


def make_card_info_excel(info):
    """Excel «Информация участнику» в том же виде, что и таб: шапка с ФИО и ИИН, колонки, строки, итого."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = 'Информация участнику'

    thin = Side(style='thin', color='FF9AAF97')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    head_fill = PatternFill('solid', fgColor='FFDFEDDA')
    group_fill = PatternFill('solid', fgColor='FFE9F4E5')
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    left = Alignment(horizontal='left', vertical='center', wrap_text=True)
    money_fmt = '#,##0.00'

    headers = ['Дата поступления', 'Дата отправки', '№', 'Дата документа', 'КНП', 'Отправитель',
               'БИН', 'Получатель', 'Сумма платежа', 'Сумма', 'Статус', 'Период']
    last_col = len(headers) + 1  # + «№ п/п»

    person = info['person']
    fio = ' '.join(x for x in (person['lastname'], person['firstname'], person['middlename']) if x)

    # строки 1-2: «№ п/п» на две строки, справа - заголовок с ФИО и ИИН, ниже - названия колонок
    ws.merge_cells(start_row=1, start_column=1, end_row=2, end_column=1)
    ws.cell(1, 1, '№ п/п')
    ws.merge_cells(start_row=1, start_column=2, end_row=1, end_column=last_col)
    ws.cell(1, 2, 'Информация участнику системы обязательного социального страхования\n'
                  f'ФИО: {fio}\nИИН: {person["iin"]}')
    ws.row_dimensions[1].height = 62
    for col, title in enumerate(headers, start=2):
        ws.cell(2, col, title)
    ws.row_dimensions[2].height = 32
    for row in (1, 2):
        for col in range(1, last_col + 1):
            c = ws.cell(row, col)
            c.font = Font(bold=True)
            c.fill = group_fill if row == 1 else head_fill
            c.border = border
            c.alignment = center
    ws.cell(1, 2).alignment = left

    r = 3
    for n, row in enumerate(info['rows'], start=1):
        values = [n, row['pay_date'], row['pay_date_gfss'], row['doc_nmb'], row['doc_date'], row['knp'],
                  row['p_name'], row['p_rnn'], row['receiver'], row['pay_sum_num'], row['sum_pay_num'],
                  row['status'], row['period']]
        for col, value in enumerate(values, start=1):
            c = ws.cell(r, col, value)
            c.border = border
            c.alignment = Alignment(vertical='center')
            if col in (10, 11):
                c.number_format = money_fmt
                c.alignment = Alignment(horizontal='right', vertical='center')
        r += 1

    if info['rows']:
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=10)
        ws.cell(r, 1, 'Итого')
        ws.cell(r, 11, info['total_num']).number_format = money_fmt
        for col in range(1, last_col + 1):
            c = ws.cell(r, col)
            c.font = Font(bold=True)
            c.fill = head_fill
            c.border = border
        ws.cell(r, 11).alignment = Alignment(horizontal='right')
        r += 1
    if info['truncated']:
        ws.cell(r + 1, 1, f"Показаны первые {info['limit']} записей.")

    for col, width in enumerate([7, 16, 16, 14, 16, 8, 38, 15, 32, 16, 16, 22, 10], start=1):
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.freeze_panes = 'A3'
    ws.page_setup.orientation = 'landscape'
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_title_rows = '1:2'

    out = BytesIO()
    wb.save(out)
    out.seek(0)
    return out
