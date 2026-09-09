/* The screen at the front of the room.
 *
 * Not the listener page at a bigger size: the room reads one line at a time
 * from twenty metres away, so this shows the line being said now, the two
 * before it, and nothing else. It never scrolls — what does not fit is what
 * has already been said.
 *
 * Once it is running there is nothing on it to press: it is a display, and
 * whoever is leading the service should never have to touch it. Before it is
 * running it has to be told three things, and it used to be told them by
 * hand-writing a query string. A wizard asks instead, on a screen that has
 * never been set up or when someone presses s, and writes its answers into
 * the address — so a screen can still be set up by pasting a URL, and the two
 * ways of doing it cannot disagree.
 *
 * Query parameters:
 *   ?room=main     which room to follow (default: main)
 *   ?lang=yue      the language to project (default: the room's own target,
 *                  falling back to the language of the transcript)
 *   ?join=...      the address shown at the foot for people to read along
 *   ?theme=dark    light ground by default, which is what most rooms project;
 *                  dark for a room that is genuinely dark
 */

const params = new URLSearchParams(location.search);

/* The address is what the screen is; anything it does not say is what this
   screen was told last time. A projector loses power, comes back on the same
   URL, and has to come back to the same room. */
function remembered(name) {
    try { return localStorage.getItem('proj.' + name) || ''; } catch (e) { return ''; }
}

function setting(name, fallback) {
    return params.get(name) || remembered(name) || fallback;
}

const ROOM = setting('room', 'main');
const LANG = setting('lang', '');
const JOIN = setting('join', location.host);
const THEME = setting('theme', 'light');
const CONFIGURED = !!(params.get('room') || params.get('lang')
                      || remembered('room') || remembered('lang'));

/* The three lines on the stage, newest last. */
let recent = [];
let socket = null;

/* What the speaker is speaking. Assumed English until a line says otherwise,
   which is what the room is told at the top of the screen. */
let sourceLang = 'en';

const el = id => document.getElementById(id);

/* ── the clock ────────────────────────────────────────────────────────────
   A service runs to a clock on the wall; this is that clock. */
function tickClock() {
    el('projClock').textContent = new Date().toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    });
}

/* ── the stage ────────────────────────────────────────────────────────────
   Three lines: the one being said, and the two before it, each quieter than
   the last. Nothing is removed until a fourth arrives, so the screen is never
   blank in a pause. */
function paint() {
    const [older, previous, now] = [recent[recent.length - 3], recent[recent.length - 2],
                                    recent[recent.length - 1]];
    el('projPast2').textContent = older ? older.text : '';
    el('projPast1').textContent = previous ? previous.text : '';
    el('projNow').textContent = now ? now.text : '';
    el('projSource').textContent = now && now.source !== now.text ? now.source : '';
}

function push(text, source) {
    if (!text) return;
    recent.push({ text: text, source: source || '' });
    if (recent.length > 3) recent.shift();
    paint();
}

/* ── scripture ────────────────────────────────────────────────────────────
   A verse stays up after the line that carried it has moved on: the room is
   still looking at it. It goes when the next verse comes, not when the next
   line does. */
/* Some Chinese Bibles are stored with a space between every character. That is
   typesetting, not reading, and on a projector it doubles the width of a
   verse. Same rule as the listener's. */
function tidyVerse(v) {
    return String((v && v.text) || '')
        .replace(/([\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])[ \t]+(?=[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])/g, '$1')
        .trim();
}

function showVerse(ref) {
    if (!ref) return;
    const slot = ref.target && ref.target.verses && ref.target.verses.length
        ? ref.target : ref.source;
    if (!slot || !slot.verses || !slot.verses.length) return;
    el('projVerseRef').textContent = ref.display || '';
    if (slot.translation) {
        const version = document.createElement('span');
        version.className = 'proj-verse-ver';
        version.textContent = slot.translation.toUpperCase();
        el('projVerseRef').appendChild(document.createTextNode(' '));
        el('projVerseRef').appendChild(version);
    }
    el('projVerseText').textContent = slot.verses.map(tidyVerse).join(' ');
    el('projVerse').hidden = false;
}

/* ── the language pair ────────────────────────────────────────────────────
   Which language is going in and which is coming out. When they are the same
   there is no translation happening and nothing to say about it: "English →
   English" is a label for a machine that is doing nothing, and the room does
   not need to read it for an hour. */
let LANG_NAMES = {};

function paintLangPair() {
    const label = el('projLang');
    if (!label) return;
    if (!LANG || sameLanguage(sourceLang, LANG)) {
        label.textContent = '';
        return;
    }
    const from = LANG_NAMES[sourceLang] || sourceLang;
    const to = LANG_NAMES[LANG] || LANG;
    label.textContent = from + ' \u2192 ' + to;
}

/* ── the foot ─────────────────────────────────────────────────────────────
   The address to read along at, and how many languages are waiting there.
   This is the only part of the screen anyone in the room can act on. */
function paintFoot(languageNames) {
    // The foot is read by the room, so it is in the room's language. It was
    // pinned to English while everything above it followed the projection.
    const table = window.sharedI18n || {};
    const dict = Object.assign({}, table.en || {}, (LANG && table[LANG]) || {});
    const join = document.createElement('span');
    join.textContent = (dict.projJoin || 'Read along in your own language') + ' — ';
    const address = document.createElement('strong');
    address.textContent = JOIN;
    el('projJoin').textContent = '';
    el('projJoin').appendChild(join);
    el('projJoin').appendChild(address);

    const shown = languageNames.slice(0, 4).join(' · ');
    const rest = languageNames.length - 4;
    el('projLangs').textContent = rest > 0
        ? shown + ' · ' + (dict.projMore || 'and %n more').replace('%n', String(rest))
        : shown;
}

/* ── the wire ─────────────────────────────────────────────────────────────
   The same room feed the listeners are on, read-only. */
function connect() {
    if (typeof io !== 'function') {
        // A screen in front of a congregation says nothing about its own
        // troubles; the log is where this belongs.
        console.error('projection: socket.io did not load, no feed');
        return;
    }
    socket = io({
        transports: ['websocket', 'polling'],
        query: { type: 'user', room: ROOM }
    });

    socket.on('connect', () => {
        document.body.classList.remove('is-offline');
    });
    socket.on('disconnect', () => {
        document.body.classList.add('is-offline');
    });

    socket.on('new_translation', async data => {
        const said = data.source_language || data.language || '';
        if (said && said !== sourceLang) {
            sourceLang = said;
            paintLangPair();
        }
        const source = data.corrected || data.original || '';
        let text = source;
        if (LANG && !sameLanguage(data.source_language || data.language || 'en', LANG)) {
            text = data.translated && data.translated_lang === LANG
                ? data.translated
                : await translate(source, LANG);
        }
        push(text, source);
        if (data.bible_refs && data.bible_refs.length) showVerse(data.bible_refs[0]);
    });

    socket.on('clear_history', () => {
        recent = [];
        paint();
        el('projVerse').hidden = true;
    });
}

/* Cantonese is written in traditional script but is its own language, so it
   has to be recognised before the script test. Same rule as the listener. */
function sameLanguage(a, b) {
    if (!a || !b) return false;
    const base = code => {
        const s = String(code).toLowerCase();
        if (s.startsWith('yue')) return 'yue';
        if (s.startsWith('zh-tw') || s.includes('-hant')) return 'zh-tw';
        if (s.startsWith('zh')) return 'zh';
        return s.split('-')[0];
    };
    return base(a) === base(b);
}

async function translate(text, target) {
    try {
        const res = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, target_lang: target })
        });
        const data = await res.json();
        return data.translated || text;
    } catch (err) {
        // A screen at the front of a room must never show an error to a
        // congregation: it falls back to the words that were actually said.
        console.error('projection translate failed', err);
        return text;
    }
}

/* ── setup ────────────────────────────────────────────────────────────────
   The wizard the room never sees. It opens on a screen that has not been set
   up, and on `s` for a screen that has: whoever is setting a projector up has
   a keyboard in front of them, and a gear in the corner would be one more
   thing for the congregation to look at all service. */
let projSetup = null;

function openSetup() {
    const modal = el('projSetupModal');
    if (!modal) return;
    // The wizard is read in the language the screen projects, not in whatever
    // this browser last stored for the listener page: the person setting a
    // projector up in a Cantonese service reads Cantonese.
    if (window.applyDisplayLanguage) window.applyDisplayLanguage(LANG || 'en');
    el('projSetupLang').value = LANG || 'en';
    el('projSetupTheme').value = THEME;
    el('projSetupJoin').textContent = JOIN;
    fillRooms();
    projSetup.show('room');
    modal.classList.add('active');
}

function closeSetup() {
    const modal = el('projSetupModal');
    if (modal) modal.classList.remove('active');
}

/* The rooms this server actually has, so nobody has to know a room's id to
   point a screen at it. If the list cannot be fetched the field keeps Main,
   which is the room every install starts with. */
async function fillRooms() {
    const select = el('projSetupRoom');
    if (!select) return;
    try {
        const res = await fetch('/api/rooms');
        const data = await res.json();
        const rooms = (data && data.rooms) || [];
        if (!rooms.length) return;
        select.textContent = '';
        rooms.forEach(function (room) {
            const option = document.createElement('option');
            option.value = room.room_id;
            option.textContent = room.display_name || room.room_id;
            select.appendChild(option);
        });
    } catch (err) {
        console.warn('room list unavailable', err);
    }
    select.value = ROOM;
}

/* Answers go to both places: stored, so the screen comes back to itself after
   a power cut, and into the address, so what is on screen is what the URL
   says and a second screen can be set up by copying it. */
function applySetup() {
    const room = el('projSetupRoom').value || 'main';
    const lang = el('projSetupLang').value || '';
    const theme = el('projSetupTheme').value || 'light';
    try {
        localStorage.setItem('proj.room', room);
        localStorage.setItem('proj.lang', lang);
        localStorage.setItem('proj.theme', theme);
    } catch (e) {}
    const url = new URL(location.href);
    url.searchParams.set('room', room);
    url.searchParams.set('lang', lang);
    url.searchParams.set('theme', theme);
    url.searchParams.delete('setup');
    location.href = url.toString();
}

document.addEventListener('DOMContentLoaded', () => {
    if (THEME === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.classList.add('pf-v6-theme-dark');
        document.body.setAttribute('data-theme', 'dark');
    }
    projSetup = Wizard('projSetup', ['room', 'language', 'look', 'done'], applySetup);
    window.projSetup = projSetup;
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { closeSetup(); return; }
        // Not while a field has the caret: s is a letter before it is a key.
        const tag = (e.target && e.target.tagName) || '';
        if (tag === 'INPUT' || tag === 'SELECT' || tag === 'TEXTAREA') return;
        if (e.key === 's' || e.key === 'S') openSetup();
    });
    const names = { en: 'English', zh: '简体中文', 'zh-tw': '繁體中文', yue: '粵語',
                    ja: '日本語', ko: '한국어', es: 'Español', fr: 'Français',
                    de: 'Deutsch', pt: 'Português', ru: 'Русский', ar: 'العربية',
                    hi: 'हिन्दी', th: 'ไทย', vi: 'Tiếng Việt', id: 'Bahasa Indonesia',
                    ms: 'Bahasa Melayu', tl: 'Tagalog', sm: 'Gagana Samoa',
                    to: 'Lea faka-Tonga', mi: 'Te Reo Māori' };
    LANG_NAMES = names;
    paintLangPair();
    el('projRoom').textContent = ROOM === 'main' ? 'EzySpeech' : ROOM;
    paintFoot(Object.keys(names).filter(c => c !== 'en').map(c => names[c]));
    tickClock();
    setInterval(tickClock, 1000);
    // A screen nobody has told anything asks; one that has been set up goes
    // straight to work, which is what it is for. Asking comes first: if the
    // feed cannot be reached, the way to fix it is still on screen.
    if (!CONFIGURED || params.get('setup') === '1') openSetup();
    connect();
});
