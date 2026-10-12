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
       p.p_name, p.p_rnn, p.rfbk_mfo_pbank, p.p_account, p.p_chief, p.p_mainbk,
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


def make_payment_doc_excel(doc):
    # Раскладка - как на экране и в старой форме «Списочная часть»: области
    # «Данные платежа», «Плательщик», «Получатель», затем таблица лиц.
    # Ширины колонок задаёт таблица (A..N), поля шапки - объединёнными ячейками.
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Списочная часть')
        title = workbook.add_format({'bold': True, 'font_size': 12})
        area = workbook.add_format({'bold': True, 'bottom': 1})
        label = workbook.add_format({'font_color': '#506A53', 'align': 'right', 'valign': 'top'})
        value = workbook.add_format({'num_format': '@', 'border': 1, 'bg_color': '#F2F2F2', 'valign': 'top'})
        value_wrap = workbook.add_format({'num_format': '@', 'border': 1, 'bg_color': '#F2F2F2', 'valign': 'top', 'text_wrap': True})
        value_money = workbook.add_format({'num_format': '#,##0.00', 'border': 1, 'bg_color': '#F2F2F2'})
        header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#DCE6F1', 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        text = workbook.add_format({'num_format': '@', 'border': 1})
        number = workbook.add_format({'border': 1})
        money = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        total_text = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#DCE6F1'})
        total_money = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'border': 1, 'bg_color': '#DCE6F1'})

        def cell(row, first, last, data, fmt):
            if first == last:
                sheet.write(row, first, data, fmt)
            else:
                sheet.merge_range(row, first, row, last, data, fmt)

        # Пары «подпись - значение»: (колонка подписи с..по, колонка значения с..по)
        slot1, slot2, slot3 = ((0, 1), (2, 4)), ((5, 5), (6, 7)), ((8, 8), (9, 13))
        wide1 = ((0, 1), (2, 7))

        def pair(row, slot, name, data, fmt=value):
            (l1, l2), (v1, v2) = slot
            cell(row, l1, l2, name, label)
            cell(row, v1, v2, data, fmt)

        def area_title(row, name):
            sheet.merge_range(row, 0, row, 13, name, area)

        sheet.write_string(0, 0, f"Платеж {doc['refer']}", title)

        area_title(2, 'Данные платежа')
        pair(3, slot1, 'Дата валют.', doc['pay_date']); pair(3, slot2, '№ док-та', doc['doc_nmb'])
        pair(4, slot1, 'Референс', doc['refer']); pair(4, slot2, 'Дата док-та', doc['doc_date'])
        pair(5, slot1, 'БИН', doc['p_rnn']); pair(5, slot2, 'Сумма', float(doc['pay_sum'] or 0), value_money)
        pair(6, slot1, 'Период', doc['period']); pair(6, slot2, 'КНП', doc['cipher_id_knp'])
        pair(7, ((0, 1), (2, 13)), 'Примечание', doc['doc_note'])
        pair(8, ((0, 1), (2, 13)), 'Назначение платежа', doc['doc_assign'], value_wrap)
        errors = (f"{doc['rfem_id']} {doc['err_name']} " if doc['rfem_id'] else '') + doc['doc_err']
        pair(9, ((0, 1), (2, 13)), 'Ошибки', errors.strip(), value_wrap)
        sheet.set_row(8, 30)
        sheet.set_row(9, 30)

        area_title(11, 'Плательщик')
        pair(12, wide1, 'Наименование', doc['p_name']); pair(12, slot3, 'БИН', doc['p_rnn'])
        pair(13, slot1, 'МФО', doc['rfbk_mfo_pbank']); pair(13, slot2, 'Счет', doc['p_account']); pair(13, slot3, 'Банк', doc['p_bank'])
        pair(14, slot1, 'Руководитель', doc['p_chief']); pair(14, slot2, 'Бухгалтер', doc['p_mainbk'])

        area_title(16, 'Получатель')
        pair(17, wide1, 'Наименование', doc['r_name']); pair(17, slot3, 'БИН', doc['r_rnn'])
        pair(18, slot1, 'МФО', doc['rfbk_mfo_rbank']); pair(18, slot2, 'Счет', doc['r_account']); pair(18, slot3, 'Банк', doc['r_bank'])

        area_title(20, 'Списочная часть')
        head = 21
        sheet.merge_range(head, 5, head, 7, 'Текущие ФИО', header)
        sheet.merge_range(head, 8, head, 10, 'ФИО при регистрации', header)
        for col, (_, name) in enumerate(LIST_COLUMNS):
            if col < 5 or col > 10:
                sheet.merge_range(head, col, head + 1, col, name, header)
            else:
                sheet.write_string(head + 1, col, name, header)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 14)
        sheet.set_column(2, 3, 10)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 10, 18)
        sheet.set_column(11, 11, 12)
        sheet.set_column(12, 13, 20)

        first_row = head + 2
        for row_num, row in enumerate(doc['rows'], first_row):
            for col, (key, _) in enumerate(LIST_COLUMNS):
                if key == 'pay_sum':
                    sheet.write_number(row_num, col, float(row[key] or 0), money)
                elif key == 'pmdl_n':
                    sheet.write_number(row_num, col, int(row[key]), number)
                else:
                    sheet.write_string(row_num, col, row[key], text)
        # Итог - как в старой форме: количество лиц под «№», сумма под «Сумма»
        total_row = first_row + len(doc['rows'])
        sheet.write_number(total_row, 0, len(doc['rows']), total_text)
        sheet.write_formula(total_row, 1, f'=SUM(B{first_row + 1}:B{total_row})', total_money,
                            float(doc['list_sum']))
        for col in range(2, 14):
            sheet.write_blank(total_row, col, None, total_text)
    output.seek(0)
    return output
