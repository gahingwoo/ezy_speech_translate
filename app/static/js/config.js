/* Settings page.
 *
 * Reads config/config.yaml through /api/config/fields and writes back only the
 * fields that changed. The endpoint refuses a path that is not already in the
 * file and refuses any path ending in a secret, so nothing here can reach
 * config/secrets.key or drop a setting this page does not render.
 *
 * Every control carries its dotted path in data-config-path; that attribute is
 * the whole mapping between the form and the file.
 */

let authToken = null;
let original = {};           // path -> value as the server last gave it
const MAX_VISIBLE_TOASTS = 4;

/* ── plumbing ─────────────────────────────────────────────────────────── */

function svgIcon(name, cls) {
    return '<svg class="pf-v6-svg' + (cls ? ' ' + cls : '') + '" aria-hidden="true"'
        + ' role="img" width="1em" height="1em" fill="currentColor">'
        + '<use href="#i-' + name + '"></use></svg>';
}

function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 4000;
    const container = document.getElementById('toastContainer');
    if (!container) { console.log('[toast]', type, message); return; }
    while (container.children.length >= MAX_VISIBLE_TOASTS) container.firstChild.remove();

    const ICONS = {
        info: 'info-circle', success: 'check-circle',
        warning: 'exclamation-triangle', danger: 'exclamation-circle',
    };
    const item = document.createElement('li');
    item.className = 'pf-v6-c-alert-group__item';

    const alert = document.createElement('div');
    alert.className = 'pf-v6-c-alert pf-m-' + type;
    alert.setAttribute('role', type === 'danger' ? 'alert' : 'status');

    const icon = document.createElement('div');
    icon.className = 'pf-v6-c-alert__icon';
    icon.innerHTML = svgIcon(ICONS[type] || ICONS.info);

    const title = document.createElement('p');
    title.className = 'pf-v6-c-alert__title';
    title.textContent = message;

    const action = document.createElement('div');
    action.className = 'pf-v6-c-alert__action';
    const close = document.createElement('button');
    close.className = 'pf-v6-c-button pf-m-plain';
    close.type = 'button';
    close.setAttribute('aria-label', 'Close alert');
    close.innerHTML = '<span class="pf-v6-c-button__icon">' + svgIcon('times') + '</span>';
    close.onclick = function () { item.remove(); };
    action.appendChild(close);

    alert.append(icon, title, action);
    item.appendChild(alert);
    container.appendChild(item);

    item.classList.add('pf-m-offstage-right');
    requestAnimationFrame(function () {
        item.classList.remove('pf-m-offstage-right');
        item.classList.add('pf-m-incoming');
    });
    setTimeout(function () {
        item.classList.add('pf-m-outgoing');
        setTimeout(function () { item.remove(); }, 300);
    }, duration);
}

async function api(url, opts = {}) {
    opts.headers = Object.assign(
        { 'Content-Type': 'application/json' },
        opts.headers || {},
        authToken ? { 'Authorization': 'Bearer ' + authToken } : {}
    );
    const resp = await fetch(url, opts);
    let data = {};
    try { data = await resp.json(); } catch (_) { /* noop */ }
    if (!resp.ok || data.success === false) {
        const err = new Error(data.error || ('HTTP ' + resp.status));
        err.fields = data.errors || null;
        throw err;
    }
    return data;
}

async function sha256Hex(str) {
    const buf = new TextEncoder().encode(str);
    const digest = await window.crypto.subtle.digest('SHA-256', buf);
    return Array.from(new Uint8Array(digest))
        .map(b => b.toString(16).padStart(2, '0')).join('');
}

function jwtUsername() {
    try {
        const payload = JSON.parse(atob(
            authToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
        ));
        return payload.username || 'admin';
    } catch (_) { return 'admin'; }
}

function logout() {
    localStorage.removeItem('authToken');
    window.location.href = '/login';
}
window.logout = logout;

/* ── the gate ─────────────────────────────────────────────────────────── */
/* The API already requires a token; this is the same second look the dashboard
   took before opening the file, kept so a signed-in machine left unattended
   does not hand over the server's settings. */

function showGate() {
    const modal = document.getElementById('configPasswordModal');
    modal.classList.add('active');
    const input = document.getElementById('configPasswordInput');
    if (input) { input.value = ''; setTimeout(() => input.focus(), 50); }
}

function cancelConfigGate() {
    window.location.href = '/admin';
}
window.cancelConfigGate = cancelConfigGate;

async function confirmConfigGate() {
    const input = document.getElementById('configPasswordInput');
    const password = input ? input.value : '';
    if (!password) { showToast('Enter your password', 'warning'); return; }

    let hash;
    try { hash = await sha256Hex(password); }
    catch (e) { showToast('Could not hash the password: ' + e.message, 'danger'); return; }

    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: jwtUsername(), password_hash: hash }),
        });
        if (!resp.ok) {
            showToast('Wrong password', 'danger');
            if (input) { input.value = ''; input.focus(); }
            return;
        }
        document.getElementById('configPasswordModal').classList.remove('active');
        await loadConfig();
    } catch (e) {
        showToast('Request failed: ' + e.message, 'danger');
    }
}
window.confirmConfigGate = confirmConfigGate;

/* ── the fields ───────────────────────────────────────────────────────── */

function fields() {
    return Array.from(document.querySelectorAll('[data-config-path]'));
}

function at(config, path) {
    let node = config;
    for (const part of path.split('.')) {
        if (node === null || typeof node !== 'object' || !(part in node)) return undefined;
        node = node[part];
    }
    return node;
}

function readControl(el) {
    if (el.type === 'checkbox') return el.checked;
    if (el.type === 'number') {
        if (el.value.trim() === '') return null;
        const n = Number(el.value);
        return Number.isFinite(n) ? n : el.value;
    }
    return el.value;
}

function writeControl(el, value) {
    if (el.type === 'checkbox') { el.checked = value === true; return; }
    el.value = (value === null || value === undefined) ? '' : String(value);
}

/* A field counts as changed only if the value differs once both sides are read
   the same way; an empty text box and a null in the file are the same thing. */
function same(a, b) {
    if (a === b) return true;
    const blank = v => v === null || v === undefined || v === '';
    if (blank(a) && blank(b)) return true;
    return String(a) === String(b);
}

function changed() {
    const out = {};
    fields().forEach(function (el) {
        const path = el.dataset.configPath;
        const value = readControl(el);
        if (!same(value, original[path])) out[path] = value;
    });
    return out;
}

function refreshDirtyState() {
    const diff = changed();
    const count = Object.keys(diff).length;
    const bar = document.getElementById('configActions');
    const label = document.getElementById('configDirtyCount');
    bar.hidden = count === 0;
    label.textContent = count === 1 ? '1 unsaved change'
        : count + ' unsaved changes';
    fields().forEach(function (el) {
        const group = el.closest('.pf-v6-c-form__group');
        if (group) group.classList.toggle('is-changed', el.dataset.configPath in diff);
    });
}

async function loadConfig() {
    let data;
    try {
        data = await api('/api/config/fields');
    } catch (e) {
        showToast('Could not read the settings: ' + e.message, 'danger', 8000);
        return;
    }
    const config = data.config || {};
    const pathEl = document.getElementById('configPath');
    if (pathEl && data.path) pathEl.textContent = data.path;

    original = {};
    fields().forEach(function (el) {
        const path = el.dataset.configPath;
        const value = at(config, path);
        original[path] = value === undefined ? null : value;
        writeControl(el, original[path]);
        const group = el.closest('.pf-v6-c-form__group');
        if (group) group.hidden = value === undefined;
    });
    refreshDirtyState();
}

async function saveChanges() {
    const diff = changed();
    if (!Object.keys(diff).length) return;
    const button = document.getElementById('configSaveButton');
    button.disabled = true;
    try {
        const data = await api('/api/config/fields', {
            method: 'POST',
            body: JSON.stringify({ changes: diff }),
        });
        Object.assign(original, data.applied || diff);
        refreshDirtyState();
        showToast(data.message || 'Saved.', 'success', 6000);
    } catch (e) {
        if (e.fields) {
            Object.entries(e.fields).forEach(function ([path, why]) {
                const el = document.querySelector('[data-config-path="' + path + '"]');
                const group = el && el.closest('.pf-v6-c-form__group');
                if (group) group.classList.add('is-invalid');
                showToast(path + ': ' + why, 'danger', 8000);
            });
        } else {
            showToast('Could not save: ' + e.message, 'danger', 8000);
        }
    } finally {
        button.disabled = false;
    }
}
window.saveChanges = saveChanges;

function discardChanges() {
    fields().forEach(function (el) {
        writeControl(el, original[el.dataset.configPath]);
        const group = el.closest('.pf-v6-c-form__group');
        if (group) group.classList.remove('is-invalid');
    });
    refreshDirtyState();
}
window.discardChanges = discardChanges;

/* ── the file, for anything the fields above do not cover ─────────────── */

function toggleRawEditor() {
    const card = document.getElementById('rawEditorCard');
    const body = document.getElementById('rawEditorBody');
    const toggle = document.getElementById('rawEditorToggle');
    const open = !card.classList.contains('pf-m-expanded');
    card.classList.toggle('pf-m-expanded', open);
    toggle.setAttribute('aria-expanded', String(open));
    body.hidden = !open;
    if (open) loadRawConfig();
}
window.toggleRawEditor = toggleRawEditor;

async function loadRawConfig() {
    const textarea = document.getElementById('configEditorTextarea');
    textarea.value = 'Loading…';
    try {
        const data = await api('/api/config/raw');
        textarea.value = data.yaml || '';
    } catch (e) {
        textarea.value = '# Could not read the file: ' + e.message;
    }
}

async function saveRawConfig() {
    const textarea = document.getElementById('configEditorTextarea');
    if (!confirm('This rewrites config.yaml and drops its comments. Continue?')) return;
    try {
        const data = await api('/api/config/raw', {
            method: 'POST',
            body: JSON.stringify({ yaml: textarea.value }),
        });
        showToast(data.message || 'Saved.', 'success', 6000);
        await loadConfig();
    } catch (e) {
        showToast('Could not save: ' + e.message, 'danger', 8000);
    }
}
window.saveRawConfig = saveRawConfig;

/* ── start ────────────────────────────────────────────────────────────── */

document.addEventListener('DOMContentLoaded', function () {
    const theme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', theme);
    document.documentElement.classList.toggle('pf-v6-theme-dark', theme === 'dark');

    authToken = localStorage.getItem('authToken');
    if (!authToken) { window.location.href = '/login'; return; }

    fields().forEach(function (el) {
        el.addEventListener('input', function () {
            const group = el.closest('.pf-v6-c-form__group');
            if (group) group.classList.remove('is-invalid');
            refreshDirtyState();
        });
        el.addEventListener('change', refreshDirtyState);
    });

    window.addEventListener('beforeunload', function (e) {
        if (Object.keys(changed()).length) { e.preventDefault(); e.returnValue = ''; }
    });

    showGate();
});
