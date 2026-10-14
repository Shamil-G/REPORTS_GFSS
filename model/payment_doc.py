"""Платёж: шапка платёжного поручения и его списочная часть (PMDL_DOC_LIST)."""
from datetime import datetime
from io import BytesIO
import xlsxwriter

from db.connect import select_2
from model.payment_search import fix_kz

# Один платёж по уникальному MHMH_ID - индексы XN2_PMPD_PAY_DOC_MHMH_ID
# и XN1_PMDL_DOC_LIST_MHMH_ID (MHMH_ID, PMDL_N), поэтому запросы мгновенные.
stmt_doc = """
select p.mhmh_id, p.refer, p.pay_date, p.doc_nmb, p.doc_date, p.pay_sum, p.period,
       p.cipher_id_knp, p.tmst_id, p.msmt_code, p.doc_assign, p.doc_note, p.doc_err,
       p.rfem_id, e.name err_name,
       p.p_name, p.p_rnn, p.p_irs, p.r_irs, p.rfse_code_p, p.rfse_code_r, p.rfbk_mfo_pbank, p.p_account, p.p_chief, p.p_mainbk,
       pb.name p_bank,
       p.r_name, p.r_rnn, p.rfbk_mfo_rbank, p.r_account, rb.name r_bank
from pmpd_pay_doc p, loader.s_error e, loader.rfbk_bank pb, loader.rfbk_bank rb
where p.mhmh_id = :mhmh_id
  and e.id(+) = p.rfem_id
  -- МФО в обеих таблицах дополнены пробелами, справочник банков - 1 тыс. строк
  and trim(pb.rfbk_mfo(+)) = trim(p.rfbk_mfo_pbank)
  and trim(rb.rfbk_mfo(+)) = trim(p.rfbk_mfo_rbank)
"""

stmt_list = """
-- Не все коды ошибок есть в S_ERROR (296, 468), поэтому соединение внешнее
select d.pmdl_n, d.pay_sum, d.period, d.rfem_id, e.name err_name,
       d.fm, d.nm, d.ft, d.fm2, d.nm2, d.ft2, d.dt, d.sic, d.rnn
from pmdl_doc_list d, loader.s_error e
where d.mhmh_id = :mhmh_id
  and e.id(+) = d.rfem_id
order by d.pmdl_n
"""

# Колонки списочной части - как в старой форме «Списочная часть»
LIST_COLUMNS = [
    ('pmdl_n', '№ в списке'), ('pay_sum', 'Сумма'), ('period', 'Период'),
    ('rfem_id', 'Код ошибки'), ('err_name', 'Наименование ошибки'),
    ('fm', 'Фамилия'), ('nm', 'Имя'), ('ft', 'Отчество'),
    ('fm2', 'Фамилия'), ('nm2', 'Имя'), ('ft2', 'Отчество'),
    ('dt', 'Дата рожд'), ('sic', 'СИК'), ('rnn', 'РНН'),
]


def _text(value):
    if value is None:
        return ''
    if isinstance(value, datetime):
        return value.strftime('%d.%m.%Y')
    return fix_kz(str(value).strip())


def _birth_date(value):
    # DT хранится строкой ГГГГММДД
    value = (value or '').strip()
    if len(value) == 8 and value.isdigit():
        return f'{value[6:]}.{value[4:6]}.{value[:4]}'
    return value


def get_payment_doc(mhmh_id):
    docs = select_2(stmt_doc, {'mhmh_id': mhmh_id}, raise_on_error=True)
    if not docs:
        return None
    doc = {key: _text(value) for key, value in docs[0].items()}
    doc['pay_sum'] = docs[0]['pay_sum']
    rows = []
    for rec in select_2(stmt_list, {'mhmh_id': mhmh_id}, raise_on_error=True):
        row = {key: _text(value) for key, value in rec.items()}
        row['pay_sum'] = rec['pay_sum']
        row['dt'] = _birth_date(row['dt'])
        rows.append(row)
    doc['rows'] = rows
    doc['list_sum'] = sum(row['pay_sum'] or 0 for row in rows)
    return doc


# Цвета экрана (payment_search.css): фон области, поле, линия, текст, подпись, шапка таблицы, строки
PANEL, INPUT, LINE, TEXT, MUTED, HEAD, ROW, ERROR = (
    '#E9F4E5', '#EFEFD3', '#BFD0BC', '#24542C', '#506A53', '#DFEDDA', '#F3F9F0', '#A52432')
# Колонки листа: A и P - узкие поля внутри рамок, B..O - таблица лиц (LIST_COLUMNS)
SHEET_WIDTHS = [2, 10, 14, 10, 10, 40, 18, 18, 18, 18, 18, 18, 12, 20, 20, 2]


def make_payment_doc_excel(doc):
    # Вид - как таб платежа на экране: области в рамках на зелёном фоне, подписи
    # прижаты к полю, значения в жёлтых рамках. Последние колонки областей
    # идут вплотную друг к другу. Ширины колонок листа задаёт таблица лиц, поэтому
    # поля шапки собраны из объединённых ячеек так, чтобы между блоками не оставалось
    # пустых колонок.
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Списочная часть')
        for col, width in enumerate(SHEET_WIDTHS):
            sheet.set_column(col, col, width)
        last_col = len(SHEET_WIDTHS) - 1
        formats = {}

        def fmt(**props):
            props = {'font_color': TEXT, 'valign': 'vcenter', **props}
            key = tuple(sorted(props.items()))
            if key not in formats:
                formats[key] = workbook.add_format(props)
            return formats[key]

        label = fmt(bg_color=PANEL, font_color=MUTED, align='right')
        label_top = fmt(bg_color=PANEL, font_color=MUTED, align='right', valign='top')
        box = dict(bg_color=INPUT, border=1, border_color=LINE)
        value = fmt(num_format='@', **box)
        value_money = fmt(num_format='#,##0.00', **box)
        value_wrap = fmt(num_format='@', text_wrap=True, valign='top', **box)
        value_error = fmt(num_format='@', text_wrap=True, valign='top', **{**box, 'font_color': ERROR})

        def frame(top, bottom, title):
            # Фон области и рамка по её краю; заголовок - в верхней строке рамки
            for r in range(top, bottom + 1):
                for c in range(last_col + 1):
                    props = {'bg_color': PANEL}
                    for side, edge in (('top', r == top), ('bottom', r == bottom),
                                       ('left', c == 0), ('right', c == last_col)):
                        if edge:
                            props[side] = 1
                            props[side + '_color'] = LINE
                    sheet.write_blank(r, c, None, fmt(**props))
            sheet.write_string(top, 1, title, fmt(bg_color=PANEL, bold=True, top=1, top_color=LINE))

        def cell(r1, c1, r2, c2, data, f):
            if (r1, c1) == (r2, c2):
                sheet.write(r1, c1, data, f)
            else:
                sheet.merge_range(r1, c1, r2, c2, data, f)

        def pair(row, lab, val, name, data, f=value, rows=1):
            # lab / val - колонки подписи и значения «с..по»; rows - высота значения в строках
            cell(row, lab[0], row, lab[1], name, label_top if rows > 1 else label)
            cell(row, val[0], row + rows - 1, val[1], data, f)

        sheet.write_string(0, 1, f"Платеж {doc['refer']}", fmt(bold=True, font_size=12))

        # Данные платежа: две колонки полей рядом, назначение и ошибки - справа
        frame(2, 8, 'Данные платежа')
        # Блоки идут вплотную (B..C+D..E, F..G+H, I..J+K..O) - без пустых колонок между ними
        c1, c2, c3 = ((1, 2), (3, 4)), ((5, 6), (7, 7)), ((8, 9), (10, 14))
        pair(3, *c1, 'Дата валют.', doc['pay_date'])
        pair(3, *c2, '№ док-та', doc['doc_nmb'])
        pair(4, *c1, 'Референс', doc['refer'])
        pair(4, *c2, 'Дата док-та', doc['doc_date'])
        pair(5, *c1, 'БИН', doc['p_rnn'])
        pair(5, *c2, 'Сумма', float(doc['pay_sum'] or 0), value_money)
        pair(6, *c1, 'Период', doc['period'])
        pair(6, *c2, 'КНП', doc['cipher_id_knp'])
        pair(7, (1, 2), (3, 7), 'Примечание', doc['doc_note'])
        pair(3, *c3, 'Назначение платежа', doc['doc_assign'], value_wrap, rows=2)
        errors = (f"{doc['rfem_id']} {doc['err_name']} " if doc['rfem_id'] else '') + doc['doc_err']
        pair(5, *c3, 'Ошибки', errors.strip(), value_error, rows=3)

        # Плательщик / Получатель: вторая колонка - вплотную к первой; МФО - D..E, БИН - I, Счет - I..J
        n1, n2 = ((1, 2), (3, 6)), ((7, 7), (8, 10))
        mfo, bin_, acc = ((3, 4)), ((8, 8)), ((8, 9))
        frame(10, 15, 'Плательщик')
        pair(11, *n1, 'Наименование', doc['p_name'])
        pair(11, n2[0], bin_, 'БИН', doc['p_rnn'])
        pair(12, n1[0], mfo, 'МФО', doc['rfbk_mfo_pbank'])
        pair(12, n2[0], acc, 'Счет', doc['p_account'])
        pair(13, *n1, 'Банк', doc['p_bank'])
        pair(14, *n1, 'Руководитель', doc['p_chief'])
        pair(14, *n2, 'Бухгалтер', doc['p_mainbk'])

        frame(17, 21, 'Получатель')
        pair(18, *n1, 'Наименование', doc['r_name'])
        pair(18, n2[0], bin_, 'БИН', doc['r_rnn'])
        pair(19, n1[0], mfo, 'МФО', doc['rfbk_mfo_rbank'])
        pair(19, n2[0], acc, 'Счет', doc['r_account'])
        pair(20, *n1, 'Банк', doc['r_bank'])

        # Списочная часть: рамка вокруг таблицы, таблица - в колонках B..O
        head = 24
        first_row = head + 2
        total_row = first_row + len(doc['rows'])
        frame(23, total_row + 1, 'Списочная часть')
        line = dict(border=1, border_color=LINE)
        group = fmt(bg_color=PANEL, font_color=MUTED, **line)
        header = fmt(bg_color=HEAD, bold=True, text_wrap=True, **line)
        for col in range(1, last_col):
            sheet.write_blank(head, col, None, group)
        sheet.merge_range(head, 6, head, 8, 'Текущие ФИО', group)
        sheet.merge_range(head, 9, head, 11, 'ФИО при регистрации', group)
        for col, (_, name) in enumerate(LIST_COLUMNS, 1):
            sheet.write_string(head + 1, col, name, header)

        cell_line = dict(bg_color=ROW, bottom=1, bottom_color=LINE)
        text = fmt(num_format='@', **cell_line)
        number = fmt(align='left', **cell_line)
        money = fmt(num_format='#,##0.00', **cell_line)
        for row_num, row in enumerate(doc['rows'], first_row):
            for col, (key, _) in enumerate(LIST_COLUMNS, 1):
                if key == 'pay_sum':
                    sheet.write_number(row_num, col, float(row[key] or 0), money)
                elif key == 'pmdl_n':
                    sheet.write_number(row_num, col, int(row[key]), number)
                else:
                    sheet.write_string(row_num, col, row[key], text)
        # Итог - как в старой форме: количество лиц под «№», сумма под «Сумма»
        total = dict(bg_color=HEAD, bold=True, **line)
        for col in range(1, last_col):
            sheet.write_blank(total_row, col, None, fmt(**total))
        sheet.write_number(total_row, 1, len(doc['rows']), fmt(align='left', **total))
        sheet.write_formula(total_row, 2, f'=SUM(C{first_row + 1}:C{total_row})',
                            fmt(num_format='#,##0.00', **total), float(doc['list_sum']))
    output.seek(0)
    return output
