/* The listener page, part of: Marked lines.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did.

   A listener marks a line with the star at its end and finds it again under
   Reading > Marked lines, by service, newest first, to copy or save. Marks
   live on this phone only (localStorage), with no account and nothing sent to
   the server. Each keeps the words as they were shown when it was marked, so
   a screen cleared by the console, or a line corrected later, does not change
   or lose what was marked. */

const MARKS_KEY = 'ezyMarks_v1';

function _loadMarks() {
    try {
        const raw = JSON.parse(localStorage.getItem(MARKS_KEY) || '{}');
        return raw && typeof raw === 'object' ? raw : {};
    } catch (e) {
        return {};
    }
}

function _saveMarks(marks) {
    try {
        localStorage.setItem(MARKS_KEY, JSON.stringify(marks));
        return true;
    } catch (e) {
        showToast(t('mk_notSaved', 'This phone would not keep the mark'), 'warning', 3000);
        return false;
    }
}

function _localDay() {
    const d = new Date();
    return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-'
        + String(d.getDate()).padStart(2, '0');
}

/* A line is known by its room, the day it was said and its number in that
   room, which is how the server keeps it too: numbers carry on across days,
   so the day is there for the grouping, not to tell lines apart. */
function _markKey(item) {
    const room = item.room_id || window.CURRENT_ROOM_ID || 'main';
    return room + '|' + item.id;
}

function _itemById(id) {
    return translations.find(x => String(x.id) === String(id));
}

function isMarked(id) {
    const item = _itemById(id);
    return !!(item && _loadMarks()[_markKey(item)]);
}

function markButton(id) {
    const on = isMarked(id);
    const label = on ? t('mk_unmark', 'Unmark this line') : t('mk_mark', 'Mark this line');
    // PatternFly's favourite button: the outline and the filled star are both
    // there, and pf-m-favorited shows the filled one with its own small
    // animation.
    return '<button class="pf-v6-c-button pf-m-plain pf-m-favorite mark-btn' + (on ? ' pf-m-favorited' : '') + '"'
        + ' type="button" data-mark-id="' + escapeHtml(id) + '" aria-pressed="' + on + '"'
        + ' title="' + escapeHtml(label) + '" aria-label="' + escapeHtml(label) + '"'
        + ' onclick="toggleMark(this)"><span class="pf-v6-c-button__icon">'
        + '<span class="pf-v6-c-button__icon-favorite">' + svgIcon('outlined-star') + '</span>'
        + '<span class="pf-v6-c-button__icon-favorited">' + svgIcon('star') + '</span>'
        + '</span></button>';
}

function _paintMarkButton(button, on) {
    const label = on ? t('mk_unmark', 'Unmark this line') : t('mk_mark', 'Mark this line');
    button.classList.toggle('pf-m-favorited', on);
    button.setAttribute('aria-pressed', String(on));
    button.setAttribute('title', label);
    button.setAttribute('aria-label', label);
}

function toggleMark(button) {
    const item = _itemById(button.getAttribute('data-mark-id'));
    if (!item) return;
    const marks = _loadMarks();
    const key = _markKey(item);
    const on = !marks[key];
    if (on) {
        const said = item.corrected || item.original || '';
        const shown = displayMode === 'transcription' ? said : (item.translated || said);
        marks[key] = {
            room: item.room_id || window.CURRENT_ROOM_ID || 'main',
            day: (item.at || '').slice(0, 10) || _localDay(),
            time: item.timestamp || '',
            text: shown,
            said: shown !== said ? said : '',
            marked: Date.now(),
        };
    } else {
        delete marks[key];
    }
    if (!_saveMarks(marks)) return;
    _paintMarkButton(button, on);
    updateMarksCount();
}

function updateMarksCount() {
    const badge = document.getElementById('marksCount');
    if (!badge) return;
    const n = Object.keys(_loadMarks()).length;
    badge.textContent = String(n);
    badge.hidden = n === 0;
}

/* A line marked before its translation came keeps the words as said. Once the
   translation is on screen, the mark takes it, with the words as said under
   it, as if it had been marked a moment later. */
function _freshenMarks() {
    const marks = _loadMarks();
    let changed = false;
    translations.forEach(item => {
        const m = marks[_markKey(item)];
        if (!m || m.said || displayMode === 'transcription') return;
        const said = item.corrected || item.original || '';
        if (item.translated && m.text === said && item.translated !== said) {
            m.text = item.translated;
            m.said = said;
            changed = true;
        }
    });
    if (changed) _saveMarks(marks);
    return marks;
}

/* By service (day and room), newest service first, each in the order its
   lines were said. */
function _marksByService() {
    const groups = new Map();
    Object.entries(_freshenMarks()).forEach(([key, m]) => {
        const g = m.day + '|' + m.room;
        if (!groups.has(g)) groups.set(g, { day: m.day, room: m.room, lines: [] });
        groups.get(g).lines.push(Object.assign({ key: key }, m));
    });
    const list = [...groups.values()];
    list.sort((a, b) => (b.day + b.room).localeCompare(a.day + a.room));
    list.forEach(g => g.lines.sort((a, b) => (a.time || '').localeCompare(b.time || '') || a.marked - b.marked));
    return list;
}

function _dayLabel(day) {
    try {
        return new Date(day + 'T12:00:00').toLocaleDateString(displayLanguage || 'en', {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        });
    } catch (e) {
        return day;
    }
}

function _roomName(room) {
    const known = (window.__roomNames || {})[room];
    return known || (room === 'main' ? '' : room);
}

function renderMarks() {
    const body = document.getElementById('marksBody');
    const actions = document.getElementById('marksActions');
    if (!body) return;
    const groups = _marksByService();
    if (actions) actions.hidden = !groups.length;
    if (!groups.length) {
        body.innerHTML = '<p class="meta">' + escapeHtml(t('mk_empty',
            'No lines marked yet. Tap the star beside a line to keep it here.')) + '</p>';
        return;
    }
    body.innerHTML = groups.map(g => {
        const room = _roomName(g.room);
        return '<section class="marks-service">'
            + '<h2 class="pf-v6-c-title pf-m-md">' + escapeHtml(_dayLabel(g.day))
            + (room ? ' <span class="meta">' + escapeHtml(room) + '</span>' : '') + '</h2>'
            + '<dl class="pf-v6-c-description-list pf-m-horizontal-on-sm kv">'
            + g.lines.map(m => '<div class="pf-v6-c-description-list__group">'
                + '<dt class="pf-v6-c-description-list__term"><span class="pf-v6-c-description-list__text card-time">'
                + escapeHtml(m.time) + '</span></dt>'
                + '<dd class="pf-v6-c-description-list__description"><div class="pf-v6-c-description-list__text marks-line">'
                + '<div><p>' + escapeHtml(m.text) + '</p>'
                + (m.said ? '<span class="meta">' + escapeHtml(m.said) + '</span>' : '') + '</div>'
                + '<button class="pf-v6-c-button pf-m-plain" type="button" data-mark-key="' + escapeHtml(m.key) + '"'
                + ' onclick="removeMark(this)" title="' + escapeHtml(t('mk_remove', 'Remove')) + '"'
                + ' aria-label="' + escapeHtml(t('mk_remove', 'Remove')) + '">'
                + '<span class="pf-v6-c-button__icon">' + svgIcon('times') + '</span></button>'
                + '</div></dd></div>').join('')
            + '</dl></section>';
    }).join('');
}

function removeMark(button) {
    const marks = _loadMarks();
    delete marks[button.getAttribute('data-mark-key')];
    if (!_saveMarks(marks)) return;
    renderMarks();
    updateMarksCount();
    _repaintStars();
}

/* The stars on the lines on screen, after marks were changed from the list. */
function _repaintStars() {
    document.querySelectorAll('.mark-btn[data-mark-id]').forEach(b => {
        _paintMarkButton(b, isMarked(b.getAttribute('data-mark-id')));
    });
}

function _marksAsText() {
    return _marksByService().map(g => {
        const room = _roomName(g.room);
        return _dayLabel(g.day) + (room ? ' · ' + room : '') + '\n\n'
            + g.lines.map(m => (m.time ? m.time + '  ' : '') + m.text + (m.said ? '\n        ' + m.said : '')).join('\n');
    }).join('\n\n\n') + '\n';
}

function copyMarks() {
    const text = _marksAsText();
    const done = () => showToast(t('mk_copied', 'Marked lines copied'), 'success', 2000);
    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done).catch(() => _copyByHand(text, done));
    } else {
        _copyByHand(text, done);
    }
}

function _copyByHand(text, done) {
    const area = document.createElement('textarea');
    area.value = text;
    area.setAttribute('readonly', '');
    area.style.position = 'fixed';
    area.style.opacity = '0';
    document.body.appendChild(area);
    area.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { ok = false; }
    document.body.removeChild(area);
    if (ok) done();
    else showToast(t('mk_copyFailed', 'This browser would not copy; use Download text'), 'warning', 3000);
}

function downloadMarks() {
    const blob = new Blob([_marksAsText()], { type: 'text/plain;charset=utf-8' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'marked-lines-' + _localDay() + '.txt';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => { URL.revokeObjectURL(a.href); a.remove(); }, 1000);
}

function clearMarks() {
    if (!confirm(t('mk_clearConfirm', 'Remove every marked line from this phone?'))) return;
    if (!_saveMarks({})) return;
    renderMarks();
    updateMarksCount();
    _repaintStars();
}

function showMarks() {
    renderMarks();
    __openModal('marksModal');
}

function hideMarks(event) {
    if (event && event.target !== event.currentTarget) return;
    __closeModal('marksModal');
}

document.addEventListener('DOMContentLoaded', updateMarksCount);
// Written from script, so written again in a new language.
document.addEventListener('displaylanguagechange', function () {
    _repaintStars();
    if (document.getElementById('marksModal')?.classList.contains('active')) renderMarks();
});
// Another tab of the same page marking lines.
window.addEventListener('storage', function (e) {
    if (e.key !== MARKS_KEY) return;
    updateMarksCount();
    _repaintStars();
});
