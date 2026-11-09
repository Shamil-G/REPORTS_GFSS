(() => {
    'use strict';

    const form = document.getElementById('payment-filters');
    const button = document.getElementById('ps-export');

    if (!form || !button) return;

    const error = document.getElementById('ps-error');
    let filters = null;      // фильтры последнего поиска: сервер выполняет запрос заново
    let exporting = false;

    // Выгрузка доступна, если что-то найдено и результат не усечён лимитом
    document.addEventListener('payment-search-results', event => {
        const d = event.detail;
        filters = (d.total > 0 && !d.truncated) ? d.filters : null;
        button.disabled = exporting || !filters;
    });

    const clear = () => {
        filters = null;
        button.disabled = true;
    };

    form.addEventListener('submit', clear);
    form.addEventListener('reset', clear);

    button.addEventListener('click', async () => {
        if (!filters || exporting) return;

        const params = new URLSearchParams(filters);
        exporting = true;
        button.disabled = true;
        error.hidden = true;

        try {
            const response = await fetch(`${button.dataset.url}?${params}`);

            if (response.redirected) {
                throw new Error(
                    'Сессия завершена. Обновите страницу и войдите снова.'
                );
            }

            const contentType = response.headers.get('content-type') || '';

            if (!response.ok) {
                const data = contentType.includes('application/json')
                    ? await response.json()
                    : {};

                throw new Error(
                    data.error || 'Не удалось выгрузить Excel.'
                );
            }

            if (!contentType.includes(
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )) {
                throw new Error('Сервер вернул некорректный ответ.');
            }

            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');

            link.href = url;
            link.download = 'payments.xlsx';

            document.body.appendChild(link);
            link.click();
            link.remove();

            setTimeout(() => URL.revokeObjectURL(url), 60000);
        } catch (exc) {
            error.textContent = exc.message || 'Не удалось выгрузить Excel.';
            error.hidden = false;
        } finally {
            exporting = false;
            button.disabled = !filters;
        }
    });
})();