/* Таб «Карточка»: поиск получателя, список, общие сведения и назначения.
   Ожидаемый ответ эндпоинта (form.dataset.url, GET с параметрами формы):
   { items: [ { id, lastName, firstName, middleName, birthDate, iin, gender, rnn, regDate,
                birthPlace, address, department, document, status,
                regFio, workplace, regDepartment, firstRegDate,
                assignments: [ { type, region, status, dateFrom, dateTo, amount } ] } ],
     options?: { paymentType: [{value,label}], region: [...], status: [...] } } */
(() => {
    const root = document.getElementById('ps-card');
    if (!root) return;
    const form = root.querySelector('#pc-filters');
    const body = root.querySelector('#pc-results');
    const empty = root.querySelector('#pc-empty');
    const total = root.querySelector('#pc-total');
    const err = root.querySelector('#pc-error');
    const data = root.querySelector('#pc-data');
    const placeholder = root.querySelector('#pc-placeholder');
    const aBody = root.querySelector('#pc-assign-rows');
    const aEmpty = root.querySelector('#pc-assign-empty');
    const mode = root.querySelector('#pc-datemode');
    const from = root.querySelector('#pc-from');
    const to = root.querySelector('#pc-to');
    let items = [];

    const td = (text, cls) => { const c = document.createElement('td'); c.textContent = text ?? ''; if (cls) c.className = cls; return c; };
    const money = v => v == null || v === '' ? '' : Number(v).toLocaleString('ru-RU', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    const showError = m => { err.textContent = m || ''; err.hidden = !m; };

    // Вложенные табы «Общие сведения» / «Назначения»
    const tabs = [...root.querySelectorAll('.pc-tabs .ps-tab')];
    const select = tab => tabs.forEach(t => {
        const on = t === tab;
        t.setAttribute('aria-selected', on);
        t.tabIndex = on ? 0 : -1;
        root.querySelector('#' + t.getAttribute('aria-controls')).hidden = !on;
    });
    tabs.forEach(t => {
        t.addEventListener('click', () => select(t));
        t.addEventListener('keydown', e => {
            const i = tabs.indexOf(t);
            const n = e.key === 'ArrowRight' ? tabs[(i + 1) % tabs.length] : e.key === 'ArrowLeft' ? tabs[(i - 1 + tabs.length) % tabs.length] : null;
            if (n) { e.preventDefault(); select(n); n.focus(); }
        });
    });

    mode.addEventListener('change', () => {
        const on = mode.value === 'range';
        from.disabled = to.disabled = !on;
        if (!on) from.value = to.value = '';
    });

    function fillSelects(opts) {
        if (!opts) return;
        [['paymentType', 'pc-ptype'], ['region', 'pc-region'], ['status', 'pc-pstatus']].forEach(([k, id]) => {
            const sel = root.querySelector('#' + id);
            if (!sel || !opts[k] || sel.options.length > 1) return;
            opts[k].forEach(o => sel.add(new Option(o.label, o.value)));
        });
    }

    function show(i) {
        const p = items[i];
        [...body.rows].forEach((r, j) => r.setAttribute('aria-selected', j === i));
        if (!p) return;
        placeholder.hidden = true; data.hidden = false;
        data.querySelectorAll('[data-f]').forEach(el => { el.textContent = p[el.dataset.f] ?? ''; });
        aBody.replaceChildren();
        (p.assignments || []).forEach(a => {
            const tr = document.createElement('tr');
            tr.append(td(a.type), td(a.region), td(a.status), td(a.dateFrom), td(a.dateTo), td(money(a.amount), 'ps-money'));
            aBody.append(tr);
        });
        aEmpty.hidden = aBody.rows.length > 0;
    }

    function render(list) {
        items = list;
        body.replaceChildren();
        list.forEach((p, i) => {
            const tr = document.createElement('tr');
            tr.tabIndex = 0;
            tr.setAttribute('aria-selected', 'false');
            tr.append(td(i + 1), td(p.lastName), td(p.firstName), td(p.middleName), td(p.birthDate));
            tr.addEventListener('click', () => show(i));
            tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i); } });
            body.append(tr);
        });
        empty.hidden = list.length > 0;
        total.textContent = 'Всего: ' + list.length;
        data.hidden = true; placeholder.hidden = false;
        if (list.length === 1) show(0);
    }

    form.addEventListener('submit', async e => {
        e.preventDefault();
        showError('');
        const iin = form.iin.value.trim();
        if (iin && !/^\d{12}$/.test(iin)) return showError('ИИН состоит из 12 цифр.');
        if (mode.value === 'range' && from.value && to.value && from.value > to.value) return showError('Дата «с» позже даты «по».');
        const q = new URLSearchParams(new FormData(form));
        for (const [k, v] of [...q]) if (v === '') q.delete(k);
        try {
            const r = await fetch(form.dataset.url + '?' + q, { headers: { Accept: 'application/json' } });
            if (!r.ok) throw new Error(r.status);
            const j = await r.json();
            fillSelects(j.options);
            render(j.items || []);
        } catch {
            showError('Не удалось выполнить поиск. Повторите попытку.');
        }
    });

    form.addEventListener('reset', () => {
        setTimeout(() => { mode.dispatchEvent(new Event('change')); render([]); showError(''); });
    });
})();
