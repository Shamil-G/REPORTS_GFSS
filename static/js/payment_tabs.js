(() => {
    'use strict';
    const docTabs = document.getElementById('ps-doc-tabs');
    const results = document.getElementById('ps-results');
    if (!docTabs || !results) return;

    // Таб показывает панель из aria-controls и прячет панели соседних табов того же списка
    function select(tab) {
        const list = tab.closest('[role="tablist"]');
        for (const other of list.querySelectorAll('.ps-tab')) {
            const selected = other === tab;
            other.setAttribute('aria-selected', String(selected));
            document.getElementById(other.getAttribute('aria-controls')).hidden = !selected;
        }
    }

    document.querySelector('.payment-search').addEventListener('click', event => {
        const close = event.target.closest('.ps-tab-close');
        if (close) {
            const tab = close.previousElementSibling;
            const wasSelected = tab.getAttribute('aria-selected') === 'true';
            document.getElementById(tab.getAttribute('aria-controls')).remove();
            close.parentElement.remove();
            if (wasSelected) select(docTabs.querySelector('.ps-tab'));
            return;
        }
        const tab = event.target.closest('.ps-tab');
        if (tab) select(tab);
    });

    async function load(panel, id) {
        try {
            const response = await fetch(docTabs.dataset.url + encodeURIComponent(id));
            if (response.redirected) throw new Error('Сессия завершена. Обновите страницу и войдите снова.');
            if (!response.ok) {
                const data = (response.headers.get('content-type') || '').includes('application/json')
                    ? await response.json() : {};
                throw new Error(data.error || 'Не удалось открыть платеж.');
            }
            panel.innerHTML = await response.text();
        } catch (exc) {
            panel.replaceChildren();
            const error = document.createElement('p');
            error.className = 'ps-error';
            error.textContent = exc.message || 'Не удалось связаться с сервером.';
            panel.appendChild(error);
        }
    }

    function open(row) {
        const id = row.dataset.id;
        if (!id) return;
        const panelId = 'ps-doc-' + id;
        const existing = docTabs.querySelector(`[aria-controls="${panelId}"]`);
        if (existing) {
            select(existing);
            return;
        }
        const wrap = document.createElement('span');
        wrap.className = 'ps-tab-wrap';
        const tab = document.createElement('button');
        tab.type = 'button';
        tab.className = 'ps-tab';
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', panelId);
        tab.textContent = 'Платеж ' + (row.dataset.refer || id);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'ps-tab-close';
        close.setAttribute('aria-label', 'Закрыть');
        close.title = 'Закрыть';
        close.textContent = '×';
        wrap.append(tab, close);
        docTabs.appendChild(wrap);

        const panel = document.createElement('div');
        panel.id = panelId;
        panel.className = 'ps-panel';
        panel.setAttribute('role', 'tabpanel');
        panel.textContent = 'Загрузка платежа...';
        document.getElementById('ps-info').appendChild(panel);
        select(tab);
        load(panel, id);
    }

    results.addEventListener('click', event => {
        const row = event.target.closest('tr.ps-open');
        if (row) open(row);
    });
    results.addEventListener('keydown', event => {
        const row = event.target.closest('tr.ps-open');
        if (row && event.key === 'Enter') open(row);
    });
})();
