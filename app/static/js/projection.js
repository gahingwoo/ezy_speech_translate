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

/* A projector in a hall is nobody's accessibility setting, but the machine
   driving it may still carry one, and a room that has asked for less motion
   should not be typed at. */
const REDUCED_MOTION = (function () {
    try {
        return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) {
        return false;
    }
})();

const el = id => document.getElementById(id);

/* ── the clock ────────────────────────────────────────────────────────────
   A service runs to a clock on the wall; this is that clock. */
function tickClock() {
    el('projClock').textContent = new Date().toLocaleTimeString([], {
        hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false
    });
}

/* ── fitting the stage ────────────────────────────────────────────────────
   The line being said is set to read from the back of a room, which means a
   long sentence does not fit. The stage centres what is in it and the page
   cannot scroll, so anything over the height was clipped at both ends and the
   end of the sentence went missing off the bottom of the screen.

   So the type is sized to the sentence: start at what the stylesheet asks for
   and come down until the whole thing is on the screen. Never below the size
   of the quiet lines above it, because a sentence nobody at the back can read
   is no better than one they cannot see the end of. */
const NOW_MAX_REM = 4.25;
const NOW_MIN_REM = 2;
let nowText = '';

function stageContentHeight(stage) {
    /* Not scrollHeight: the stage centres its children, so a browser counts
       only what hangs off the bottom and the top of a long sentence is missed.
       Measure the children instead. */
    const kids = Array.prototype.filter.call(stage.children,
        k => !k.hidden && k.offsetParent !== null);
    if (!kids.length) return 0;
    const gap = parseFloat(getComputedStyle(stage).rowGap) || 0;
    let h = gap * (kids.length - 1);
    kids.forEach(k => {
        const cs = getComputedStyle(k);
        // scrollHeight, not the box. These are flex items and they shrink, so
        // the boxes always add up to the height of the stage however much text
        // is in them: measuring those said every sentence fitted while the
        // words ran off the bottom of the screen.
        h += Math.max(k.scrollHeight, k.getBoundingClientRect().height)
           + (parseFloat(cs.marginTop) || 0)
           + (parseFloat(cs.marginBottom) || 0);
    });
    return h;
}

/* Sized against the finished sentence rather than whatever the typewriter has
   reached, so the room does not watch the text shrink as it arrives. */
function fitNow(text) {
    const stage = document.querySelector('.proj-stage');
    const now = el('projNow');
    if (!stage || !now) return;
    nowText = text;
    // On the first paint the stage has not been laid out yet and measures
    // nothing, and a height of zero makes every sentence look too long. Wait a
    // frame rather than shrinking the type to its floor for no reason.
    if (stage.clientHeight <= 0) {
        window.requestAnimationFrame(function () { fitNow(text); });
        return;
    }
    const showing = now.textContent;
    now.style.minHeight = '';
    now.textContent = text;
    // Every paint starts from the whole stage and the largest type, so a short
    // line after a long one gets its size and its history back.
    const past = [el('projPast1'), el('projPast2')].filter(Boolean);
    past.forEach(k => { k.hidden = false; });
    // Any line mid-animation is holding a height for the typewriter; measuring
    // that instead of its text would size this one against the last one.
    Array.prototype.forEach.call(stage.querySelectorAll('[style*="min-height"]'),
        k => { if (k !== now) k.style.minHeight = ''; });
    let size = NOW_MAX_REM;
    now.style.fontSize = size + 'rem';

    // What gives way first is the history, oldest line then the other. Those
    // two are there so the screen is not blank in a pause; they have already
    // been read, and a long one of them is no reason to shrink the sentence
    // the room is reading right now.
    for (let i = past.length - 1; i >= 0 && stageContentHeight(stage) > stage.clientHeight; i--) {
        past[i].hidden = true;
    }
    // Only then the type, and never below the size those quiet lines were:
    // a sentence nobody at the back can read is no better than one whose end
    // they cannot see.
    while (size > NOW_MIN_REM && stageContentHeight(stage) > stage.clientHeight) {
        size = Math.max(NOW_MIN_REM, size - 0.25);
        now.style.fontSize = size + 'rem';
    }
    now.textContent = showing;
}

/* The height available changes too: a window resized, or the scripture panel
   opening under the line and taking a third of the screen with it. */
function refitNow() { fitNow(nowText); }

/* ── the stage ────────────────────────────────────────────────────────────
   Three lines: the one being said, and the two before it, each quieter than
   the last. Nothing is removed until a fourth arrives, so the screen is never
   blank in a pause. */
function paint() {
    const [older, previous, now] = [recent[recent.length - 3], recent[recent.length - 2],
                                    recent[recent.length - 1]];
    // The two lines above have already been read; they move up in place. Only
    // the line being said is typed, because that is the one the room is
    // reading as it arrives.
    el('projPast2').textContent = older ? older.text : '';
    el('projPast1').textContent = previous ? previous.text : '';
    say('projSource', now && now.source !== now.text ? now.source : '');
    // Sized before it is typed, so the size is right from the first frame.
    fitNow(now ? now.text : '');
    say('projNow', now ? now.text : '');
}

/* Type into one of the stage lines. The typewriter only types what is new, so
   an interim transcription that grows a word at a time grows on screen rather
   than being retyped from its first letter every time. */
function say(id, text) {
    const node = el(id);
    if (!node) return;
    if (typeof animateTextChange !== 'function' || REDUCED_MOTION) {
        node.textContent = text;
        return;
    }
    animateTextChange(node, node.textContent, text, 400);
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
    refitNow();
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
function paintFoot() {
    // The address, and nothing else. A list of four language names and "and 16
    // more" told the room nothing it could act on — the address is where the
    // languages are, and naming a few of them only crowded the foot of a wall
    // that is mostly meant to be read from twenty metres away.
    //
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

    /* What is being said right now, before the sentence is finished. The room
       sees the words arrive instead of waiting for a pause and then being
       handed a paragraph. It is the speaker's own words, so it goes on the
       quiet line under the translation — unless no translation is happening,
       in which case that quiet line is the line. */
    socket.on('realtime_transcription', data => {
        const said = data.original || data.text || '';
        if (!said) return;
        const translating = LANG && !sameLanguage(sourceLang, LANG);
        if (translating) {
            say('projSource', said);
            return;
        }
        // Where nothing is being translated this quiet line is the line, and
        // it grows a word at a time as the speaker talks. It has to be sized
        // like any other: paint() fits what it writes, but this path never went
        // through paint(), so a sentence that outgrew the screen mid-speech was
        // clipped until the moment it finished and paint() finally sized it.
        // The room watched the end of a long sentence disappear off the bottom
        // and come back a second later, smaller.
        fitNow(said);
        say('projNow', said);
    });

    socket.on('clear_history', () => {
        recent = [];
        paint();
        el('projVerse').hidden = true;
        refitNow();
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

    /* The cursor. projection.css hides it, because one left on a projector is
       a white arrow on the wall for the whole service. But the gear in the
       corner and every control in the wizard have to be clickable, and a
       pointer nobody can see cannot be aimed. Bring it back whenever the mouse
       moves and take it away again once the mouse has been still, which on a
       screen at the front of a room means the operator has walked off. The
       stylesheet holds it open for as long as the wizard is, however still it
       is held. */
    window.addEventListener('resize', refitNow);

    let cursorIdle = null;
    document.addEventListener('mousemove', function () {
        document.body.classList.add('cursor-shown');
        clearTimeout(cursorIdle);
        cursorIdle = setTimeout(function () {
            document.body.classList.remove('cursor-shown');
        }, 3000);
    }, { passive: true });
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
    paintFoot();
    tickClock();
    setInterval(tickClock, 1000);
    // A screen nobody has told anything asks; one that has been set up goes
    // straight to work, which is what it is for. Asking comes first: if the
    // feed cannot be reached, the way to fix it is still on screen.
    if (!CONFIGURED || params.get('setup') === '1') openSetup();
    connect();
});
