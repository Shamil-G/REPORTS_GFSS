"""Печать платежа: платёжное поручение на листе А4 - по образцу бумажной формы."""
from io import BytesIO
import xlsxwriter

# Ширины колонок: A - подписи, B - значения, C/D - ИИК, БИК, КОд/КБе, E - сумма и коды
WIDTHS = [30, 40, 24, 22, 20]

_ONES = ['', 'один', 'два', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
_ONES_F = ['', 'одна', 'две', 'три', 'четыре', 'пять', 'шесть', 'семь', 'восемь', 'девять']
_TEENS = ['десять', 'одиннадцать', 'двенадцать', 'тринадцать', 'четырнадцать', 'пятнадцать',
          'шестнадцать', 'семнадцать', 'восемнадцать', 'девятнадцать']
_TENS = ['', '', 'двадцать', 'тридцать', 'сорок', 'пятьдесят', 'шестьдесят', 'семьдесят',
         'восемьдесят', 'девяносто']
_HUNDREDS = ['', 'сто', 'двести', 'триста', 'четыреста', 'пятьсот', 'шестьсот', 'семьсот',
             'восемьсот', 'девятьсот']
# (форма для 1, форма для 2-4, форма для 5+, женский род)
_UNITS = [('', '', '', False),
          ('тысяча', 'тысячи', 'тысяч', True),
          ('миллион', 'миллиона', 'миллионов', False),
          ('миллиард', 'миллиарда', 'миллиардов', False)]


def _triple(n, feminine):
    words = [_HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest < 20:
        words.append(_TEENS[rest - 10])
    else:
        words.append(_TENS[rest // 10])
        words.append((_ONES_F if feminine else _ONES)[rest % 10])
    return [w for w in words if w]


def sum_in_words(amount):
    """1476963.69 -> 'Один миллион ... шестьдесят три тенге 69 тиын'."""
    tenge, tiyn = divmod(int(round(float(amount or 0) * 100)), 100)
    words = ['ноль'] if tenge == 0 else []
    for i in range(len(_UNITS) - 1, -1, -1):
        part = tenge // 1000 ** i % 1000
        if not part:
            continue
        one, few, many, feminine = _UNITS[i]
        words += _triple(part, feminine)
        if i:
            tail = 0 if part % 100 // 10 == 1 else part % 10
            words.append(one if tail == 1 else few if 2 <= tail <= 4 else many)
    text = ' '.join(words)
    return f'{text[0].upper()}{text[1:]} тенге {tiyn:02d} тиын'


def make_payment_print_excel(doc):
    output = BytesIO()
    with xlsxwriter.Workbook(output, {
        'in_memory': True, 'strings_to_formulas': False, 'strings_to_urls': False,
    }) as workbook:
        sheet = workbook.add_worksheet('Печать платежа')
        for col, width in enumerate(WIDTHS):
            sheet.set_column(col, col, width)
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 1)
        sheet.set_margins(0.5, 0.5, 0.5, 0.5)
        sheet.hide_gridlines(2)
        formats = {}

        def fmt(**props):
            props = {'font_name': 'Arial', 'font_size': 9, 'valign': 'vcenter', **props}
            key = tuple(sorted(props.items()))
            if key not in formats:
                formats[key] = workbook.add_format(props)
            return formats[key]

        def cell(r1, c1, r2, c2, data, f):
            if (r1, c1) == (r2, c2):
                sheet.write(r1, c1, data, f)
            else:
                sheet.merge_range(r1, c1, r2, c2, data, f)

        grid = dict(border=1)
        label = fmt(text_wrap=True, **grid)
        value = fmt(text_wrap=True, num_format='@', **grid)
        center = fmt(text_wrap=True, align='center', num_format='@', **grid)
        last = len(WIDTHS) - 1

        sheet.write_string(0, 0, 'Поступило в банк-получатель', fmt(bold=True))
        sheet.set_row(0, 24)
        cell(2, 0, 2, last, f"ПЛАТЕЖНОЕ ПОРУЧЕНИЕ №{doc['doc_nmb']}",
             fmt(bold=True, font_size=11, align='center'))
        cell(3, 0, 3, last, doc['doc_date'], fmt(bold=True, align='center'))
        cell(4, 0, 4, last, '(дата документа)', fmt(bold=True, align='center'))
        cell(6, 2, 6, 3, 'выписки документа', fmt(align='center'))
        sheet.write_string(6, last, 'СУММА', fmt(bold=True, align='center'))

        def stack(caption, data):
            return f'{caption}\n{data}' if data else caption

        # (высота, подпись, значение, правый блок: ('c', подпись, значение) - две ячейки
        # C и D, ('cd', подпись, значение) - одна ячейка C:D)
        rows = [
            (30, 'Фактический плательщик', '', ('c', 'ИИН (БИН)', '', '', '')),
            (40, 'Отправитель денег', doc['p_name'],
             ('c', 'ИИК', doc['p_account'], 'КОд', doc['p_irs'] + doc['rfse_code_p'])),
            (28, 'ИИН (БИН)', doc['p_rnn'], ('c', 'Страна резидентства', '', '', '')),
            (42, 'Банк, филиал банка-нерезидента Республики Казахстан отправителя денег',
             doc['p_bank'], ('cd', 'БИК', doc['rfbk_mfo_pbank'])),
            (40, 'Бенефициар', doc['r_name'],
             ('c', 'ИИК', doc['r_account'], 'КБе', doc['r_irs'] + doc['rfse_code_r'])),
            (28, 'ИИН (БИН)', doc['r_rnn'], ('c', 'Страна резидентства', '', '', '')),
            (30, 'Фактический (конечный) бенефициар', '', ('cd', 'ИИН (БИН)', '')),
            (42, 'Банк, филиал банка-нерезидента Республики Казахстан бенефициара',
             doc['r_bank'], ('cd', 'БИК', doc['rfbk_mfo_rbank'])),
            (42, 'Банк, филиал банка-нерезидента Республики Казахстан - посредник',
             '', ('cd', 'БИК', '')),
        ]
        r = 7
        for height, name, val, right in rows:
            sheet.set_row(r, height)
            sheet.write_string(r, 0, name, label)
            sheet.write_string(r, 1, val, value)
            if right[0] == 'cd':
                cell(r, 2, r, 3, stack(right[1], right[2]), center)
            else:
                sheet.write_string(r, 2, stack(right[1], right[2]), center)
                # у «ИИН (БИН)» и «Страна резидентства» ячейка D пустая
                sheet.write_string(r, 3, stack(right[3], right[4]), center)
            r += 1
        # Сумма - справа от первых строк таблицы, как на бумажной форме
        cell(7, 4, 8, 4, float(doc['pay_sum'] or 0),
             fmt(bold=True, align='center', num_format='#,##0.00', **grid))
        cell(9, 4, 15, 4, '', value)

        sheet.set_row(r, 30)
        sheet.write_string(r, 0, 'Сумма прописью', label)
        cell(r, 1, r, last, sum_in_words(doc['pay_sum']), value)
        r += 1
        sheet.set_row(r, 30)
        sheet.write_string(r, 0, 'Дата получения товара (оказания услуг)', label)
        cell(r, 1, r, 2, '', value)
        sheet.write_string(r, 3, 'Код назначения платежа', center)
        sheet.write_string(r, 4, doc['cipher_id_knp'], center)
        r += 1
        sheet.set_row(r, 30)
        cell(r, 0, r, 2, 'Назначение платежа', fmt(valign='top', **grid))
        sheet.write_string(r, 3, 'Код бюджетной классификации', center)
        sheet.write_string(r, 4, '', center)
        for extra in (1, 2, 3):
            sheet.set_row(r + extra, 22)
        cell(r + 1, 0, r + 3, 2, doc['doc_assign'],
             fmt(text_wrap=True, valign='bottom', num_format='@', **grid))
        cell(r + 1, 3, r + 2, 4, '', value)
        sheet.write_string(r + 3, 3, 'Дата валютирования', center)
        sheet.write_string(r + 3, 4, doc['pay_date'], center)
        r += 5

        plain = fmt(text_wrap=True, valign='top')
        sign_top = r
        for caption, name in (
            ('Фамилия, имя, отчество (при его наличии) руководителя (уполномоченного лица)',
             doc['p_chief']),
            ('Фамилия, имя, отчество (при его наличии) главного бухгалтера (уполномоченного лица)',
             doc['p_mainbk']),
        ):
            sheet.set_row(r, 40)
            sheet.write_string(r, 0, caption, plain)
            sheet.write_string(r, 1, name, plain)
            sheet.write_string(r + 1, 0, 'Подпись ______________', plain)
            r += 3
        # Подписи банка - справа от подписей плательщика
        bank = fmt(align='center')
        cell(sign_top, 2, sign_top, last, '(Подписи ответственных исполнителей банка)', bank)
        cell(sign_top + 1, 2, sign_top + 1, last, 'Проведено банком', bank)
        cell(sign_top + 2, 2, sign_top + 2, last, '"___" ____________ 20___ г.', bank)
        sheet.print_area(0, 0, r, last)
    output.seek(0)
    return output
