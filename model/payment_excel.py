"""Выгрузка результатов поиска платежей: запрос выполняется заново, строки идут потоком."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import xlsxwriter

from model.payment_search import iter_payments

COLUMNS = [
    ('pay_date', 'Дата платежа'), ('doc_date', 'Дата документа'),
    ('doc_nmb', 'Номер документа'), ('refer', 'Референс'),
    ('cipher_id_knp', 'КНП'), ('pay_sum', 'Сумма, ₸'),
    ('rfem_id', 'Код ошибки'), ('tmst_id', 'Статус'),
    ('p_name', 'Наименование'), ('p_rnn', 'БИН'),
    ('rfbk_mfo_pbank', 'МФО'), ('p_account', 'Счет'),
    ('r_name', 'Наименование'), ('r_rnn', 'БИН'),
    ('rfbk_mfo_rbank', 'МФО'), ('r_account', 'Счет'),
    ('doc_assign', 'Назначение'), ('doc_err', 'Ошибка'),
]


def make_payment_excel(filters):
    """Excel по фильтрам поиска (не более payment_search.LIMIT строк).

    Файл пишется в режиме constant_memory: 200 тысяч строк не копятся в памяти
    приложения. Поэтому строки идут строго подряд, а ширины и высоты задаются
    до записи данных.
    """
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'constant_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Платежи')
        header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#DCE6F1', 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        text = workbook.add_format({'num_format': '@', 'valign': 'top'})
        date_format = workbook.add_format({'num_format': 'dd.mm.yyyy'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        total_format = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'top': 1})
        sheet.set_row(1, 32)
        sheet.set_column(0, 2, 16)
        sheet.set_column(3, 3, 42)
        sheet.set_column(4, 7, 16)
        sheet.set_column(8, 8, 36)
        sheet.set_column(9, 11, 24)
        sheet.set_column(12, 12, 36)
        sheet.set_column(13, 15, 24)
        sheet.set_column(16, 16, 60)
        sheet.set_column(17, 17, 18)
        for first, last, title in [(0, 7, 'Общие'), (8, 11, 'Плательщик'), (12, 15, 'Получатель'), (16, 17, 'Дополнительно')]:
            sheet.merge_range(0, first, 0, last, title, header)
        for col, (_, title) in enumerate(COLUMNS):
            sheet.write_string(1, col, title, header)
        sheet.freeze_panes(2, 0)
        total = 0.0
        count = 0
        for row_num, row in enumerate(iter_payments(filters), 2):
            count += 1
            for col, (key, _) in enumerate(COLUMNS):
                value = row.get(key)
                if value is None or value == '':
                    continue
                if key in ('pay_date', 'doc_date'):
                    sheet.write_datetime(row_num, col, datetime.strptime(value, '%d.%m.%Y'), date_format)
                elif key == 'pay_sum':
                    number = float(Decimal(value))
                    total += number
                    sheet.write_number(row_num, col, number, money)
                else:
                    sheet.write_string(row_num, col, value[:32767], text)
        if not count:
            raise ValueError('Платежи не найдены: выгружать нечего.')
        total_row = count + 2
        sheet.write_string(total_row, 0, 'ИТОГО', total_format)
        sheet.write_formula(total_row, 5, f'=SUM(F3:F{count + 2})', total_format, total)
        sheet.autofilter(1, 0, count + 1, 17)
    output.seek(0)
    return output
