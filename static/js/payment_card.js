/* Таб «Карточка»: поиск получателя в LOADER.PERSON (GET /payment-search/card/data).
   Фильтры: iin, lastname, firstname, middlename, birthdate. Ответ:
   { items: [ { sicid, iin, lastname, ..., regfio } ], truncated, limit } (поля - см. COLUMNS в model/payment_card.py)
   Ошибки приходят как { error } с кодом 4xx/5xx. Остальные поля «Общих сведений» и
   «Назначения» заполняются, когда бэк начнёт их отдавать (data-f в card_panel.html). */
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
    let selected = -1;
    const openBtn = root.querySelector('#pc-open-info');

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

    // Блок «Любая дата / Дата с - по» бэком пока не используется; если его убрали из разметки - не падаем
    if (mode && from && to) {
        mode.addEventListener('change', () => {
            const on = mode.value === 'range';
            from.disabled = to.disabled = !on;
            if (!on) from.value = to.value = '';
        });
    }

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
        selected = i;
        if (openBtn) openBtn.disabled = !p.sicid;
        placeholder.hidden = true; data.hidden = false;
        data.querySelectorAll('[data-f]').forEach(el => { el.textContent = p[el.dataset.f] ?? ''; });
        // «Назначения» - в разработке: таблица появится в разметке позже
        if (aBody) {
            aBody.replaceChildren();
            (p.assignments || []).forEach(a => {
                const tr = document.createElement('tr');
                tr.append(td(a.type), td(a.region), td(a.status), td(a.dateFrom), td(a.dateTo), td(money(a.amount), 'ps-money'));
                aBody.append(tr);
            });
            if (aEmpty) aEmpty.hidden = aBody.rows.length > 0;
        }
    }

    function render(list, truncated, limit) {
        items = list;
        body.replaceChildren();
        list.forEach((p, i) => {
            const tr = document.createElement('tr');
            tr.tabIndex = 0;
            tr.setAttribute('aria-selected', 'false');
            tr.append(td(i + 1), td(p.lastname), td(p.firstname), td(p.middlename), td(p.birthdate));
            tr.addEventListener('click', () => show(i));
            tr.addEventListener('dblclick', () => { show(i); openInfo(); });
            tr.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); show(i); } });
            body.append(tr);
        });
        empty.hidden = list.length > 0;
        total.textContent = 'Всего: ' + list.length + (truncated ? ' (показаны первые ' + limit + ', уточните фильтры)' : '');
        selected = -1;
        if (openBtn) openBtn.disabled = true;
        data.hidden = true; placeholder.hidden = false;
        if (list.length === 1) show(0);
    }

    const button = form.querySelector('button[type="submit"]');
    let controller = null;
    let sequence = 0;

    form.addEventListener('submit', async e => {
        e.preventDefault();
        showError('');
        const f = Object.fromEntries(new FormData(form));
        const iin = (f.iin || '').trim();
        if (iin && !/^\d{12}$/.test(iin)) return showError('ИИН состоит из 12 цифр.');
        if (!iin && !(f.lastname || '').trim()) return showError('Укажите ИИН или фамилию.');
        const q = new URLSearchParams();
        ['iin', 'lastname', 'firstname', 'middlename', 'birthdate'].forEach(k => { if ((f[k] || '').trim()) q.set(k, f[k].trim()); });

        if (controller) controller.abort();
        const current = new AbortController();
        controller = current;
        const seq = ++sequence;
        const timer = setTimeout(() => current.abort(), 45000);
        button.disabled = true;
        total.textContent = 'Поиск...';
        try {
            const r = await fetch(form.dataset.url + '?' + q, { signal: current.signal, headers: { Accept: 'application/json' } });
            if (r.redirected) throw new Error('Сессия завершена. Обновите страницу и войдите снова.');
            if (!(r.headers.get('content-type') || '').includes('application/json'))
                throw new Error('Сервер вернул некорректный ответ. Обновите страницу и повторите поиск.');
            const j = await r.json();
            if (!r.ok) throw new Error(j.error || 'Не удалось выполнить поиск.');
            if (seq === sequence) { fillSelects(j.options); render(j.items || [], j.truncated, j.limit); }
        } catch (exc) {
            if (seq === sequence) {
                showError(exc.name === 'AbortError' ? 'Превышено время ожидания. Уточните фильтры.' : (exc.message || 'Не удалось связаться с сервером.'));
                total.textContent = 'Поиск не выполнен.';
            }
        } finally {
            clearTimeout(timer);
            if (seq === sequence) { button.disabled = false; controller = null; }
        }
    });

    form.addEventListener('reset', () => {
        ++sequence;
        if (controller) controller.abort();
        controller = null;
        button.disabled = false;
        setTimeout(() => { if (mode) mode.dispatchEvent(new Event('change')); render([], false, 0); showError(''); });
    });

    // ---- Таб «Информация участнику»: новая вкладка в полосе «Открытые документы» ----
    const strip = document.getElementById('ps-doc-tabs');
    const PREFIX = 'ps-pinfo-';

    function activate(tab) {
        strip.querySelectorAll('.ps-tab').forEach(t => {
            const on = t === tab;
            t.setAttribute('aria-selected', on);
            const panel = document.getElementById(t.getAttribute('aria-controls'));
            if (panel) panel.hidden = !on;
        });
    }

    async function openInfo() {
        const p = items[selected];
        if (!p || !p.sicid || !strip) return;
        // сначала переходим на раздел «Информация по отчислениям и назначениям»
        const outer = document.querySelector('[role="tab"][aria-controls="ps-info"]');
        if (outer && outer.getAttribute('aria-selected') !== 'true') outer.click();

        const id = PREFIX + p.sicid;
        const existing = strip.querySelector(`[aria-controls="${id}"]`);
        if (existing) return activate(existing);

        const wrap = document.createElement('span');
        wrap.className = 'ps-tab-wrap';
        const tab = document.createElement('button');
        tab.type = 'button';
        tab.className = 'ps-tab';
        tab.setAttribute('role', 'tab');
        tab.setAttribute('aria-controls', id);
        tab.setAttribute('aria-selected', 'false');
        tab.textContent = 'Информация: ' + (p.lastname || p.iin || p.sicid);
        const close = document.createElement('button');
        close.type = 'button';
        close.className = 'ps-tab-close';
        close.setAttribute('aria-label', 'Закрыть вкладку');
        close.textContent = '×';
        wrap.append(tab, close);
        strip.append(wrap);

        const panel = document.createElement('div');
        panel.id = id;
        panel.className = 'ps-panel pc-info-panel';
        panel.setAttribute('role', 'tabpanel');
        panel.innerHTML = '<div class="ps-empty"><strong>Загрузка...</strong></div>';
        strip.parentNode.append(panel);
        activate(tab);

        close.addEventListener('click', () => {
            const wasActive = tab.getAttribute('aria-selected') === 'true';
            const next = wrap.previousElementSibling?.querySelector('.ps-tab') || wrap.previousElementSibling || strip.querySelector('.ps-tab');
            wrap.remove();
            panel.remove();
            if (wasActive && next) next.click();
        });

        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 45000);
        try {
            const r = await fetch(`${form.dataset.infoUrl}${p.sicid}/info`, { signal: ctrl.signal });
            if (r.redirected) throw new Error('Сессия завершена. Обновите страницу и войдите снова.');
            const type = r.headers.get('content-type') || '';
            if (!r.ok) {
                const j = type.includes('application/json') ? await r.json() : {};
                throw new Error(j.error || 'Не удалось получить данные.');
            }
            if (!type.includes('text/html')) throw new Error('Сервер вернул некорректный ответ.');
            panel.innerHTML = await r.text();   // фрагмент формирует сервер (Jinja экранирует значения)
        } catch (exc) {
            const msg = document.createElement('div');
            msg.className = 'ps-empty';
            const b = document.createElement('strong');
            b.textContent = exc.name === 'AbortError' ? 'Превышено время ожидания.' : (exc.message || 'Не удалось связаться с сервером.');
            msg.append(b);
            panel.replaceChildren(msg);
        } finally {
            clearTimeout(timer);
        }
    }

    if (openBtn) openBtn.addEventListener('click', openInfo);

    // Клик по любой другой вкладке этой полосы: свои панели скрываем (остальными управляет payment_tabs.js)
    if (strip) strip.addEventListener('click', e => {
        const t = e.target.closest('.ps-tab');
        if (!t) return;
        const mine = (t.getAttribute('aria-controls') || '').startsWith(PREFIX);
        if (mine) return activate(t);
        strip.querySelectorAll('.ps-tab').forEach(x => {
            if ((x.getAttribute('aria-controls') || '').startsWith(PREFIX)) {
                x.setAttribute('aria-selected', 'false');
                const panel = document.getElementById(x.getAttribute('aria-controls'));
                if (panel) panel.hidden = true;
            }
        });
    });
})();
