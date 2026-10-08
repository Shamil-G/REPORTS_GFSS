(() => {
    'use strict';
    const form = document.getElementById('payment-filters');
    if (!form) return;
    const results = document.getElementById('ps-results');
    const error = document.getElementById('ps-error');
    const from = form.elements.dateFrom;
    const to = form.elements.dateTo;
    const isoDate = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    const today = new Date();
    const todayISO = isoDate(today);
    const monthStart = isoDate(new Date(today.getFullYear(), today.getMonth(), 1));
    from.defaultValue = monthStart;
    to.defaultValue = todayISO;

    // Вымышленные записи для проверки интерфейса. Запросов к серверу нет.
    // При подключении API заменить этот массив ответом сервера и справочники
    // формы — действующими значениями из БД.
    const demoRows = [
        {id: 'DEMO-001', knp: '012', amount: 25000, direction: 'incoming', paymentType: 'payment', payer: 'ТОО «Пример Альфа»', payerBin: '000000000001', recipient: 'АО «Пример Фонд»', recipientBin: '000000000099', date: todayISO},
        {id: 'DEMO-002', knp: '012', amount: 125000.50, direction: 'incoming', paymentType: 'payment', payer: 'ТОО «Пример Бета»', payerBin: '000000000002', recipient: 'АО «Пример Фонд»', recipientBin: '000000000099', date: monthStart},
        {id: 'DEMO-003', knp: '048', amount: 395503389, direction: 'outgoing', paymentType: 'payment', payer: 'АО «Пример Фонд»', payerBin: '000000000099', recipient: 'АО «Пример Получатель»', recipientBin: '000000000003', date: todayISO},
        {id: 'DEMO-004', knp: '012', amount: 10000, direction: 'outgoing', paymentType: 'return', payer: 'АО «Пример Фонд»', payerBin: '000000000099', recipient: 'ТОО «Пример Альфа»', recipientBin: '000000000001', date: todayISO},
    ].map((row, index) => ({
        ...row, status: '5', errorCode: '—', documentNumber: String(1408 + index),
        reference: row.id, paymentDate: row.date, processedDate: row.date,
        documentDate: isoDate(new Date(Number(row.date.slice(0, 4)), Number(row.date.slice(5, 7)) - 1, Number(row.date.slice(8, 10)) - 1)),
        payerMfo: 'DEMOXXXX', payerAccount: `KZ00DEMO00000000000${index + 1}`,
    }));
    const money = value => new Intl.NumberFormat('ru-RU', {minimumFractionDigits: 2, maximumFractionDigits: 2}).format(value);
    const formatDate = value => value.split('-').reverse().join('.');

    function render(rows) {
        results.replaceChildren();
        for (const row of rows) {
            const tr = document.createElement('tr');
            const cells = [formatDate(row.paymentDate), formatDate(row.documentDate), row.documentNumber,
                row.reference, row.knp, money(row.amount), row.errorCode, `${row.status} — Обработан`,
                row.payer, row.payerBin, row.payerMfo, row.payerAccount, row.recipient, row.recipientBin];
            cells.forEach((value, index) => {
                const td = document.createElement('td');
                td.textContent = value;
                if (index === 5) td.classList.add('ps-money');
                tr.appendChild(td);
            });
            results.appendChild(tr);
        }
        document.getElementById('ps-empty').hidden = rows.length > 0;
        const totalCents = rows.reduce((total, row) => total + Math.round(row.amount * 100), 0);
        document.getElementById('ps-summary').textContent = `Найдено: ${rows.length} · Общая сумма: ${money(totalCents / 100)} ₸`;
    }

    function search() {
        error.hidden = true;
        const filters = Object.fromEntries(new FormData(form));
        if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
            error.textContent = 'Дата «с» не должна быть позже даты «по».';
            error.hidden = false;
            from.focus();
            return;
        }
        const amountText = filters.amount.trim().replace(/\s/g, '').replace(',', '.');
        if (amountText && (!/^\d+(\.\d{1,2})?$/.test(amountText) || !Number.isSafeInteger(Math.round(Number(amountText) * 100)))) {
            error.textContent = 'Введите неотрицательную сумму с точностью до двух знаков после запятой.';
            error.hidden = false;
            form.elements.amount.focus();
            return;
        }
        const reference = filters.reference.trim().toLocaleLowerCase('ru');
        const bin = filters.bin.trim();
        render(demoRows.filter(row =>
            (!filters.status || row.status === filters.status) &&
            (!filters.knp || row.knp === filters.knp) &&
            (!filters.direction || row.direction === filters.direction) &&
            (!filters.paymentType || row.paymentType === filters.paymentType) &&
            (!reference || row.reference.toLocaleLowerCase('ru').includes(reference)) &&
            (!bin || row.payerBin.includes(bin) || row.recipientBin.includes(bin)) &&
            (!amountText || Math.round(row.amount * 100) === Math.round(Number(amountText) * 100)) &&
            (!filters.dateFrom || row[filters.dateType] >= filters.dateFrom) &&
            (!filters.dateTo || row[filters.dateType] <= filters.dateTo)
        ));
    }
    form.addEventListener('submit', event => { event.preventDefault(); search(); });
    // После штатного сброса формы возвращаем исходные фильтры и результаты.
    form.addEventListener('reset', () => { setTimeout(search, 0); });
    search();
})();
