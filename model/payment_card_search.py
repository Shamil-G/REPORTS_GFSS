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
INFO_LIMIT = 3000
RECEIVER = 'Гос.фонд социального страхования'


INFO_SQL = """SELECT * FROM (
WITH p AS (
    SELECT sicid FROM LOADER.person WHERE iin = :iin
),
sics AS (
    SELECT c.sicid FROM LOADER.p10_card c WHERE c.sicid IN (SELECT sicid FROM p)
    UNION ALL
    SELECT c.sicid FROM LOADER.p10_card c WHERE c.sicid_head IN (SELECT sicid FROM p)
),
l AS (
    SELECT pl.sicid, pl.pay_sum, pl.mhmh_id, pl.period, pl.rfem_id
      FROM sics v, LOADER.pmdl_doc_list pl
     WHERE pl.sicid = v.sicid
),
t AS (
    SELECT d.pay_date in_date, d.pay_date out_date, d.doc_nmb, d.doc_date,
           d.cipher_id_knp knp, d.p_name company, d.p_rnn rnn,
           NULL pf_name, d.pay_sum sum_doc, l.pay_sum, d.tmst_id,
           s.name, d.period
      FROM l, LOADER.pmpd_pay_doc d, LOADER.tmst_state s
     WHERE d.mhmh_id = l.mhmh_id
       AND s.tmst_id < 7
       AND d.tmst_id = s.tmst_id
       AND d.cipher_id_knp IN ('012', '017')
       AND d.pay_date < DATE '2006-07-01'
    UNION ALL
    SELECT d.pay_date, d.pay_date, d.doc_nmb, d.doc_date, d.cipher_id_knp,
           d.p_name, d.p_rnn, NULL, d.pay_sum, l.pay_sum,
           CASE WHEN l.rfem_id IS NULL THEN d.tmst_id ELSE 6 END,
           CASE WHEN l.rfem_id IS NULL THEN s.name ELSE 'СТОРНИРОВАННЫЕ' END,
           NVL(d.period, l.period)
      FROM l, LOADER.pmpd_pay_doc d, LOADER.tmst_state s
     WHERE d.mhmh_id = l.mhmh_id
       AND s.tmst_id <> 103
       AND d.tmst_id = s.tmst_id(+)
       AND d.cipher_id_knp IN ('012', '017')
       AND d.pay_date > DATE '2006-07-01'
    UNION ALL
    SELECT d.pay_date, d.pay_date, d.doc_nmb, d.doc_date, d.cipher_id_knp,
           d.p_name, d.p_rnn, d.r_name, d.pay_sum, l.pay_sum, d.tmst_id,
           s.name, NVL(d.period, l.period)
      FROM l, LOADER.pmpd_pay_doc d, LOADER.tmst_state s
     WHERE d.mhmh_id = l.mhmh_id
       AND s.tmst_id = 103
       AND d.tmst_id = s.tmst_id
       AND d.cipher_id_knp IN ('026', '094')
)
SELECT in_date, out_date, doc_nmb, doc_date, knp, company, rnn,
       NVL(pf_name, 'Гос.фонд социального страхования') pf_name, sum_doc,
       pay_sum, LOWER(RTRIM(name)) name, period,
       CASE WHEN tmst_id = 5 AND knp <> '032' THEN pay_sum ELSE 0 END sum_processed
  FROM t
 ORDER BY in_date
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
                iin = _text(person[0]).strip()
                if iin and not is_admin():
                    try:
                        if iin_in_ad(iin):
                            raise PermissionError('Доступ запрещен!')
                    except AdUnavailable:
                        raise ValueError('Не удалось проверить данные в Active Directory. Попробуйте позже.') from None
                rows = []
                if iin:
                    cursor.arraysize = 200
                    cursor.execute(INFO_SQL, {'iin': iin, 'lim': INFO_LIMIT + 1})
                    rows = cursor.fetchall()
        finally:
            connection.call_timeout = old_timeout

    result, total = [], Decimal(0)
    for (in_date, out_date, doc_nmb, doc_date, knp, company, rnn, pf_name,
         sum_doc, pay_sum, name, period, sum_processed) in rows[:INFO_LIMIT]:
        if sum_processed is not None:
            total += Decimal(str(sum_processed))
        result.append({
            'pay_date': _date(in_date), 'pay_date_gfss': _date(out_date),
            'doc_nmb': _text(doc_nmb), 'doc_date': _date(doc_date), 'knp': _text(knp),
            'p_name': _text(company), 'p_rnn': _text(rnn), 'receiver': _text(pf_name),
            'pay_sum': _money(sum_doc), 'sum_pay': _money(pay_sum),
            'sum_processed': _money(sum_processed),
            'pay_sum_num': None if sum_doc is None else float(sum_doc),   # числа - для Excel
            'sum_pay_num': None if pay_sum is None else float(pay_sum),
            'status': _text(name),
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
