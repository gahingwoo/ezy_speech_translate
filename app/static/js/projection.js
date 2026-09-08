/* The screen at the front of the room.
 *
 * Not the listener page at a bigger size: the room reads one line at a time
 * from twenty metres away, so this shows the line being said now, the two
 * before it, and nothing else. It never scrolls — what does not fit is what
 * has already been said.
 *
 * Everything on it is read-only. There is nothing to press, no settings, and
 * no way in to the rest of the app: this is a display, and whoever is running
 * the service should never have to touch it once it is up.
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
const ROOM = params.get('room') || 'main';
const LANG = params.get('lang') || '';
const JOIN = params.get('join') || location.host;

/* The three lines on the stage, newest last. */
let recent = [];
let socket = null;

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
    el('projVerseText').textContent = slot.verses.map(v => v.text).join(' ');
    el('projVerse').hidden = false;
}

/* ── the foot ─────────────────────────────────────────────────────────────
   The address to read along at, and how many languages are waiting there.
   This is the only part of the screen anyone in the room can act on. */
function paintFoot(languageNames) {
    const dict = (window.sharedI18n || {}).en || {};
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

document.addEventListener('DOMContentLoaded', () => {
    if (params.get('theme') === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
        document.documentElement.classList.add('pf-v6-theme-dark');
        document.body.setAttribute('data-theme', 'dark');
    }
    const names = { en: 'English', zh: '简体中文', 'zh-tw': '繁體中文', yue: '粵語',
                    ja: '日本語', ko: '한국어', es: 'Español', fr: 'Français',
                    de: 'Deutsch', pt: 'Português', ru: 'Русский', ar: 'العربية',
                    hi: 'हिन्दी', th: 'ไทย', vi: 'Tiếng Việt', id: 'Bahasa Indonesia',
                    ms: 'Bahasa Melayu', tl: 'Tagalog', sm: 'Gagana Samoa',
                    to: 'Lea faka-Tonga', mi: 'Te Reo Māori' };
    el('projLang').textContent = LANG ? 'English → ' + (names[LANG] || LANG) : '';
    el('projRoom').textContent = ROOM === 'main' ? 'EzySpeech' : ROOM;
    paintFoot(Object.keys(names).filter(c => c !== 'en').map(c => names[c]));
    tickClock();
    setInterval(tickClock, 1000);
    connect();
});
