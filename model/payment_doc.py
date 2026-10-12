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
       p.r_name, p.r_rnn, p.rfbk_mfo_rbank, p.r_account
from pmpd_pay_doc p, loader.s_error e
where p.mhmh_id = :mhmh_id
  and e.id(+) = p.rfem_id
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
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Списочная часть')
        title = workbook.add_format({'bold': True, 'font_size': 12})
        header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#DCE6F1', 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        text = workbook.add_format({'num_format': '@', 'border': 1})
        number = workbook.add_format({'border': 1})
        money = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        total_format = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'top': 1})

        sheet.write_string(0, 0, f"Платеж {doc['refer']} от {doc['pay_date']}, документ № {doc['doc_nmb']} от {doc['doc_date']}, КНП {doc['cipher_id_knp']}, период {doc['period']}", title)
        sheet.write_string(1, 0, f"Плательщик: {doc['p_name']}, БИН {doc['p_rnn']}")
        sheet.write_string(2, 0, f"Получатель: {doc['r_name']}, БИН {doc['r_rnn']}")
        sheet.write_string(3, 0, f"Назначение платежа: {doc['doc_assign']}")

        sheet.merge_range(5, 5, 5, 7, 'Текущие ФИО', header)
        sheet.merge_range(5, 8, 5, 10, 'ФИО при регистрации', header)
        for col, (_, name) in enumerate(LIST_COLUMNS):
            if col < 5 or col > 10:
                sheet.merge_range(5, col, 6, col, name, header)
            else:
                sheet.write_string(6, col, name, header)
        sheet.set_column(0, 0, 10)
        sheet.set_column(1, 1, 14)
        sheet.set_column(2, 3, 10)
        sheet.set_column(4, 4, 40)
        sheet.set_column(5, 10, 18)
        sheet.set_column(11, 11, 12)
        sheet.set_column(12, 13, 20)

        first_row = 7
        for row_num, row in enumerate(doc['rows'], first_row):
            for col, (key, _) in enumerate(LIST_COLUMNS):
                if key == 'pay_sum':
                    sheet.write_number(row_num, col, float(row[key] or 0), money)
                elif key == 'pmdl_n':
                    sheet.write_number(row_num, col, int(row[key]), number)
                else:
                    sheet.write_string(row_num, col, row[key], text)
        total_row = first_row + len(doc['rows'])
        sheet.write_string(total_row, 0, 'ИТОГО', total_format)
        sheet.write_formula(total_row, 1, f'=SUM(B{first_row + 1}:B{total_row})', total_format,
                            float(doc['list_sum']))
        sheet.freeze_panes(first_row, 0)
    output.seek(0)
    return output
