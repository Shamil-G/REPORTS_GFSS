"""Выгрузка показанных результатов поиска без повторного запроса к Oracle."""
from datetime import datetime
from decimal import Decimal, InvalidOperation
from io import BytesIO
import xlsxwriter

COLUMNS = [
    ('pay_date', 'Дата платежа'), ('doc_date', 'Дата документа'),
    ('doc_nmb', 'Номер документа'), ('refer', 'Референс'),
    ('cipher_id_knp', 'КНП'), ('pay_sum', 'Сумма, ₸'),
    ('doc_err', 'Код ошибки'), ('tmst_id', 'Статус'),
    ('p_name', 'Наименование'), ('p_rnn', 'БИН'),
    ('rfbk_mfo_pbank', 'МФО'), ('p_account', 'Счет'),
    ('r_name', 'Наименование'), ('r_rnn', 'БИН'),
    ('rfbk_mfo_rbank', 'МФО'), ('r_account', 'Счет'),
    ('doc_assign', 'Назначение'), ('doc_err', 'Ошибка'),
]


def make_payment_excel(rows):
    if not isinstance(rows, list) or not rows or len(rows) > 3000:
        raise ValueError('Для выгрузки необходимо от 1 до 3000 записей.')
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Платежи')
        header = workbook.add_format({'bold': True, 'border': 1, 'bg_color': '#DCE6F1', 'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
        text = workbook.add_format({'num_format': '@', 'valign': 'top'})
        date_format = workbook.add_format({'num_format': 'dd.mm.yyyy'})
        money = workbook.add_format({'num_format': '#,##0.00'})
        total_format = workbook.add_format({'bold': True, 'num_format': '#,##0.00', 'top': 1})
        for first, last, title in [(0, 7, 'Общие'), (8, 11, 'Плательщик'), (12, 15, 'Получатель'), (16, 17, 'Дополнительно')]:
            sheet.merge_range(0, first, 0, last, title, header)
        for col, (_, title) in enumerate(COLUMNS):
            sheet.write_string(1, col, title, header)
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
        for row_num, row in enumerate(rows, 2):
            if not isinstance(row, dict):
                raise ValueError('Некорректные данные таблицы.')
            for col, (key, _) in enumerate(COLUMNS):
                value = row.get(key)
                if value is None or value == '':
                    continue
                if not isinstance(value, (str, int, float)):
                    raise ValueError('Некорректное значение в таблице.')
                if key in ('pay_date', 'doc_date'):
                    try:
                        parsed = datetime.strptime(str(value), '%d.%m.%Y')
                    except ValueError:
                        raise ValueError('Некорректная дата в таблице.') from None
                    sheet.write_datetime(row_num, col, parsed, date_format)
                elif key == 'pay_sum':
                    try:
                        amount = Decimal(str(value))
                        if not amount.is_finite():
                            raise InvalidOperation
                        number = float(amount)
                        if not (-1e308 < number < 1e308):
                            raise InvalidOperation
                    except (InvalidOperation, ValueError, OverflowError):
                        raise ValueError('Некорректная сумма в таблице.') from None
                    sheet.write_number(row_num, col, number, money)
                else:
                    if len(str(value)) > 32767:
                        raise ValueError('Слишком длинный текст в таблице.')
                    sheet.write_string(row_num, col, str(value), text)
        total_row = len(rows) + 2
        sheet.write_string(total_row, 0, 'ИТОГО', total_format)
        sheet.write_formula(total_row, 5, f'=SUM(F3:F{len(rows) + 2})', total_format,
                            sum(float(row.get('pay_sum') or 0) for row in rows))
        sheet.freeze_panes(2, 0)
        sheet.autofilter(1, 0, len(rows) + 1, 17)
    output.seek(0)
    return output
