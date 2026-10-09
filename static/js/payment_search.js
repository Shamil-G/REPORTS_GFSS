(() => {
    'use strict';
    const form = document.getElementById('payment-filters');
    if (!form) return;
    const results = document.getElementById('ps-results');
    const error = document.getElementById('ps-error');
    const summary = document.getElementById('ps-summary');
    const empty = document.getElementById('ps-empty');
    const button = form.querySelector('button[type="submit"]');
    const initialSummary = summary.textContent;
    const columns = ['pay_date', 'doc_date', 'doc_nmb', 'refer', 'cipher_id_knp',
        'pay_sum', 'doc_err', 'tmst_id', 'p_name', 'p_rnn', 'rfbk_mfo_pbank',
        'p_account', 'r_name', 'r_rnn', 'rfbk_mfo_rbank', 'r_account', 'doc_assign', 'doc_err'];
    const money = value => new Intl.NumberFormat('ru-RU', {
        minimumFractionDigits: 2, maximumFractionDigits: 2
    }).format(Number(value || 0));
    let controller = null;
    let sequence = 0;

    function updateRequired() {
        const required = !form.elements.reference.value.trim();
        form.elements.dateFrom.required = required;
        form.elements.dateTo.required = required;
    }
    function showError(message) {
        error.textContent = message;
        error.hidden = false;
    }
    function render(data) {
        results.replaceChildren();
        const fragment = document.createDocumentFragment();
        for (const row of data.rows) {
            const tr = document.createElement('tr');
            columns.forEach((key, index) => {
                const td = document.createElement('td');
                td.textContent = index === 5 ? money(row[key]) : (row[key] ?? '');
                if (index === 5) td.classList.add('ps-money');
                tr.appendChild(td);
            });
            fragment.appendChild(tr);
        }
        results.appendChild(fragment);
        empty.hidden = data.rows.length > 0;
        const total = data.rows.reduce((sum, row) => sum + Number(row.pay_sum || 0), 0);
        summary.textContent = data.truncated
            ? `Показаны первые ${data.limit} записей. Уточните фильтры. Сумма показанных платежей: ${money(total)} ₸`
            : `Найдено: ${data.rows.length} · Общая сумма: ${money(total)} ₸`;

        document.dispatchEvent(
            new CustomEvent('payment-search-results', {detail: data})
        );
    }
    form.elements.reference.addEventListener('input', updateRequired);
    updateRequired();
    form.addEventListener('submit', async event => {
        event.preventDefault();
        error.hidden = true;
        const filters = Object.fromEntries(new FormData(form));
        if (!filters.reference.trim() && (!filters.dateFrom || !filters.dateTo)) {
            showError('Укажите обе даты периода или референс.');
            return;
        }
        if (Boolean(filters.dateFrom) !== Boolean(filters.dateTo)) {
            showError('Укажите обе даты периода или очистите их для поиска по референсу.');
            return;
        }
        if (filters.dateFrom && filters.dateTo && filters.dateFrom > filters.dateTo) {
            showError('Дата «с» не должна быть позже даты «по».');
            return;
        }
        if (controller) controller.abort();
        const currentController = new AbortController();
        controller = currentController;
        const currentSequence = ++sequence;
        const timer = setTimeout(() => currentController.abort(), 45000);
        button.disabled = true;
        results.replaceChildren();
        empty.hidden = true;
        summary.textContent = 'Поиск платежей...';
        try {
            const response = await fetch(`${form.dataset.url}?${new URLSearchParams(filters)}`, {
                signal: currentController.signal, headers: {'Accept': 'application/json'}
            });
            if (response.redirected) throw new Error('Сессия завершена. Обновите страницу и войдите снова.');
            if (!(response.headers.get('content-type') || '').includes('application/json')) {
                throw new Error('Сервер вернул некорректный ответ. Обновите страницу и повторите поиск.');
            }
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'Не удалось выполнить поиск.');
            if (currentSequence === sequence) render(data);
        } catch (exc) {
            if (currentSequence === sequence) {
                showError(exc.name === 'AbortError'
                    ? 'Превышено время ожидания. Уточните период или другие фильтры.'
                    : (exc.message || 'Не удалось связаться с сервером.'));
                summary.textContent = 'Поиск не выполнен.';
            }
        } finally {
            clearTimeout(timer);
            if (currentSequence === sequence) {
                button.disabled = false;
                controller = null;
            }
        }
    });
    form.addEventListener('reset', () => {
        ++sequence;
        if (controller) controller.abort();
        controller = null;
        button.disabled = false;
        results.replaceChildren();
        empty.hidden = true;
        error.hidden = true;
        summary.textContent = initialSummary;
        setTimeout(updateRequired, 0);
    });
})();
