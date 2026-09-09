// Initialize Socket.IO with proper configuration and error handling
let socket = null;
let socketRetryCount = 0;
let socketListenersSetup = false;

// Multi-room support: derive room from URL ?room=xxx, default to 'main'
function getRoomId() {
    try {
        const params = new URLSearchParams(window.location.search);
        const r = (params.get('room') || '').trim();
        if (/^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/.test(r)) return r;
    } catch (e) { /* noop */ }
    return 'main';
}
window.CURRENT_ROOM_ID = getRoomId();
console.log('Joining room:', window.CURRENT_ROOM_ID);

// Generate or retrieve persistent client ID (stored in localStorage)
function getOrCreateClientId() {
    let clientId = localStorage.getItem('_client_id');
    if (!clientId) {
        // Generate a new UUID-like client ID - stored for persistence across sessions
        clientId = 'user_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now();
        localStorage.setItem('_client_id', clientId);
        console.log('Generated new persistent client ID:', clientId);
    } else {
        console.log('Using persistent client ID:', clientId);
    }
    return clientId;
}

function initSocket() {
    if (socket && socket.connected) {
        console.log('Socket already connected');
        return;
    }

    console.log('Initializing Socket.IO connection...');
    
    // Get persistent client ID and send it to server
    const clientId = getOrCreateClientId();

    socket = io({
        reconnection: true,
        reconnectionDelay: 1000,
        reconnectionDelayMax: 5000,
        reconnectionAttempts: 10,
        transports: ['websocket', 'polling'],
        upgrade: true,
        rememberUpgrade: true,
        rejectUnauthorized: false,  // For self-signed certificates
        forceNew: false,  // Reuse existing connection if possible
        query: {
            client_id: clientId,  // Send persistent client ID to server
            type: 'user',  // Identify as user client (not admin)
            room: window.CURRENT_ROOM_ID || 'main'  // Multi-room scope
        }
    });

    socket.on('connect_error', (error) => {
        socketRetryCount++;
        console.error(`Socket.IO connection error (attempt ${socketRetryCount}):`, error);
        if (socketRetryCount > 3) {
            console.warn('Connection failed multiple times. Check server status and network settings.');
        }
    });

    socket.on('error', (error) => {
        console.error('Socket.IO error:', error);
    });

    // ── Heartbeat: keep server aware this client is still alive ─────────
    // Runs every 15 s.  Server evicts silent clients after 45 s.
    let _heartbeatTimer = null;
    socket.on('connect', () => {
        if (_heartbeatTimer) clearInterval(_heartbeatTimer);
        _heartbeatTimer = setInterval(() => {
            if (socket && socket.connected) socket.emit('heartbeat');
        }, 15000);
    });
    socket.on('disconnect', () => {
        if (_heartbeatTimer) { clearInterval(_heartbeatTimer); _heartbeatTimer = null; }
    });

    // Register all app-level listeners immediately — before the socket
    // can connect — so connect/ready events are never missed.
    setupSocketEventListeners();

    return socket;
}

// Initialize socket after DOM is ready
function ensureSocketConnected() {
    if (!socket || !socket.connected) {
        initSocket();
    }
}

// TTS Settings
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let availableVoices = [];
let selectedVoice = null;
let ttsEngine = 'system';  // 'system' (Local) or 'edge' (Cloud)
let edgeTTSVoices = [];     // Available Edge TTS voices

// TTS Queue Management - prevents parallel playback and maintains order
let ttsQueue = [];          // Queue of {text, isAutoPlay} waiting to be spoken
let isTTSPlaying = false;   // Currently playing TTS
let currentAudioElement = null;  // Current playing audio element for Edge TTS
let currentUtterance = null;     // Current utterance for System TTS
let lastTTSClickText = '';  // Track last clicked TTS text for double-tap stop
let lastTTSClickTime = 0;   // Track when user last clicked TTS button
const TTS_DOUBLE_TAP_THRESHOLD = 500;  // 500ms window for double-tap detection

// Use shared translations provided by /static/js/i18n.js
const i18n = window.sharedI18n || {};
/* The reading language is the one choice a listener makes, and this is what
   the browser is asked for before they make it. English was missing from the
   whole table: nothing here could ever resolve to it, so an English browser
   fell past every branch to the Cantonese default at the bottom. That was
   invisible while this only picked a translation target — English in, English
   out, nothing to translate — but the page's own language follows this now,
   so an English speaker was met with a Cantonese page. */
const BROWSER_LANG_MAP = {
    'en': 'en',
    'zh-HK': 'yue',
    'zh-MO': 'yue',
    'yue': 'yue',
    'zh-CN': 'zh',
    'zh-SG': 'zh',
    'zh': 'zh',
    'zh-TW': 'zh-tw',
    'ja': 'ja',
    'ja-JP': 'ja',
    'ko': 'ko',
    'ko-KR': 'ko',
    'es': 'es',
    'es-ES': 'es',
    'fr': 'fr',
    'fr-FR': 'fr',
    'de': 'de',
    'de-DE': 'de',
    'ru': 'ru',
    'ru-RU': 'ru',
    'ar': 'ar',
    'pt': 'pt',
    'pt-PT': 'pt',
    'it': 'it',
    'it-IT': 'it',
    'nl': 'nl',
    'nl-NL': 'nl',
    'pl': 'pl',
    'pl-PL': 'pl',
    'tr': 'tr',
    'tr-TR': 'tr',
    'vi': 'vi',
    'vi-VN': 'vi',
    'th': 'th',
    'th-TH': 'th',
    'id': 'id',
    'id-ID': 'id',
    'ms': 'ms',
    'ms-MY': 'ms',
    'hi': 'hi',
    'hi-IN': 'hi',
    'ta': 'ta',
    'ta-IN': 'ta'
};

let displayLanguage = localStorage.getItem('displayLanguage') || detectDisplayLanguageLocal();

/* i18n.js resolves the language for everything carrying data-i18n and records
   it as window._displayLanguage. This file kept a second copy, and the reading
   language — set from the wizard, the dialog or a URL parameter — went through
   the shared runtime without touching it. So the markup translated and
   everything the script writes did not: the whole guide, the empty states, the
   toasts, all still in the language the page had loaded in. Wrapping the one
   funnel keeps the copy in step, whoever calls it. */
(function () {
    const shared = window.applyDisplayLanguage;
    if (typeof shared !== 'function' || shared.__syncsLocal) return;
    const wrapped = function () {
        shared.apply(this, arguments);
        const resolved = window._displayLanguage;
        if (resolved && i18n[resolved]) displayLanguage = resolved;
        return resolved;
    };
    wrapped.__syncsLocal = true;
    window.applyDisplayLanguage = wrapped;
})();
let displayMode = localStorage.getItem('displayMode') || 'translation';
let targetLang = localStorage.getItem('targetLang') || 'en';
let showSourceText = localStorage.getItem('showSourceText') !== 'false';  // Default true, unless explicitly set to false
let fontSize = parseInt(localStorage.getItem('fontSize') || '18', 10);
let translations = [];
let searchQuery = '';
const visibleTranslationIds = new Set();

// Virtual Scrolling / Pagination
let translationsOffset = 0;          // Current offset in pagination
let translationsLimit = 30;          // Items per load — large enough to fill the
                                     // viewport in one request so the scroll
                                     // sentinel doesn't trigger a cascade of
                                     // sequential loads on first connect.
let translationsTotal = 0;           // Total items on server
let isLoadingMore = false;           // Prevent duplicate requests
let hasMoreTranslations = false;     // More items available on server
let apiSessionToken = localStorage.getItem('apiSessionToken') || null;  // API token from WebSocket connection
let pageVisible = true;              // Track if page is visible (for optimization)

// Race-condition guard: each loadInitialTranslations call gets a sequence
// number; only the LAST call is allowed to commit its result to the DOM.
let _translationsLoadSeq = 0;

// ── Client-side translation cache ────────────────────────────────────────────
// Restore up to 50 most-recent translations from localStorage so the user
// sees their data immediately on page load — even if the server just restarted.
const _CACHE_KEY = '_txCache_v1_' + (window.CURRENT_ROOM_ID || 'main');
const _CACHE_LIMIT = 50;
try {
    const _raw = localStorage.getItem(_CACHE_KEY);
    if (_raw) {
        const _cached = JSON.parse(_raw);
        if (Array.isArray(_cached) && _cached.length) {
            translations = _cached;
            translationsTotal = _cached.length;
            console.log('Restored ' + _cached.length + ' translations from local cache');
        }
    }
} catch (e) {}

// Virtual Scrolling Optimization - PERFORMANCE FIX
let renderedCount = 0;               // How many items currently rendered in DOM
let renderBatchSize = 30;            // Render this many items at once (was rendering all!)
// Hard cap on the number of cards kept in the DOM. New translations stream in at
// the top during a live service; without a cap the DOM grows unbounded and the
// page becomes laggy past ~1000 cards. The full set stays in the `translations`
// array, so trimmed (older) cards are re-rendered from memory when scrolled to.
const MAX_RENDERED_CARDS = 250;
let scrollObserver = null;           // unused: the list ends in a button now
let isRenderingMore = false;         // Prevent duplicate render operations

// Translation queue - prevents rate limit when admin bulk imports
let translationQueue = [];           // Queue of {item, resolve} waiting to translate
let translationQueueRunning = false; // Is the queue processor running
let translationConcurrency = 0;      // Current concurrent translation count
const MAX_TRANSLATION_CONCURRENCY = 3;  // Max parallel translations
const TRANSLATION_DELAY_MS = 300;    // Delay between translations (ms)

// Debounce batch new_translation events from WebSocket
let pendingNewTranslations = [];     // Queue for incoming WebSocket translations

// State tracking for intelligent chunk detection
let activeChunkTracking = {};        // Map of temp_id -> {text, startTime, hasTransitionedToUnderstanding, statusChangeInterval}
const LISTENING_MIN_WORD_COUNT = 5;  // Min words to trigger transitions from listening
const WORD_BOUNDARY_REGEX = /\s+/;   // Split words
const PUNCTUATION_MARKERS = /[.!?;:]/; // Sentence boundaries
const PSYCHOLOGICAL_STATUS_CHANGE_MS = 1000; // Change status every ~1 second (0.8-1.2 range)
const UNDERSTANDING_AUTO_PROGRESS_MS = 4000; // Auto-progress to 'preparing' at 4s
const PREPARING_AUTO_PROGRESS_MS = 6000;     // Auto-progress to 'translating' at 6s

// Animation helpers
const CURSOR_PULSE = ['▌', '▎', '▍', '▌']; // Typing cursor animation

// PatternFly icons for the markup this file builds as strings. The paths are
// in the page once, as <symbol>s in the sprite render_user.py emits; this only
// points at them. Never put an emoji here — the page is PatternFly 6.
function svgIcon(name, cls) {
    return '<svg class="pf-v6-svg' + (cls ? ' ' + cls : '') + '" aria-hidden="true"'
        + ' role="img" width="1em" height="1em" fill="currentColor">'
        + '<use href="#i-' + name + '"></use></svg>';
}
const DOT_PULSE = ['.', '..', '...', '..'];  // Dot animation
let cursorIndex = 0;
let dotIndex = 0;
let newTranslationTimer = null;      // Timer for debouncing

// Translation fallback system
const translationCache = {};         // Cache translations locally for fallback

/* =========================
   i18n helpers
   ========================= */
// (Removed earlier simple local i18n helpers to avoid clobbering shared window helpers.)

/* =========================
   Settings
   ========================= */
function loadSettings() {
    const savedDisplay = localStorage.getItem('displayLanguage');
    if (savedDisplay && i18n[savedDisplay]) displayLanguage = savedDisplay;

    const displaySelect = document.getElementById('displayLanguage');
    if (displaySelect) displaySelect.value = displayLanguage;

    const modeSelect = document.getElementById('displayMode');
    if (modeSelect) {
        modeSelect.value = displayMode;
        modeSelect.addEventListener('change', () => {
            displayMode = modeSelect.value;
            localStorage.setItem('displayMode', displayMode);
            applyDisplayMode();
        });
    }

    const targetSelect = document.getElementById('targetLang');
    if (targetSelect) {
        targetSelect.value = targetLang;
        targetSelect.addEventListener('change', () => {
            targetLang = targetSelect.value;
            localStorage.setItem('targetLang', targetLang);
            loadVoices();
            // Only re-render in translation mode - in transcription mode, target language doesn't affect display
            if (displayMode !== 'transcription') {
                renderTranslations();
            }
        });
    }

    const fontSlider = document.getElementById('fontSizeSlider');
    if (fontSlider) {
        fontSlider.value = fontSize;
        fontSlider.addEventListener('input', () => {
            fontSize = parseInt(fontSlider.value, 10);
            localStorage.setItem('fontSize', fontSize);
            applyFontSize();
        });
    }

    // Setup source text toggle button
    const sourceTextToggle = document.getElementById('sourceTextToggle');
    if (sourceTextToggle) {
        updateSourceTextToggleUI();
        sourceTextToggle.addEventListener('click', () => {
            toggleSourceText();
        });
    }

    applyFontSize();
}

function applyFontSize() {
    let style = document.getElementById('dynamicFontStyle');
    if (!style) {
        style = document.createElement('style');
        style.id = 'dynamicFontStyle';
        document.head.appendChild(style);
    }
    style.textContent = `.text-target, .sc-line { font-size: ${fontSize}px !important; }`;
}

function applyDisplayMode() {
    const languageGroup = document.getElementById('languageSelectGroup');
    const ttsSection = document.querySelector('.sidebar-section:has(#toggleTTS)');
    const bibleTransRow = document.getElementById('bibleVerseToggleWrap');
    if (displayMode === 'transcription') {
        if (ttsSection)     ttsSection.style.display = 'none';
        if (languageGroup)  languageGroup.style.display = 'none';
        if (bibleTransRow)  bibleTransRow.style.display = 'none';
    } else {
        if (ttsSection)     ttsSection.style.display = '';
        if (languageGroup)  languageGroup.style.display = '';
        if (bibleTransRow)  bibleTransRow.style.display = '';
    }
}

function toggleSourceText() {
    // Toggle showing/hiding original text
    showSourceText = !showSourceText;
    localStorage.setItem('showSourceText', showSourceText);
    updateSourceTextToggleUI();
    
    // Update all existing interim cards (data-temp-id attribute)
    const list = document.getElementById('translationsList');
    if (list) {
        const interimCards = list.querySelectorAll('[data-temp-id]');
        console.log('Updating ' + interimCards.length + ' interim cards: showSourceText=' + showSourceText);
        
        interimCards.forEach(card => {
            const existingSource = card.querySelector('.text-source');
            const textTarget = card.querySelector('.text-target');
            
            if (existingSource) {
                // The row always carries the line; showing the English is only
                // ever a question of whether it is hidden.
                existingSource.hidden = !showSourceText;
            } else if (showSourceText && textTarget) {
                const sourceDiv = document.createElement('span');
                sourceDiv.className = 'meta text-source';
                sourceDiv.setAttribute('data-original-text', '');
                textTarget.insertAdjacentElement('afterend', sourceDiv);
            }
        });
    }
    
    // Re-render final cards
    renderTranslations();
}

function updateSourceTextToggleUI() {
    const btn = document.getElementById('sourceTextToggle');
    const textSpan = document.getElementById('sourceTextText');
    
    console.log('Updating source text toggle UI: showSourceText=' + showSourceText);
    
    if (btn && textSpan) {
        // Update text based on current state
        // If showing source (true) → button says "Hide Source"
        // If hiding source (false) → button says "Show Source"
        textSpan.textContent = showSourceText ? 'Hide Source' : 'Show Source';
        console.log('Button text set to: ' + textSpan.textContent);
    } else {
        console.warn('Could not find sourceTextToggle or sourceTextText elements');
    }
}

/* =========================
   Bible verse panel (opt-in, server-gated)
   =========================
   Server attaches `bible_refs` to translations when
   features.bible_detection.enabled is true in config.yaml.  The server
   broadcasts only ref METADATA (book/chapter/verse/display) — no verse
   text.  Each client fetches verse text via /api/bible/lookup using
   their own preferred target translation, which is auto-matched to the
   user's selected display/target language.

   Source translation is admin-configured (admin HTML) and never sent
   by the user client — the server uses its own configured value.

   The Bible section (✝️) is rendered server-side (Jinja2) so it only
   appears when the admin has enabled bible_detection.
*/
let bibleFeatureAvailable = false;
// Default ON — set 'showBibleVerse'='false' in localStorage to opt out.
let showBibleVerse = localStorage.getItem('showBibleVerse') !== 'false';

// User's chosen target Bible translation (persisted in localStorage).
// "" means "none" — no second translation shown.
let bibleTargetTrans = localStorage.getItem('bibleTargetTrans') || '';

// ── Language → PrayerPulse language-name mapping ─────────────────────
// Maps UI lang codes to the PrayerPulse language group name and a
// preferred default translation code for that language.
const _LANG_BIBLE = {
    en:      { pp: 'English',             def: 'KJV'    },
    zh:      { pp: 'Chinese',             def: 'CUNPS',  script: 'simplified' },  // simplified → new punct (simplified edition)
    'zh-tw': { pp: 'Chinese',             def: 'CUV',    script: 'traditional' },  // traditional
    yue:     { pp: 'Chinese',             def: 'CUV',    script: 'traditional' },  // Cantonese → traditional
    ja:      { pp: 'Japanese',            def: null     },  // first available
    ko:      { pp: 'Korean',              def: 'KRV'    },
    es:      { pp: 'Spanish',             def: 'RV1960' },
    fr:      { pp: 'French',              def: null     },  // first available
    de:      { pp: 'German',              def: 'ELB'    },
    ru:      { pp: 'Russian',             def: 'SYNOD'  },
    pt:      { pp: 'Portuguese',          def: null     },
    id:      { pp: 'Indonesian',          def: 'TB'     },
    ar:      { pp: 'Arabic',              def: null     },
    hi:      { pp: 'Hindi',               def: null     },
    nl:      { pp: 'Dutch',               def: null     },
    pl:      { pp: 'Polish',              def: null     },
    vi:      { pp: 'Vietnamese',          def: null     },
    tr:      { pp: null,                  def: null     },  // not in PrayerPulse
    th:      { pp: null,                  def: null     },
    it:      { pp: null,                  def: null     },
    ms:      { pp: 'Indonesian',          def: 'TB'     },  // closest available
    ta:      { pp: 'Tamil',               def: null     },
};

// Fetched once from /api/bible/languages and cached in-memory.
// Shape: [{ language: "English", translations: [{short_name, full_name}, ...] }, ...]
let _bibleLanguageData = null;

async function _loadBibleLanguages() {
    if (_bibleLanguageData) return _bibleLanguageData;
    try {
        const r = await fetch('/api/bible/languages');
        if (r.ok) _bibleLanguageData = await r.json();
    } catch (e) { /* offline / not enabled */ }
    return _bibleLanguageData || [];
}

// Classify a Chinese Bible translation as 'simplified' or 'traditional'.
// The bolls.life "Chinese" group mixes both scripts, so we inspect the name:
// explicit English markers first, then simplified/traditional-only characters.
const _ZH_TRAD_CHARS = '聖標點經傳啟後羅馬譯證書現體國語當達靈際東與聞約詩';
const _ZH_SIMP_CHARS = '圣标点经传启后罗马译证书现体国语当达灵际东与闻约诗';
function _zhScriptOf(t) {
    const name = `${(t && t.full_name) || ''} ${(t && t.short_name) || ''}`;
    if (/simplified/i.test(name)) return 'simplified';
    if (/traditional/i.test(name)) return 'traditional';
    let s = 0, tr = 0;
    for (const ch of name) {
        if (_ZH_SIMP_CHARS.includes(ch)) s++;
        else if (_ZH_TRAD_CHARS.includes(ch)) tr++;
    }
    if (s > tr) return 'simplified';
    if (tr > s) return 'traditional';
    // Fallback: an "…S" short name is usually the simplified sibling.
    return /S$/.test((t && t.short_name) || '') ? 'simplified' : 'traditional';
}

/**
 * Populate the target translation <select> with all options from PrayerPulse,
 * putting the user's matched language group first, then everything else.
 * Auto-selects the best default for the given langCode.
 */
/* Editions that do not belong in the same list as the rest.
 *
 * 思高聖經 is a Catholic translation whose book names and verse numbering do
 * not line up with 和合本. A reader who picks it by accident gets references
 * that do not resolve — and in a live service they have no way of knowing
 * that is why. It is left out rather than explained.
 */
const _EXCLUDED_BIBLES = ['CHISB'];

function _excludedBible(t) {
    const code = String(t.short_name || '').toUpperCase();
    const name = String(t.full_name || '');
    return _EXCLUDED_BIBLES.includes(code)
        || name.includes('思高') || /studium biblicum/i.test(name);
}

/* The script of a stored translation code, looked up in the language list we
   already have rather than guessed from the code. */
function _zhScriptOfCode(langData, code) {
    for (const group of langData || []) {
        for (const t of group.translations || []) {
            if (t.short_name === code) return _zhScriptOf(t);
        }
    }
    return null;
}

async function loadBibleTranslationOptions(langCode) {
    const sel = document.getElementById('bibleTargetTranslation');
    if (!sel) return;
    const prevTgt = bibleTargetTrans;

    const langData = await _loadBibleLanguages();
    if (!langData || !langData.length) {
        // Fallback: keep whatever is currently selected
        return;
    }

    const hint = document.getElementById('bibleTransLoadingHint');
    const info = _LANG_BIBLE[langCode] || {};
    const ppLangName = info.pp || null;

    sel.innerHTML = '<option value="">— None —</option>';

    // Only show translations for the user's matched language — no giant global list.
    const matched = langData.filter(g =>
        ppLangName && g.language.toLowerCase().startsWith(ppLangName.toLowerCase())
    ).map(g => Object.assign({}, g, {
        translations: (g.translations || []).filter(t => !_excludedBible(t))
    }));

    // Build options for the matched language group.
    const allMatchedCodes = [];
    const addOptgroup = (label, translations) => {
        if (!translations.length) return;
        const og = document.createElement('optgroup');
        og.label = label;
        translations.forEach(t => {
            const o = document.createElement('option');
            o.value = t.short_name;
            o.textContent = `${t.short_name} — ${t.full_name}`;
            og.appendChild(o);
            allMatchedCodes.push(t.short_name);
        });
        sel.appendChild(og);
    };
    matched.forEach(group => {
        const translations = group.translations || [];
        if (ppLangName === 'Chinese') {
            // bolls.life returns one mixed "Chinese" group — split by script so
            // Simplified and Traditional editions land under the right header.
            const simp = [], trad = [];
            translations.forEach(t => (_zhScriptOf(t) === 'simplified' ? simp : trad).push(t));
            const order = info.script === 'traditional'
                ? [['中文 — 繁體 (Traditional)', trad], ['中文 — 简体 (Simplified)', simp]]
                : [['中文 — 简体 (Simplified)', simp], ['中文 — 繁體 (Traditional)', trad]];
            order.forEach(([label, list]) => addOptgroup(label, list));
        } else {
            addOptgroup(group.language, translations);
        }
    });

    // If no match (language not in PrayerPulse), show English as fallback
    if (!matched.length) {
        const enGroup = langData.find(g => g.language === 'English');
        if (enGroup) {
            const og = document.createElement('optgroup');
            og.label = 'English (fallback)';
            (enGroup.translations || []).forEach(t => {
                const o = document.createElement('option');
                o.value = t.short_name;
                o.textContent = `${t.short_name} — ${t.full_name}`;
                og.appendChild(o);
                allMatchedCodes.push(t.short_name);
            });
            sel.appendChild(og);
        }
    }

    if (hint) hint.hidden = !ppLangName;

    // Restore saved preference if still valid for this language, else auto-match.
    // "Valid" has to mean the script too: bolls.life returns Simplified and
    // Traditional Chinese in one group, so a reader who switched from 粵語 to
    // 简体中文 kept CUV and got a Traditional Bible under a Simplified page —
    // both scripts on one screen, which is the thing this page must not do.
    const keeps = bibleTargetTrans && allMatchedCodes.includes(bibleTargetTrans)
        && (ppLangName !== 'Chinese' || !info.script
            || _zhScriptOfCode(langData, bibleTargetTrans) === info.script);
    if (keeps) {
        sel.value = bibleTargetTrans;
    } else {
        // Auto-match: use language default, or first in matched group
        const preferred = info.def;
        if (preferred && allMatchedCodes.includes(preferred)) {
            sel.value = preferred;
        } else if (allMatchedCodes.length) {
            sel.value = allMatchedCodes[0];
        } else {
            sel.value = '';
        }
        bibleTargetTrans = sel.value;
        try { localStorage.setItem('bibleTargetTrans', bibleTargetTrans); } catch (e) {}
    }

    // If the effective target translation changed, clear cache and reload visible panels
    if (bibleTargetTrans !== prevTgt) {
        _bibleLookupCache.clear();
        if (showBibleVerse) {
            translations.forEach(item => {
                if (item.bible_refs && item.bible_refs.length) {
                    const card = document.getElementById('translation-' + item.id);
                    if (card) loadBiblePanel(card, item.bible_refs);
                }
            });
        }
    }
}

// In-flight lookup promises: key = refs+translation fingerprint → Promise<enrichedRefs>
const _bibleLookupCache = new Map();

async function _fetchBibleVerses(refs, tgt) {
    // Source translation is admin-configured — not sent by client.
    const cacheKey = JSON.stringify({ refs: refs.map(r => r.display).sort(), tgt });
    if (_bibleLookupCache.has(cacheKey)) return _bibleLookupCache.get(cacheKey);

    const promise = fetch('/api/bible/lookup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refs, target_translation: tgt }),
    })
    .then(r => r.ok ? r.json() : [])
    .catch(() => []);

    _bibleLookupCache.set(cacheKey, promise);
    setTimeout(() => _bibleLookupCache.delete(cacheKey), 120000);
    return promise;
}

/**
 * Fetch verse text for refs and attach to card.
 */
async function loadBiblePanel(card, refs) {
    if (!card || !refs || !refs.length) return;
    if (!bibleFeatureAvailable) return;
    // In transcription mode show source text only (no target translation).
    const tgt = displayMode === 'transcription' ? '' : bibleTargetTrans;
    const when = card.querySelector('.card-time');
    try {
        const enriched = await _fetchBibleVerses(refs, tgt);
        if (!enriched || !enriched.length) { speakDeferred(card); return; }
        // The lookup rebuilds each ref around the verse text and drops what it
        // did not ask about — including `match`, which is the whole of how the
        // page decides whether to show a verse at all. Put the detector's own
        // fields back.
        const merged = enriched.map((found, i) => {
            const original = refs.find(r => r.display === found.display) || refs[i] || {};
            return Object.assign({}, original, found, {
                // Refs stored before there was a `match` came from the
                // reference detector, and a reference is what they are.
                match: original.match || found.match || 'reference',
                verse_start: original.verse_start != null
                    ? original.verse_start : found.verse_start,
                verse_end: original.verse_end != null
                    ? original.verse_end : found.verse_end
            });
        });
        // The record of what this service read is kept whether or not the
        // verses are shown in the stream: switching them off is a reading
        // preference, not an instruction to forget the readings.
        merged.forEach(ref => addToScripture(ref, when ? when.textContent : ''));
        if (!showBibleVerse) { speakDeferred(card); return; }
        // The lookup takes a few hundred milliseconds, and a line that arrives
        // while the speaker is talking can be re-rendered inside that window —
        // the row this was called with is then detached, and the verse used to
        // be dropped on the floor. It only ever showed up after a reload,
        // which is the one moment nobody is watching. Find the row again.
        const live = card.isConnected
            ? card
            : (card.id ? document.getElementById(card.id) : null);
        // Whatever happens, a line held back for a verse gets read: nothing
        // may be worse than the wrong thing, but silence is worse than both.
        if (live) attachBiblePanel(live, merged);
        else speakDeferred(card);
    } catch (e) {
        console.warn('loadBiblePanel failed:', e);
        speakDeferred(card);
    }
}

function initBibleFeature() {
    // The server renders the Bible section only when bible_detection is enabled.
    bibleFeatureAvailable = !!document.getElementById('bibleVerseToggle');
    if (!bibleFeatureAvailable) return;

    // Prefer targetLang (translation output language) as the Bible language;
    // fall back to displayLanguage (UI language) for users who haven’t set a target.
    const currentLang = (typeof targetLang !== 'undefined' && targetLang && targetLang !== 'en'
            ? targetLang
            : null)
        || localStorage.getItem('targetLang')
        || (typeof displayLanguage !== 'undefined' ? displayLanguage : null)
        || localStorage.getItem('displayLanguage')
        || 'en';
    loadBibleTranslationOptions(currentLang);
    updateBibleToggleUI();
}

function _restoreBibleTranslationSelectors() {
    // Legacy stub — options are now populated dynamically by loadBibleTranslationOptions().
    // Called by initBibleFeature() indirectly; keeping for backward compat.
}

function onBibleTranslationChange() {
    const tgtSel = document.getElementById('bibleTargetTranslation');
    if (tgtSel) bibleTargetTrans = tgtSel.value;

    try { localStorage.setItem('bibleTargetTrans', bibleTargetTrans); } catch (e) {}
    _bibleLookupCache.clear();

    // Re-fetch for all visible cards
    if (showBibleVerse) {
        translations.forEach(item => {
            if (item.bible_refs && item.bible_refs.length) {
                const card = document.getElementById('translation-' + item.id);
                if (card) loadBiblePanel(card, item.bible_refs);
            }
        });
    }
}

function toggleBibleVerse() {
    showBibleVerse = !showBibleVerse;
    localStorage.setItem('showBibleVerse', showBibleVerse);
    updateBibleToggleUI();

    if (showBibleVerse) {
        // Load verse text for all cards that have refs
        translations.forEach(item => {
            if (item.bible_refs && item.bible_refs.length) {
                const card = document.getElementById('translation-' + item.id);
                if (card) loadBiblePanel(card, item.bible_refs);
            }
        });
    } else {
        // The verse stood in for the translation, so putting the verses away
        // has to put the translation back: rendering the list again is the one
        // path that rebuilds every row from what the item actually holds.
        renderTranslations();
    }
}

function updateBibleToggleUI() {
    const textSpan = document.getElementById('bibleVerseText');
    if (!textSpan) return;
    const onText = (i18n && i18n[displayLanguage] && i18n[displayLanguage].bibleVerseHide) || (i18n && i18n.en && i18n.en.bibleVerseHide) || 'Hide Bible Verses';
    const offText = (i18n && i18n[displayLanguage] && i18n[displayLanguage].bibleVerseShow) || (i18n && i18n.en && i18n.en.bibleVerseShow) || 'Show Bible Verses';
    textSpan.textContent = showBibleVerse ? onText : offText;
}

/**
 * Returns 'simplified', 'traditional', or null based on the user's current language setting.
 */
function _bibleChineseScript() {
    const lang = (typeof displayLanguage !== 'undefined' ? displayLanguage : null)
        || localStorage.getItem('displayLanguage')
        || (typeof targetLang !== 'undefined' ? targetLang : null)
        || '';
    return (_LANG_BIBLE[lang] || {}).script || null;
}

/**
 * Build the verse panel DOM for a list of enriched refs and append to `card`.
 * Idempotent — replaces any existing panel. Uses only textContent/createElement
 * to prevent any HTML injection from API responses.
 */
function attachBiblePanel(card, refs) {
    if (!card || !refs || !refs.length) return;

    const text = card.querySelector('.stream-text');
    if (!text) return;
    text.querySelectorAll('.sc-offer').forEach(el => el.remove());

    // A verse the speaker read goes where the machine translation would have
    // been: it IS the line, which is the whole point of looking it up in the
    // reader's own Bible rather than translating it.
    //
    // But only when the line is the verse. "John 3:16" is; "John 3:16, and
    // I've told you about this before" is a sentence that happens to name one,
    // and swallowing it loses everything the speaker actually said. Then the
    // verse sits under the translation instead of replacing it.
    const shown = refs.find(r => r.match === 'reference' || r.match === 'wording');
    if (shown) {
        if (shown.match === 'wording' || saidNothingElse(card, shown)) {
            substituteVerse(card, text, shown);
        } else {
            alongsideVerse(card, text, shown);
        }
    }

    // Anything doubtful is offered *instead* — which is what "instead" has to
    // mean. A row already showing Matthew 5:19 was still offering "This may be
    // Matthew 5:20" and "This may be Matthew 18:4" underneath it: three
    // answers to one question, two of them guesses, under a verse the page was
    // sure enough about to put in place of what the speaker said.
    if (!shown) {
        refs.filter(r => r.match === 'offer' || r.match === 'cited')
            .forEach(r => text.appendChild(buildOffer(r)));
    }

    // The row has settled: read it now if reading it was held back.
    speakDeferred(card);
}

/* Did the speaker say anything besides the reference?

   Take the words out that naming a passage needs — the book, the numbers, and
   the few words English uses to point at one — and see what is left. Nothing
   means they read it; a sentence means they were talking, and what they said
   has to be translated like any other line. */
function saidNothingElse(card, ref) {
    const item = translations.find(t => 'translation-' + t.id === card.id);
    const said = ((item && (item.corrected || item.original)) || '').toLowerCase();
    if (!said) return true;
    const rest = said
        .replace((ref.book || '').toLowerCase(), ' ')
        .replace(/\d+\s*[:\uff1a]\s*\d+(\s*[-\u2013\u2014]\s*\d+)?/g, ' ')
        .replace(/\b(chapter|chapters|verse|verses|ch|v|vv)\b/g, ' ')
        .replace(/[^a-z\u4e00-\u9fff]+/g, ' ')
        .trim();
    const words = rest.split(/\s+/).filter(Boolean);
    return words.length < 3;
}

/* What the play button on a row reads out. A row whose line was a reference
   has the verse put in place of it on screen, but the button kept the words
   that were transcribed — so pressing play on "For God so loved the world"
   said "john 3:16 to 18" instead, and with reading aloud on that reference
   was spoken before the next line's own words. The button says what the row
   says. */
function setRowSpeech(card, text) {
    const btn = card && card.querySelector('.tts-icon');
    if (btn && text) btn.setAttribute('data-text', text);
    // Once a row reads a verse, the background translation landing later must
    // not put the transcribed reference back on the button.
    if (card && text) card.setAttribute('data-speaks-verse', '1');
}

/* A line that carries a reference is not read aloud when it arrives: the
   lookup takes a second or two, and by the time it lands the row may be
   showing the verse instead of the words that were transcribed. Speaking
   immediately meant hearing "john 3:16 to 18" and then, on the next line, the
   sermon going on without the verse ever being read. The row is marked, and
   whatever it settles on is spoken once the lookup is done. */
function deferSpeech(card) {
    if (card) card.setAttribute('data-await-verse', '1');
}

function speakDeferred(card) {
    if (!card || card.getAttribute('data-await-verse') !== '1') return;
    card.removeAttribute('data-await-verse');
    if (!ttsEnabled || displayMode === 'transcription') return;
    const btn = card.querySelector('.tts-icon');
    const text = btn && btn.getAttribute('data-text');
    if (text) speakText(text, true);
}

/* Is this line nothing but a reference, so that the verse will take its
   place? The speak sites need to know before the lookup comes back. */
function willBecomeVerse(data) {
    return !!(showBibleVerse && bibleFeatureAvailable
              && data && data.bible_refs && data.bible_refs.length);
}

function verseSpeech(slot) {
    return slot.verses.map(function (v) { return tidyVerseText(v.text); })
        .join(' ').trim();
}

/* The verse under the translation rather than in place of it, for a line that
   named a passage while saying something of its own. */
function alongsideVerse(card, text, ref) {
    const both = pickVersions(ref);
    const slot = both.primary;
    if (!slot || !slot.verses || !slot.verses.length) return;

    text.querySelectorAll('.sc-verse, .sc-more').forEach(el => el.remove());
    const verse = document.createElement('div');
    verse.className = 'sc-verse';
    renderWindow(verse, slot.verses, ref, both.secondary);
    text.appendChild(verse);
    if (slot.verses.length > VERSE_WINDOW) {
        text.appendChild(buildShowAll(ref, slot.verses.length));
    }
    writeVerseTag(card, ref, both);
}

function substituteVerse(card, text, ref) {
    const both = pickVersions(ref);
    const slot = both.primary;
    if (!slot || !slot.verses || !slot.verses.length) return;

    const holder = text.querySelector('.sc-verse') || text.querySelector('.stream-zh');
    if (!holder) return;

    const verse = document.createElement('div');
    verse.className = 'sc-verse';
    renderWindow(verse, slot.verses, ref, both.secondary);
    holder.replaceWith(verse);

    text.querySelectorAll('.sc-more').forEach(el => el.remove());
    if (slot.verses.length > VERSE_WINDOW) {
        verse.insertAdjacentElement('afterend', buildShowAll(ref, slot.verses.length));
    }

    setRowSpeech(card, verseSpeech(slot));
    writeVerseTag(card, ref, both);
}

/* The reference and how it was found belong against the timestamp, not in a
   header of their own: the row already has a place for saying what a line is. */
function writeVerseTag(card, ref, both) {
    const term = card.querySelector('.pf-v6-c-description-list__text');
    if (!term) return;
    term.querySelectorAll('.stream-tag').forEach(el => el.remove());
    const tag = document.createElement('span');
    tag.className = 'stream-tag';
    const bits = [ref.display];
    const names = [both.primary && both.primary.translation,
                   both.secondary && both.secondary.translation]
        .filter(Boolean).map(n => n.toUpperCase());
    if (names.length) bits.push(names.join(' / '));
    bits.push(ref.match === 'wording'
        ? t('sc_byWording', 'matched by wording')
        : t('sc_fromBible', 'from the Bible, not translated'));
    tag.textContent = bits.join(' · ');
    term.appendChild(tag);
}

/* The two Bibles this verse is read in, in the order the page reads: the
   reader's own first, the English under it — the same shape as every other row,
   where the translation leads and the English sits quietly beneath. */
function pickVersions(ref) {
    const has = slot => slot && slot.verses && slot.verses.length;
    const target = has(ref.target) ? ref.target : null;
    const source = has(ref.source) ? ref.source : null;
    const legacy = (!target && !source && ref.verses && ref.verses.length)
        ? { translation: ref.translation, verses: ref.verses } : null;

    const primary = target || source || legacy;
    let secondary = null;
    if (target && source && target.translation !== source.translation) {
        secondary = source;
    }
    return { primary: primary, secondary: secondary };
}

/* Kept for the callers that only ever need one. */
function pickVersion(ref) {
    return pickVersions(ref).primary;
}

function buildShowAll(ref, total) {
    const more = document.createElement('p');
    more.className = 'sc-more';
    const btn = document.createElement('button');
    btn.className = 'pf-v6-c-button pf-m-inline pf-m-link';
    btn.type = 'button';
    btn.setAttribute('aria-haspopup', 'dialog');
    btn.onclick = () => showPassage(ref);
    const label = document.createElement('span');
    label.className = 'pf-v6-c-button__text';
    label.textContent = t('sc_showAll', 'Show all %n verses').replace('%n', String(total))
        + ' — ' + (ref.display || '');
    btn.appendChild(label);
    more.appendChild(btn);
    return more;
}

/* One quiet line: the reference, and a way to read it. */
function buildOffer(ref) {
    const line = document.createElement('p');
    line.className = 'sc-offer';
    const label = document.createElement('span');
    label.textContent = (ref.match === 'cited'
        ? t('sc_cited', 'Mentioned')
        : t('sc_maybe', 'This may be')) + ' — ';
    line.appendChild(label);
    const open = document.createElement('button');
    open.className = 'pf-v6-c-button pf-m-inline pf-m-link';
    open.type = 'button';
    open.setAttribute('aria-haspopup', 'dialog');
    open.onclick = () => showPassage(ref);
    const openText = document.createElement('span');
    openText.className = 'pf-v6-c-button__text';
    openText.textContent = ref.display || '';
    open.appendChild(openText);
    line.appendChild(open);
    return line;
}

/* ── the Scripture section ────────────────────────────────────────────────
   Every passage this service has been through, gathered in one place, so
   somebody who looked away can find the reading without scrolling the stream.
   Offers and citations are listed too: what was mentioned is part of the
   record even when it was not read out. */
const scriptureSeen = new Set();

function addToScripture(ref, timestamp) {
    const list = document.getElementById('scriptureList');
    if (!list || !ref || !ref.display) return;
    const key = ref.display + '|' + (ref.match || '');
    if (scriptureSeen.has(key)) return;
    scriptureSeen.add(key);

    const empty = list.querySelector('.scripture-empty');
    if (empty) empty.remove();

    const group = document.createElement('div');
    group.className = 'pf-v6-c-description-list__group';

    // The reference is the term here, with the time under it — this page is
    // read by passage, not by clock.
    const dt = document.createElement('dt');
    dt.className = 'pf-v6-c-description-list__term';
    const dtText = document.createElement('span');
    dtText.className = 'pf-v6-c-description-list__text';
    dtText.textContent = ref.display;
    const when = document.createElement('span');
    when.className = 'sc-time';
    when.textContent = timestamp || '';
    dtText.appendChild(when);
    dt.appendChild(dtText);
    group.appendChild(dt);

    const dd = document.createElement('dd');
    dd.className = 'pf-v6-c-description-list__description';
    const ddText = document.createElement('div');
    ddText.className = 'pf-v6-c-description-list__text';

    const both = pickVersions(ref);
    const slot = both.primary;
    if (slot && slot.verses && slot.verses.length) {
        const verse = document.createElement('div');
        verse.className = 'sc-verse';
        renderWindow(verse, slot.verses, ref, both.secondary);
        ddText.appendChild(verse);
        if (slot.verses.length > VERSE_WINDOW) {
            ddText.appendChild(buildShowAll(ref, slot.verses.length));
        }
    } else {
        ddText.appendChild(buildOffer(ref));
    }

    // How it was found, and which verse the speaker actually read — said in
    // words, because this page is the record and a record has to explain
    // itself later.
    const how = document.createElement('span');
    how.className = 'meta';
    const parts = [{
        reference: t('sc_wasSpoken', 'The reference was spoken'),
        wording: t('sc_byWording', 'matched by wording'),
        offer: t('sc_maybe', 'This may be'),
        cited: t('sc_cited', 'Mentioned')
    }[ref.match] || ''];
    const names = [slot && slot.translation, both.secondary && both.secondary.translation]
        .filter(Boolean).map(n => n.toUpperCase());
    if (names.length) parts.push(names.join(' / '));
    if (ref.verse_start && ref.verse_end === ref.verse_start
            && slot && slot.verses && slot.verses.length > 1) {
        parts.push(t('sc_verseRead', 'verse %n was the one read aloud')
            .replace('%n', String(ref.verse_start)));
    }
    how.textContent = parts.filter(Boolean).join(' · ');
    ddText.appendChild(how);

    dd.appendChild(ddText);
    group.appendChild(dd);
    list.insertBefore(group, list.firstChild);
}
window.addToScripture = addToScripture;

/* ── the window over a long passage ───────────────────────────────────────
   Up to three verses are shown whole. Beyond that the window has to contain
   the verse that was actually read — not simply the first three — or the
   reader is shown the run-up to the point and never the point. */
const VERSE_WINDOW = 3;

function verseWindow(verses, ref) {
    if (verses.length <= VERSE_WINDOW) return { start: 0, verses: verses };
    // When the whole passage was read, nothing is singled out and the window
    // starts at the top.
    const read = (ref.verse_start && ref.verse_end && ref.verse_end > ref.verse_start
                  && (ref.verse_end - ref.verse_start + 1) >= verses.length)
        ? null : ref.verse_start;
    let start = 0;
    if (read != null) {
        const at = verses.findIndex(v => Number(v.n) === Number(read));
        if (at > 0) start = Math.min(Math.max(0, at - 1), verses.length - VERSE_WINDOW);
    }
    return { start: start, verses: verses.slice(start, start + VERSE_WINDOW) };
}

function renderWindow(host, verses, ref, secondary) {
    const win = verseWindow(verses, ref);
    const above = win.start;
    const below = verses.length - win.start - win.verses.length;

    // The other version, indexed by verse number: the two Bibles do not always
    // return the same run, and a line pairs with its own number or with
    // nothing at all.
    const other = new Map();
    (secondary && secondary.verses || []).forEach(v => other.set(String(v.n), v));

    if (above > 0) host.appendChild(elide(above));
    win.verses.forEach(v => {
        host.appendChild(verseLine(v, ref));
        const pair = other.get(String(v.n));
        if (pair) host.appendChild(verseLine(pair, ref, true));
    });
    if (below > 0) host.appendChild(elide(below));
}

function elide(count) {
    const line = document.createElement('p');
    line.className = 'sc-elide';
    line.textContent = '⋯ ';
    const label = document.createElement('span');
    label.textContent = t('sc_moreVerses', '%n more verses').replace('%n', String(count));
    line.appendChild(label);
    return line;
}

/* Some Chinese Bibles are stored with a space between every character —
   "我 雖 然 行 過 死 蔭 的 幽 谷" — which is how the text was typeset, not how it
   is read. A space between two Han characters carries no meaning and pulls a
   verse to twice its width, so it goes; a space beside anything else stays,
   because there it is doing a job. */
function tidyVerseText(text) {
    return String(text || '')
        .replace(/([\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])[ \t]+(?=[\u3400-\u9fff\uf900-\ufaff\u3000-\u303f\uff00-\uffef])/g, '$1')
        .trim();
}

function verseLine(v, ref, paired) {
    const line = document.createElement('p');
    line.className = paired ? 'sc-line sc-pair' : 'sc-line';
    // Context around the verse that was read is dimmed, so the eye lands on
    // the one the speaker actually said.
    if (ref && ref.verse_start && ref.verse_end === ref.verse_start
            && Number(v.n) !== Number(ref.verse_start)) {
        line.classList.add('sc-dim');
    }
    if (paired) {
        // The number is already on the line above; repeating it would make a
        // pair look like two verses.
        const spacer = document.createElement('sup');
        spacer.className = 'sc-n';
        spacer.setAttribute('aria-hidden', 'true');
        line.appendChild(spacer);
    } else {
        const num = document.createElement('sup');
        num.className = 'sc-n';
        num.textContent = String(v.n);
        line.appendChild(num);
    }
    line.appendChild(document.createTextNode(' ' + tidyVerseText(v.text)));
    return line;
}

/* ── the passage dialog ───────────────────────────────────────────────────
   The whole passage at a reading measure. Its footer reads it aloud; the
   stream never starts a passage on its own. */
async function showPassage(ref) {
    const modal = document.getElementById('passageModal');
    if (!modal) return;
    document.getElementById('passageTitle').textContent = ref.display || '';
    const sub = document.querySelector('#passageModal .modal-sub');
    if (sub) {
        const names = [ref.target && ref.target.translation, ref.source && ref.source.translation]
            .filter(Boolean).map(n => n.toUpperCase());
        sub.textContent = names.length
            ? names.join(' / ') + ' · ' + t('sc_fromBible', 'from the Bible, not translated')
            : t('sc_fromBible', 'from the Bible, not translated');
    }
    const body = document.getElementById('passageBody');
    body.replaceChildren();
    const loading = document.createElement('p');
    loading.className = 'sc-elide';
    loading.textContent = t('bibleLoading', '— Loading... —');
    body.appendChild(loading);
    modal.classList.add('active');

    let full = ref;
    if (!ref.source && !ref.target) {
        try {
            const got = await _fetchBibleVerses([ref], displayMode === 'transcription'
                ? '' : bibleTargetTrans);
            if (got && got.length) full = got[0];
        } catch (e) {
            console.warn('passage lookup failed', e);
        }
    }

    body.replaceChildren();
    const both = pickVersions(full);
    if (both.primary) {
        const other = new Map();
        (both.secondary && both.secondary.verses || []).forEach(v => other.set(String(v.n), v));
        const wrap = document.createElement('div');
        wrap.className = 'modal-verses';
        both.primary.verses.forEach(v => {
            wrap.appendChild(verseLine(v, null));
            const pair = other.get(String(v.n));
            if (pair) wrap.appendChild(verseLine(pair, null, true));
        });
        body.appendChild(wrap);
    }
    if (!body.childNodes.length) {
        const empty = document.createElement('p');
        empty.className = 'bible-verse-missing';
        empty.textContent = t('sc_unavailable', 'Verse text unavailable');
        body.appendChild(empty);
    }
    modal._passage = full;
}
window.showPassage = showPassage;

function hidePassage() {
    const modal = document.getElementById('passageModal');
    if (modal) modal.classList.remove('active');
}
window.hidePassage = hidePassage;

/* The one place a whole passage is ever spoken. */
function readPassageAloud() {
    const modal = document.getElementById('passageModal');
    const full = modal && modal._passage;
    if (!full) return;
    const slot = (full.target && full.target.verses && full.target.verses.length)
        ? full.target : full.source;
    if (!slot || !slot.verses) return;
    speakText(slot.verses.map(v => tidyVerseText(v.text)).join(' '));
}
window.readPassageAloud = readPassageAloud;

/* =========================
   Voice management (basic)
   ========================= */
function loadVoices() {
    if (!('speechSynthesis' in window)) return;
    availableVoices = speechSynthesis.getVoices() || [];
    const sel = document.getElementById('voiceSelect');
    if (!sel) return;
    sel.innerHTML = '';
    const auto = document.createElement('option');
    auto.value = '';
    auto.textContent = 'Auto';
    sel.appendChild(auto);
    availableVoices.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.name;
        opt.textContent = v.name;
        sel.appendChild(opt);
    });
    sel.addEventListener('change', () => {
        const nm = sel.value;
        selectedVoice = availableVoices.find(v => v.name === nm) || null;
        localStorage.setItem('selectedVoice', nm);
    });
}

/* =========================
   Translation (uses Google translate endpoints like before)
   ========================= */
/* Two language codes name the same language when their base subtag matches —
   en-US and en, cmn-Hans-CN and zh — except that Chinese splits by script, so
   simplified and traditional stay apart. */
function sameLanguage(a, b) {
    if (!a || !b) return false;
    const base = code => {
        const s = String(code).toLowerCase();
        // Cantonese is written in traditional script but is its own language,
        // so it has to be recognised before the script test.
        if (s.startsWith('yue')) return 'yue';
        if (s.startsWith('zh-tw') || s.includes('-hant')) return 'zh-tw';
        if (s.startsWith('zh')) return 'zh';
        return s.split('-')[0];
    };
    return base(a) === base(b);
}
window.sameLanguage = sameLanguage;

/* There were two functions called translateText here. JavaScript keeps the
   last one, so this one — which asked the endpoint directly and would have
   worked — was dead the moment it was written. It is gone; the live one is
   below, and its fallback now does what this did.
*/

/* =========================
   TTS
   ========================= */
function speakText(text) {
    if (!('speechSynthesis' in window)) return;
    speechSynthesis.cancel();
    if (!text) return;
    const u = new SpeechSynthesisUtterance(text);
    u.rate = ttsRate;
    u.volume = ttsVolume;
    if (selectedVoice) {
        const v = availableVoices.find(x => x.name === selectedVoice.name);
        if (v) u.voice = v;
    }
    speechSynthesis.speak(u);
}

/* =========================
   Rendering (minimal)
   ========================= */


/* =========================
   Init
   ========================= */
function init() {
    // ── URL param: ?lang=zh-TW  sets language without any manual selection ──
    // Normalise to the exact option values used by the <select> dropdowns.
    // e.g. zh-CN → zh,  zh-TW → zh-tw,  YUE → yue
    const _URL_LANG_MAP = {
        'zh-cn': 'zh', 'zh-hans': 'zh', 'cmn': 'zh',
        'zh-tw': 'zh-tw', 'zh-hant': 'zh-tw', 'zh-hk': 'zh-tw',
        'yue': 'yue', 'zh-yue': 'yue',
    };
    const _urlParams = new URLSearchParams(window.location.search);
    const _urlLangRaw = _urlParams.get('lang');
    if (_urlLangRaw) {
        const _norm = _urlLangRaw.toLowerCase();
        // Check explicit map first, then try direct match against select options
        const _mapped = _URL_LANG_MAP[_norm] || _norm.split('-')[0];
        // Validate against the actual <select> options before saving
        const _sel = document.getElementById('targetLang');
        const _valid = _sel ? Array.from(_sel.options).some(o => o.value === _mapped) : true;
        const _finalLang = _valid ? _mapped : _norm.split('-')[0];
        localStorage.setItem('targetLang', _finalLang);
        // Also set displayLanguage from same param
        const _dispSel = document.getElementById('displayLanguage');
        const _dispValid = _dispSel ? Array.from(_dispSel.options).some(o => o.value === _finalLang) : false;
        if (_dispValid) localStorage.setItem('displayLanguage', _finalLang);
        window.history.replaceState({}, '', window.location.href);
    }

    loadSettings();
    applyDisplayLanguageLocal();
    applyDisplayMode();

    // Must set bibleFeatureAvailable = true BEFORE renderTranslations() so that
    // Bible panels are loaded for cached cards shown immediately on page restore.
    initBibleFeature();

    // Show cached translations immediately so the user sees their data on
    // page load without waiting for the server round-trip.
    if (translations.length) {
        renderTranslations();
    }

    // Initialize Socket.IO connection
    ensureSocketConnected();

    // Load appropriate voices based on TTS engine
    if ('speechSynthesis' in window) {
        loadVoices();
        speechSynthesis.addEventListener('voiceschanged', function() {
            if (ttsEngine === 'system') {
                loadVoices();
            }
        });
    }

    const langSel = document.getElementById('displayLanguage');
    if (langSel) langSel.addEventListener('change', changeDisplayLanguageLocal);

    // Monitor page visibility to optimize resource usage
    document.addEventListener('visibilitychange', handleVisibilityChange);
    pageVisible = !document.hidden;

    // Ensure source text toggle button UI is updated after all DOM elements are loaded
    updateSourceTextToggleUI();

    // Apply saved view mode (standard / accessibility / elderly)
    loadUIMode();

    // Browser-level network status (additive, complements socket events)
    try {
        window.addEventListener('offline', function () {
            setConnectionStatus('offline');
            showToast(t('toast_offline', 'You are offline'), 'warning', 4000);
        });
        window.addEventListener('online', function () {
            setConnectionStatus('waiting');
            showToast(t('toast_reconnected', 'Back online'), 'success', 2500);
        });
    } catch (e) {}

    // First-visit onboarding (only shows once per browser).
    // Gate: don't interrupt if user is already interacting (scroll, focus, or another modal open).
    try {
        if (!localStorage.getItem('onboardingSeen_v1')) {
            let __userInteracted = false;
            const __markInteract = function () { __userInteracted = true; };
            window.addEventListener('scroll', __markInteract, { once: true, passive: true });
            window.addEventListener('keydown', __markInteract, { once: true });
            window.addEventListener('mousedown', __markInteract, { once: true });
            window.addEventListener('touchstart', __markInteract, { once: true, passive: true });
            const __tryShow = function () {
                if (__userInteracted) return; // user is busy; skip welcome this session
                if (__activeModalId) return;  // some other modal is open
                if (document.hidden) return;  // tab not visible
                showWelcome();
            };
            if (typeof requestIdleCallback === 'function') {
                requestIdleCallback(function () { setTimeout(__tryShow, 600); }, { timeout: 2000 });
            } else {
                setTimeout(__tryShow, 1200);
            }
        }
    } catch (e) {}

    console.log('user.js initialized');
}

document.addEventListener('DOMContentLoaded', init);

// ─── Screen Wake Lock ─────────────────────────────────────────────────────────
// Keeps the phone screen on while the audience page is visible.
(function () {
    if (!('wakeLock' in navigator)) return;

    let _wakeLock = null;

    async function _acquire() {
        if (_wakeLock) return;
        if (document.hidden) return;
        try {
            _wakeLock = await navigator.wakeLock.request('screen');
            _wakeLock.addEventListener('release', function () { _wakeLock = null; });
        } catch (e) {}
    }

    // Re-acquire whenever tab becomes visible (lock auto-releases on hide)
    document.addEventListener('visibilitychange', function () {
        if (!document.hidden) _acquire();
    });

    _acquire();
})();

/* ===================================
   XSS Protection
   =================================== */

function sanitizeInput(input) {
    if (typeof input !== 'string') return '';

    // Remove HTML tags and dangerous characters
    return input
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;')
        .trim();
}

function validateText(text, maxLength = 10000) {
    if (!text || typeof text !== 'string') {
        return { valid: false, error: 'Invalid input' };
    }

    const trimmed = text.trim();

    if (trimmed.length === 0) {
        return { valid: false, error: 'Text cannot be empty' };
    }

    if (trimmed.length > maxLength) {
        return { valid: false, error: `Text too long (max ${maxLength} characters)` };
    }

    // Check for suspicious patterns
    const dangerousPatterns = [
        /<script/i,
        /javascript:/i,
        /on\w+\s*=/i,
        /<iframe/i,
        /<object/i,
        /<embed/i
    ];

    for (let pattern of dangerousPatterns) {
        if (pattern.test(trimmed)) {
            return { valid: false, error: 'Invalid characters detected' };
        }
    }

    return { valid: true, text: sanitizeInput(trimmed) };
}

// TTS Language Mapping
const TTS_LANG_MAP = {
    'yue': 'zh-HK',
    'zh': 'zh-CN',
    'zh-tw': 'zh-TW',
    'ja': 'ja-JP',
    'ko': 'ko-KR',
    'es': 'es-ES',
    'fr': 'fr-FR',
    'de': 'de-DE',
    'ru': 'ru-RU',
    'ar': 'ar-SA',
    'pt': 'pt-PT',
    'it': 'it-IT',
    'nl': 'nl-NL',
    'pl': 'pl-PL',
    'tr': 'tr-TR',
    'vi': 'vi-VN',
    'th': 'th-TH',
    'id': 'id-ID',
    'ms': 'ms-MY',
    'hi': 'hi-IN',
    'ta': 'ta-IN'
};

// Language Detection Mapping

/* ===================================
   Auto Language Detection
   =================================== */

function detectUserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    console.log('Browser language detected:', browserLang);

    // Try exact match first
    if (BROWSER_LANG_MAP[browserLang]) {
        console.log('Exact match found:', BROWSER_LANG_MAP[browserLang]);
        return BROWSER_LANG_MAP[browserLang];
    }

    // Try the script and region before the bare base: browsers report
    // zh-Hant-HK rather than zh-HK, and taking the base of that would answer
    // Simplified to someone reading Traditional.
    const lower = browserLang.toLowerCase();
    if (lower.startsWith('yue') || lower.includes('-hk') || lower.includes('-mo')) return 'yue';
    if (lower.startsWith('zh') && (lower.includes('hant') || lower.includes('-tw'))) return 'zh-tw';

    // Try base language (e.g., 'zh' from 'zh-Hans')
    const baseLang = browserLang.split('-')[0];
    if (BROWSER_LANG_MAP[baseLang]) {
        console.log('Base language match found:', BROWSER_LANG_MAP[baseLang]);
        return BROWSER_LANG_MAP[baseLang];
    }

    // Check all browser languages
    if (navigator.languages && navigator.languages.length > 0) {
        for (let lang of navigator.languages) {
            if (BROWSER_LANG_MAP[lang]) {
                console.log('Alternative language match found:', BROWSER_LANG_MAP[lang]);
                return BROWSER_LANG_MAP[lang];
            }
            const base = lang.split('-')[0];
            if (BROWSER_LANG_MAP[base]) {
                console.log('Alternative base language match found:', BROWSER_LANG_MAP[base]);
                return BROWSER_LANG_MAP[base];
            }
        }
    }

    // Default to Cantonese
    console.log('No match found, using default: yue');
    return 'yue';
}

function detectDisplayLanguageLocal() {
    /* The page's language is the reading language, so it is detected the same
       way. This used to be a second table with its own idea of which browser
       means which language, and the two disagreed: this one answered English
       where the other answered Cantonese, and which of them a reader got
       depended on which ran first. */
    return detectUserLanguage();
}

// Use shared i18n runtime helpers when available to avoid duplication and errors.
function applyDisplayLanguageLocal() {
    if (window.applyDisplayLanguage && !window._applyingDisplayLanguage) {
        try {
            window.applyDisplayLanguage();
            return;
        } catch (e) {
            console.warn('shared applyDisplayLanguage failed', e);
        }
    }

    // Fallback: minimal safe application
    const elements = document.querySelectorAll('[data-i18n]');
    elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (i18n[displayLanguage] && i18n[displayLanguage][key]) {
            element.textContent = i18n[displayLanguage][key];
        }
    });

    const badge = document.getElementById('statusBadge');
    if (badge) {
        const statusSpan = badge.querySelector('.pf-v6-c-label__text');
        if (statusSpan) {
            statusSpan.textContent = i18n[displayLanguage]?.online || i18n[displayLanguage]?.offline || i18n[displayLanguage]?.waiting || statusSpan.textContent;
        }
    }

    updateThemeUI(document.documentElement.getAttribute('data-theme'));
}

async function changeDisplayLanguageLocal() {
    const select = document.getElementById('displayLanguage');
    if (!select) return;
    const newLang = select.value;
    // Always persist the chosen language locally so other scripts can read it
    displayLanguage = newLang;
    try {
        localStorage.setItem('displayLanguage', displayLanguage);
    } catch (e) {
    }

    if (window.changeDisplayLanguage) {
        // Delegate rendering to the shared runtime (it will update the DOM)
        try {
            window.changeDisplayLanguage(newLang);
        } catch (e) {
            console.warn('shared changeDisplayLanguage failed', e);
            applyDisplayLanguageLocal();
        }
    } else {
        // Fallback: apply locally
        applyDisplayLanguageLocal();
    }
    
    // Re-render translations to update empty state with new language
    await renderTranslations();
    // Re-apply display mode to update mode-specific text
    updateDisplayMode();
    // Update Bible toggle button label for the new language
    updateBibleToggleUI();
    // Auto-match Bible target translation to the new display language
    if (bibleFeatureAvailable) {
        loadBibleTranslationOptions(newLang);
    }
}

/* ===================================
   Settings Management
   =================================== */

function loadSettings() {
    const savedLang = localStorage.getItem('targetLang');
    const savedMode = localStorage.getItem('displayMode');
    const savedVoice = localStorage.getItem('selectedVoice');
    const savedRate = localStorage.getItem('ttsRate');
    const savedVolume = localStorage.getItem('ttsVolume');
    const savedTheme = localStorage.getItem('theme');
    const savedFontSize = localStorage.getItem('fontSize');
    const savedDisplayLanguage = localStorage.getItem('displayLanguage');
    const savedTTSEngine = localStorage.getItem('ttsEngine');
    const savedTTSEnabled = localStorage.getItem('ttsEnabled');

    // Load TTS enabled state
    if (savedTTSEnabled !== null) {
        ttsEnabled = savedTTSEnabled === 'true';
        console.log('Loaded TTS enabled state:', ttsEnabled);
    }
    // Unconditionally: the masthead icon says which state it is in, and with
    // nothing stored yet it would otherwise keep the speaking icon while
    // silent.
    const ttsBox = document.getElementById('toggleTTS');
    if (ttsBox) ttsBox.checked = ttsEnabled;
    syncTTSQuickToggle();

    // Load TTS engine preference
    if (savedTTSEngine && (savedTTSEngine === 'system' || savedTTSEngine === 'edge')) {
        ttsEngine = savedTTSEngine;
    }
    const engineSelect = document.getElementById('ttsEngine');
    if (engineSelect) engineSelect.value = ttsEngine;

    // Load display language (be tolerant of variants like 'en-US')
    if (savedDisplayLanguage) {
        if (i18n[savedDisplayLanguage]) {
            displayLanguage = savedDisplayLanguage;
            console.log('Using saved display language:', savedDisplayLanguage);
        } else {
            const base = savedDisplayLanguage.split('-')[0];
            if (i18n[base]) {
                displayLanguage = base;
                console.log('Using base of saved display language:', base);
            } else {
                displayLanguage = detectDisplayLanguageLocal();
                console.log('Saved display language not supported, auto-detected:', displayLanguage);
            }
        }
    } else {
        displayLanguage = detectDisplayLanguageLocal();
        localStorage.setItem('displayLanguage', displayLanguage);
        console.log('Auto-detected and saved display language:', displayLanguage);
    }

    const dispEl = document.getElementById('displayLanguage');
    if (dispEl) dispEl.value = displayLanguage;

    // Load display mode
    if (savedMode) {
        displayMode = savedMode;
        document.getElementById('displayMode').value = savedMode;
        updateDisplayMode();
    }

    // Auto-detect language if not saved
    if (savedLang) {
        targetLang = savedLang;
        console.log('Using saved language:', savedLang);
    } else {
        targetLang = detectUserLanguage();
        localStorage.setItem('targetLang', targetLang);
        console.log('Auto-detected and saved language:', targetLang);
    }

    document.getElementById('targetLang').value = targetLang;

    /* Now that the reading language is settled, the page can say what it is:
       "Live Translations" or, when that language is the one being spoken,
       "Live Transcription". This used to run only when a display mode had
       been stored, so a first visit kept whatever the template happened to
       say. */
    updateDisplayMode();

    if (savedRate) {
        ttsRate = parseFloat(savedRate);
        document.getElementById('rateSlider').value = ttsRate;
    }

    if (savedVolume) {
        ttsVolume = parseFloat(savedVolume);
        document.getElementById('volumeSlider').value = Math.round(ttsVolume * 100);
    }

    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeUI(savedTheme);
    }

    if (savedFontSize) {
        fontSize = parseInt(savedFontSize);
        document.getElementById('fontSizeSlider').value = fontSize;
        applyFontSize();
    }

    // The three settings above are the inputs of PatternFly sliders; writing
    // an input does not move a thumb, so the thumbs are told to catch up.
    if (typeof syncSliders === 'function') syncSliders();

    return savedVoice;
}

/* ===================================
   Voice Management
   =================================== */

function loadVoices() {
    const voiceSelect = document.getElementById('voiceSelect');
    
    if (ttsEngine === 'edge') {
        loadEdgeTTSVoices();
    } else {
        loadSystemVoices();
    }
}

function loadSystemVoices() {
    // Load Web Speech API (System) voices
    availableVoices = speechSynthesis.getVoices();

    if (availableVoices.length === 0) {
        return;
    }

    const voiceSelect = document.getElementById('voiceSelect');
    const savedVoice = localStorage.getItem('selectedVoice');
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;

    // Filter voices based on target language
    const matchingVoices = availableVoices.filter(function (voice) {
        const voiceLang = voice.lang.toLowerCase();
        const targetLangLower = ttsLang.toLowerCase();

        // Special handling for Chinese variants
        if (targetLang === 'yue') {
            return voiceLang === 'zh-hk' ||
                voiceLang.includes('yue') ||
                (voice.name.includes('粵語') || voice.name.includes('粤语'));
        } else if (targetLang === 'zh') {
            return voiceLang === 'zh' ||
                (voiceLang.startsWith('zh') &&
                    (voice.name.includes('普通话') ||
                        voice.name.includes('China mainland') ||
                        voice.name.includes('中国大陆'))) &&
                !voice.name.includes('Taiwan') &&
                !voice.name.includes('臺灣') &&
                !voice.name.includes('台灣') &&
                !voice.name.includes('Hong Kong') &&
                !voice.name.includes('香港');
        } else if (targetLang === 'zh-tw') {
            return voiceLang === 'zh-tw' ||
                (voiceLang.startsWith('zh') &&
                    (voice.name.includes('Taiwan') ||
                        voice.name.includes('臺灣') ||
                        voice.name.includes('台灣') ||
                        voice.name.includes('國語'))) &&
                !voice.name.includes('China mainland') &&
                !voice.name.includes('中国大陆') &&
                !voice.name.includes('Hong Kong') &&
                !voice.name.includes('香港');
        } else {
            return voiceLang === targetLangLower;
        }
    });

    const voicesToShow = matchingVoices.length > 0 ? matchingVoices : availableVoices;

    voiceSelect.innerHTML = '';

    // Add auto option
    const autoOption = document.createElement('option');
    autoOption.value = '';
    autoOption.textContent = 'Auto (System Default)';
    voiceSelect.appendChild(autoOption);

    // Group voices by language
    const grouped = {};
    voicesToShow.forEach(function (voice) {
        const lang = voice.lang;
        if (!grouped[lang]) grouped[lang] = [];
        grouped[lang].push(voice);
    });

    // Add voice options
    Object.keys(grouped).sort().forEach(function (lang) {
        grouped[lang].forEach(function (voice) {
            const option = document.createElement('option');
            option.value = voice.name;

            // Clean voice name
            let cleanName = voice.name;
            let iterations = 0;
            while (iterations < 10) {
                const before = cleanName;
                cleanName = cleanName.replace(/\s*\([^()]*\)/g, '');
                cleanName = cleanName.replace(/\s*（[^（）]*）/g, '');
                cleanName = cleanName.replace(/\s*\[[^\[\]]*\]/g, '');
                cleanName = cleanName.replace(/\s*【[^【】]*】/g, '');
                if (before === cleanName) break;
                iterations++;
            }

            cleanName = cleanName.replace(/\s+/g, ' ').trim();

            // Remove region keywords
            const regionKeywords = [
                'India', 'Bulgaria', 'Bangladesh', 'Bosnia', 'Herzegovina',
                'Spain', 'Czechia', 'Kingdom', 'Denmark', 'United States',
                'China', 'Taiwan', 'Hong Kong', 'Japan', 'Korea',
                '中国', '台湾', '臺灣', '香港', '日本', '韩国', '大陆'
            ];

            for (let i = 0; i < regionKeywords.length; i++) {
                const keyword = regionKeywords[i];
                const regex = new RegExp('\\s+' + keyword + '$', 'i');
                cleanName = cleanName.replace(regex, '');
            }

            cleanName = cleanName.trim();
            option.textContent = cleanName;
            voiceSelect.appendChild(option);
        });
    });

    // Restore saved voice
    if (savedVoice) {
        const voiceExists = voicesToShow.find(function (v) {
            return v.name === savedVoice;
        });
        if (voiceExists) {
            voiceSelect.value = savedVoice;
            selectedVoice = voiceExists;
        } else {
            selectedVoice = null;
        }
    }

    console.log('Loaded ' + availableVoices.length + ' system voices, showing ' + voicesToShow.length + ' for ' + targetLang);
}

async function loadEdgeTTSVoices(retryCount = 0, maxRetries = 5) {
    // Load Edge TTS voices from backend API with automatic retry
    const voiceSelect = document.getElementById('voiceSelect');
    
    // Only show loading message on first attempt
    if (retryCount === 0) {
        voiceSelect.innerHTML = '<option value="">Loading Edge TTS voices...</option>';
    }
    
    try {
        // Map target language to Edge TTS language code
        const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
        const savedVoice = localStorage.getItem('selectedVoice');
        
        if (retryCount === 0) {
            console.log('Fetching Edge TTS voices for language:', targetLang, '', ttsLang);
        } else {
            console.log(`Retrying Edge TTS voices (attempt ${retryCount + 1}/${maxRetries})...`);
        }
        
        const response = await fetch('/api/tts/voices?lang=' + encodeURIComponent(ttsLang));
        
        // Check HTTP response status
        if (!response.ok) {
            console.error(`HTTP ${response.status} error from /api/tts/voices`);
            
            let errorMsg = `Server error (${response.status})`;
            try {
                const errorData = await response.json();
                errorMsg = errorData.error || errorData.message || errorMsg;
            } catch (e) {
                // Response is not JSON
            }
            
            voiceSelect.innerHTML = `<option value="">Edge TTS Error: ${errorMsg.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}</option>`;
            console.warn(`Edge TTS server error: ${errorMsg}`);
            return;
        }
        
        const data = await response.json();
        
        // Check if voices are still loading
        if (data.warning && data.warning.includes('loading')) {
            console.log(`Voices still loading, retrying in 2 seconds...`);
            if (retryCount < maxRetries) {
                // Wait and retry
                voiceSelect.innerHTML = `<option value="">Loading Edge TTS voices (${parseInt(retryCount) + 1}/${parseInt(maxRetries)})...</option>`;
                await new Promise(resolve => setTimeout(resolve, 2000));
                return loadEdgeTTSVoices(retryCount + 1, maxRetries);
            } else {
                console.warn('Edge TTS voices still loading after max retries');
                voiceSelect.innerHTML = '<option value="">Voices loading, please refresh...</option>';
                return;
            }
        }
        
        if (!data.success || !data.edge_tts_available) {
            const msg = data.error || 'Edge TTS not available';
            console.warn(`Edge TTS not available: ${msg}`);
            voiceSelect.innerHTML = `<option value="">${String(msg || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</option>`; 
            return;
        }
        
        edgeTTSVoices = data.edge_voices || [];
        
        voiceSelect.innerHTML = '';
        
        // Add auto option
        const autoOption = document.createElement('option');
        autoOption.value = '';
        autoOption.textContent = 'Auto (Cloud Default)';
        voiceSelect.appendChild(autoOption);
        
        if (edgeTTSVoices.length === 0) {
            const noVoicesOption = document.createElement('option');
            noVoicesOption.value = '';
            noVoicesOption.textContent = 'No voices available for this language';
            voiceSelect.appendChild(noVoicesOption);
            console.warn('No Edge TTS voices available for language:', targetLang);
            return;
        }
        
        // Group voices by language
        const grouped = {};
        edgeTTSVoices.forEach(function (voice) {
            const lang = voice.locale;
            if (!grouped[lang]) grouped[lang] = [];
            grouped[lang].push(voice);
        });
        
        // Add voice options
        Object.keys(grouped).sort().forEach(function (lang) {
            grouped[lang].forEach(function (voice) {
                const option = document.createElement('option');
                option.value = voice.name;
                option.textContent = voice.display_name + ' (' + voice.gender + ')';
                voiceSelect.appendChild(option);
            });
        });
        
        // Restore saved voice selection
        if (savedVoice) {
            const voiceExists = edgeTTSVoices.find(function (v) {
                return v.name === savedVoice;
            });
            if (voiceExists) {
                voiceSelect.value = savedVoice;
                console.log('Restored saved Edge TTS voice:', savedVoice);
            } else {
                voiceSelect.value = '';
                console.log('Saved voice not available, using auto selection');
            }
        }
        
        console.log('Loaded ' + edgeTTSVoices.length + ' Edge TTS voices');
    } catch (error) {
        console.error('Error loading Edge TTS voices:', error);
        voiceSelect.innerHTML = `<option value="">Error: ${String(error.message || 'Unknown').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')}</option>`;
    }
}

function changeVoice() {
    const voiceSelect = document.getElementById('voiceSelect');
    const voiceName = voiceSelect.value;

    // Clear TTS queue when changing voice to prevent wrong voice playback
    clearTTSQueue();

    if (ttsEngine === 'system') {
        // System TTS
        if (voiceName) {
            selectedVoice = availableVoices.find(function (v) {
                return v.name === voiceName;
            });
            localStorage.setItem('selectedVoice', voiceName);
            console.log('Selected system voice: ' + voiceName);
        } else {
            selectedVoice = null;
            localStorage.removeItem('selectedVoice');
            console.log('Using auto voice selection');
        }
    } else if (ttsEngine === 'edge') {
        // Edge TTS
        localStorage.setItem('selectedVoice', voiceName);
        console.log('Selected Edge TTS voice: ' + voiceName);
    }
}

function changeTTSEngine() {
    const engineSelect = document.getElementById('ttsEngine');
    ttsEngine = engineSelect.value;
    localStorage.setItem('ttsEngine', ttsEngine);
    
    console.log('Switched TTS engine to:', ttsEngine === 'system' ? 'System (Local)' : 'Edge TTS (Cloud)');
    
    // Clear TTS queue when switching engines to avoid mixing
    clearTTSQueue();
    
    // Load appropriate voices for the new engine
    loadVoices();
}

function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    localStorage.setItem('targetLang', targetLang);

    loadVoices();

    // Clear cached translations (not the data, just the cached translations)
    translations.forEach(function (item) {
        item.translated = null;
        item.currentLang = null;
    });
    
    // Re-render with new language (will trigger translation)
    renderTranslations();

    // Auto-match Bible target translation to the new target language
    if (bibleFeatureAvailable) {
        loadBibleTranslationOptions(targetLang);
    }

    // The page follows the reading language. The dialog said so itself after
    // calling this, but the select in the settings did not, so changing the
    // language there translated the lines and left the buttons and headings
    // in the old one until the page was reloaded.
    updateDisplayMode();
    if (typeof followReadingLanguage === 'function') followReadingLanguage();
}

function changeDisplayMode() {
    const select = document.getElementById('displayMode');
    displayMode = select.value;
    localStorage.setItem('displayMode', displayMode);

    console.log('Display mode changed to:', displayMode);
    
    // Clear any pending interim cards when switching modes
    const list = document.getElementById('translationsList');
    if (list) {
        const interimCards = list.querySelectorAll('[data-temp-id]');
        console.log('Removing ' + interimCards.length + ' interim cards');
        interimCards.forEach(card => card.remove());
    }

    // Reset virtual-scroll cursor — renderTranslations() will rebuild the
    // DOM from scratch and append items afresh; keeping the old count
    // would skip items or duplicate them.
    renderedCount = 0;

    updateDisplayMode();
    renderTranslations();
}

function updateDisplayMode() {
    const ttsTab = document.getElementById('settings-tabitem-speech');
    const bibleTab = document.getElementById('settings-tabitem-bible');
    const languageGroup = document.getElementById('languageSelectGroup');
    const bibleTransRow = document.getElementById('bibleVerseToggleWrap');
    const mainTitleText = document.getElementById('mainTitleText');
    const emptyStateText = document.getElementById('emptyStateText');
    const emptyStateDesc = document.getElementById('emptyStateDesc');

    // Transcription mode hides the settings that only matter to a translation.
    const transcriptionMode = displayMode === 'transcription';
    if (ttsTab)        ttsTab.hidden = transcriptionMode;
    if (bibleTab)      bibleTab.hidden = transcriptionMode;
    if (languageGroup) languageGroup.hidden = transcriptionMode;
    if (bibleTransRow) bibleTransRow.hidden = transcriptionMode;

    /* What the page calls itself is a separate question from which settings it
       shows. Reading the language being spoken is transcription by another
       name — nothing is being translated — so the heading says so rather than
       announcing "Live Translations" above a column of untranslated English.
       The settings stay where they are: a reader may be about to change
       language, and the tabs are how they would. */
    const transcribing = transcriptionMode || readingWhatIsSpoken();
    const dict = (i18n && i18n[displayLanguage]) || {};
    const fallback = (i18n && i18n.en) || {};
    const pick = (key, last) => dict[key] || fallback[key] || last;

    /* Set the key, not just the words. The heading carries data-i18n, so the
       shared translator rewrites it from that key every time the language is
       applied — writing only the text here worked until the next such pass
       put "Live Translations" straight back over the top of it. */
    if (mainTitleText) {
        const key = transcribing ? 'liveTranscriptions' : 'liveTranslations';
        mainTitleText.setAttribute('data-i18n', key);
        mainTitleText.textContent = pick(key, transcribing
            ? 'Live Transcription' : 'Live Translations');
    }
    if (emptyStateText) {
        const key = transcribing ? 'waitingTranscriptions' : 'waitingTranslations';
        emptyStateText.setAttribute('data-i18n', key);
        emptyStateText.textContent = pick(key, transcribing
            ? 'Waiting for transcriptions...' : 'Waiting for translations...');
    }
    if (emptyStateDesc) {
        emptyStateDesc.textContent = pick('waitingDesc',
            transcribing ? 'Transcriptions will appear here in real-time'
                         : 'Translations will appear here in real-time');
    }
    console.log(transcribing ? 'Showing what was said' : 'Showing translations');
}

/* ===================================
   UI Controls
   =================================== */

function toggleMobileMenu() {
    setSidebarOpen(!isSidebarOpen());
}

/* PatternFly owns the sidebar's state. Below xl the panel is a drawer that
   .pf-m-expanded slides in; from xl it is a column that .pf-m-collapsed folds
   away, and the page's main container widens into the space. One toggle, two
   classes, because which one applies depends on the width. */
function sidebarIsWide() {
    return window.matchMedia('(min-width: 75rem)').matches;
}

function isSidebarOpen() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return false;
    return sidebarIsWide()
        ? !sidebar.classList.contains('pf-m-collapsed')
        : sidebar.classList.contains('pf-m-expanded');
}

function setSidebarOpen(open) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');
    if (!sidebar) return;
    const wide = sidebarIsWide();
    sidebar.classList.toggle('pf-m-collapsed', wide && !open);
    sidebar.classList.toggle('pf-m-expanded', !wide && open);
    if (overlay) overlay.classList.toggle('active', open && !wide);
    if (toggle) {
        toggle.classList.toggle('active', open);
        toggle.setAttribute('aria-expanded', String(open));
    }
}

function closeMobileMenu() {
    // Only the drawer closes on its own; folding the desktop panel away
    // because someone pressed a button in it would be a surprise.
    if (!sidebarIsWide()) setSidebarOpen(false);
}

function toggleMobileSearch() {
    // PatternFly's expandable search animates itself: the one class is the
    // whole of the state, and the component grows the field, fades the icon
    // out and the close button in. What was here hid one element and showed
    // another, which happens in a single frame and reads as a jump.
    const group = document.getElementById('mobileSearchBar');
    const toggle = document.getElementById('mobileSearchToggle');
    if (!group) return;
    const open = !group.classList.contains('pf-m-expanded');

    group.classList.toggle('pf-m-expanded', open);
    if (toggle) toggle.setAttribute('aria-expanded', String(open));

    const searchInput = document.getElementById('searchInputMobile');
    if (open) {
        if (searchInput) setTimeout(() => searchInput.focus(), 100);
    } else if (searchInput && searchInput.value) {
        // Leaving search puts the list back the way it was.
        searchInput.value = '';
        handleSearch();
    }
}

function showAbout() {
    document.getElementById('aboutModal').classList.add('active');
}

function hideAbout(event) {
    if (!event || event.target.id === 'aboutModal' || event.target.classList.contains('about-close')) {
        document.getElementById('aboutModal').classList.remove('active');
    }
}

function toggleTheme() {
    // theme.js paints it, and crossfades the page while it does. The label
    // changes inside the same fade rather than a frame before it.
    toggleThemeTo(updateThemeUI);
}

// ── Landscape / kiosk caption mode ───────────────────────────────────────────
// When phone rotates landscape, collapse sidebar and maximise the caption area.
(function _landscapeWatcher() {
    function applyOrientation() {
        const isLandscape = window.matchMedia('(orientation: landscape) and (max-height: 500px)').matches;
        document.documentElement.setAttribute('data-landscape', isLandscape ? 'true' : 'false');
    }
    applyOrientation();
    window.addEventListener('orientationchange', () => setTimeout(applyOrientation, 150));
    window.addEventListener('resize', applyOrientation);
})();


function updateThemeUI(theme) {
    const text = document.getElementById('themeText');
    // The icon is two PatternFly SVGs in the markup and CSS shows the one that
    // matches the theme, so nothing here writes a glyph into the page, and
    // theme.js has already put the page in the theme this is labelling.
    if (theme === 'dark') {
        if (text) text.textContent = t('lightMode', 'Light Mode');
    } else {
        if (text) text.textContent = t('darkMode', 'Dark Mode');
    }
}

function resetSettings() {
    if (!confirm(i18n[displayLanguage]?.confirmReset || 'Reset all settings to default?')) {
        return;
    }

    // Clear all settings from localStorage
    localStorage.removeItem('displayMode');
    localStorage.removeItem('targetLang');
    localStorage.removeItem('selectedVoice');
    localStorage.removeItem('ttsRate');
    localStorage.removeItem('ttsVolume');
    localStorage.removeItem('theme');
    localStorage.removeItem('fontSize');
    localStorage.removeItem('displayLanguage');
    localStorage.removeItem('uiMode');

    console.log('Settings reset to defaults');

    // Reload page to apply defaults
    location.reload();
}

function showSyncIndicator() {
    const indicator = document.getElementById('syncIndicator');
    indicator.classList.add('show');
    setTimeout(function () {
        indicator.classList.remove('show');
    }, 3000);
}

/* ===================================
   View Mode (standard / accessibility / elderly)
   =================================== */
function applyUIMode(mode) {
    const valid = { standard: 1, accessibility: 1, elderly: 1 };
    const m = valid[mode] ? mode : 'standard';
    // On the root, where the stylesheet looks for it and where data-theme
    // already lives. Written to the body, it matched nothing: picking
    // Accessibility or Elderly stored the choice and changed nothing on the
    // page, before or after a reload.
    document.documentElement.setAttribute('data-ui-mode', m);
    const sel = document.getElementById('uiMode');
    if (sel && sel.value !== m) sel.value = m;
}
function updateUIMode() {
    const sel = document.getElementById('uiMode');
    if (!sel) return;
    const m = sel.value || 'standard';
    applyUIMode(m);
    try { localStorage.setItem('uiMode', m); } catch (e) {}
    const labelMap = {
        standard: t('uiMode_standard', 'Standard'),
        accessibility: t('uiMode_accessibility', 'Accessibility'),
        elderly: t('uiMode_elderly', 'Elderly')
    };
    if (typeof showToast === 'function') {
        showToast(t('uiMode', 'View Mode') + ': ' + labelMap[m], 'info', 2000);
    }
}
function loadUIMode() {
    let saved = 'standard';
    try { saved = localStorage.getItem('uiMode') || 'standard'; } catch (e) {}
    applyUIMode(saved);
}

/* ===================================
   Toast Notifications (additive helper)
   =================================== */
const MAX_VISIBLE_TOASTS = 4;
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    const container = document.getElementById('toastContainer');
    if (!container) {
        console.log('[toast]', type, message);
        return;
    }
    while (container.children.length >= MAX_VISIBLE_TOASTS) {
        container.firstChild.remove();
    }

    // PatternFly's alert, in the toast alert group. The group is a <ul>, so
    // each alert is wrapped in the group's item.
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

    // The group animates an item in from off-stage and out again.
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
function t(key, fallback) {
    return (i18n && i18n[displayLanguage] && i18n[displayLanguage][key])
        || (i18n && i18n.en && i18n.en[key])
        || fallback;
}

/* ===================================
   Connection Status helper (additive)
   =================================== */
function setConnectionStatus(state) {
    const badge = document.getElementById('statusBadge');
    if (!badge) return;
    const known = { online: 'online', offline: 'offline', waiting: 'waiting' };
    // PatternFly label modifiers carry the state colour. This function
    // rewrites className wholesale, so they are set here rather than in the
    // template, where they would be wiped on the first status change.
    const mod = { online: 'pf-m-green', offline: 'pf-m-red', waiting: 'pf-m-orange' };
    const cls = known[state] || 'waiting';
    badge.className = 'pf-v6-c-label ' + mod[cls] + ' connection-badge ' + cls;
    const sp = badge.querySelector('.pf-v6-c-label__text');
    if (sp) sp.textContent = t(cls, sp.textContent || cls);
    // The icon says the state too, so the word can step aside on a narrow
    // masthead without the label going silent. The title carries it either way.
    const ico = document.getElementById('statusBadgeIcon');
    if (ico) {
        ico.innerHTML = svgIcon({ online: 'check-circle', offline: 'exclamation-circle',
                                  waiting: 'info-circle' }[cls]);
    }
    badge.title = t(cls, cls);
}

/* ===================================
   Modal helpers for shortcuts/welcome (additive)
   =================================== */
let __modalLastFocus = null;
let __activeModalId = null;
const __FOCUSABLE_SEL = 'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';
function __getFocusable(modal) {
    return Array.prototype.filter.call(
        modal.querySelectorAll(__FOCUSABLE_SEL),
        function (el) { return el.offsetParent !== null || el === document.activeElement; }
    );
}
function __trapFocus(e) {
    if (e.key !== 'Tab' || !__activeModalId) return;
    const m = document.getElementById(__activeModalId);
    if (!m || !m.classList.contains('active')) return;
    const items = __getFocusable(m);
    if (!items.length) { e.preventDefault(); return; }
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
}
document.addEventListener('keydown', __trapFocus, true);
function __openModal(id) {
    try { __modalLastFocus = document.activeElement; } catch (e) { __modalLastFocus = null; }
    const m = document.getElementById(id);
    if (!m) return;
    m.classList.add('active');
    __activeModalId = id;
    // Focus the first focusable element (or close button)
    setTimeout(function () {
        const items = __getFocusable(m);
        const closeBtn = m.querySelector('.about-close');
        const target = closeBtn || items[0];
        if (target) try { target.focus(); } catch (e) {}
    }, 50);
}
function __closeModal(id) {
    const m = document.getElementById(id);
    if (m) m.classList.remove('active');
    if (__activeModalId === id) __activeModalId = null;
    if (__modalLastFocus && typeof __modalLastFocus.focus === 'function') {
        try { __modalLastFocus.focus(); } catch (e) {}
    }
    __modalLastFocus = null;
}
function showShortcuts() { __openModal('shortcutsModal'); }
function hideShortcuts(event) {
    if (event && event.target !== event.currentTarget) return;
    __closeModal('shortcutsModal');
}
function showWelcome() { __openModal('welcomeModal'); }
function hideWelcome(event) {
    if (event && event.target !== event.currentTarget) return;
    __closeModal('welcomeModal');
    try { localStorage.setItem('onboardingSeen_v1', '1'); } catch (e) {}
}

/* ===================================
   Feature Tour (multi-step guide)
   =================================== */
let __tourStep = 0;
function __tourSteps() {
    return [
        { icon: 'microphone', titleKey: 'tour_s1_title', titleFb: 'Live Translation', bodyKey: 'tour_s1_body',
          bodyFb: 'As the host speaks, transcriptions and translations appear here in real time. Newer cards stack at the top.' },
        { icon: 'globe', titleKey: 'tour_s2_title', titleFb: 'Choose Your Language', bodyKey: 'tour_s2_body',
          bodyFb: 'Use "Display Language" in the sidebar to change the interface, and "Target Language" to control the translation output.' },
        { icon: 'volume-up', titleKey: 'tour_s3_title', titleFb: 'Listen with TTS', bodyKey: 'tour_s3_body',
          bodyFb: 'Enable Text-to-Speech to hear translations read aloud automatically. Adjust voice, speed and volume in the sidebar.' },
        { icon: 'edit', titleKey: 'tour_s4_title', titleFb: 'Cards & Actions', bodyKey: 'tour_s4_body',
          bodyFb: 'Each card has a copy button and a replay button. The Cached badge means the result was served instantly from cache.' },
        { icon: 'search', titleKey: 'tour_s5_title', titleFb: 'Search & Export', bodyKey: 'tour_s5_body',
          bodyFb: 'Use the search bar to filter the visible list. Export keeps your full history as TXT, JSON, CSV or SRT subtitles.' },
        { icon: 'wheelchair', titleKey: 'tour_s6_title', titleFb: 'View Modes', bodyKey: 'tour_s6_body',
          bodyFb: 'Switch between Standard, Accessibility (larger focus, bigger tap targets) and Elderly (large text and buttons) in Settings.' },
        { icon: 'keyboard', titleKey: 'tour_s7_title', titleFb: 'Shortcuts', bodyKey: 'tour_s7_body',
          bodyFb: 'Press "?" anytime to see keyboard shortcuts. Press "/" to focus search, "g" to scroll to top, "Esc" to close dialogs.' }
    ];
}
function __renderTour() {
    const steps = __tourSteps();
    const total = steps.length;
    if (__tourStep < 0) __tourStep = 0;
    if (__tourStep >= total) __tourStep = total - 1;
    const step = steps[__tourStep];
    const iconEl = document.getElementById('tourStepIcon');
    const titleEl = document.getElementById('tourStepTitle');
    const bodyEl = document.getElementById('tourStepBody');
    const dotsEl = document.getElementById('tourDots');
    const progEl = document.getElementById('tourProgress');
    const prevBtn = document.getElementById('tourPrev');
    const nextBtn = document.getElementById('tourNext');
    if (!bodyEl) return;
    if (iconEl) iconEl.innerHTML = svgIcon(step.icon);
    if (titleEl) titleEl.textContent = t(step.titleKey, step.titleFb);
    bodyEl.innerHTML = '';
    const p = document.createElement('p');
    p.textContent = t(step.bodyKey, step.bodyFb);
    bodyEl.appendChild(p);
    if (dotsEl) {
        // PatternFly's progress stepper: a step is done, current, or still to
        // come, and each one is a button so the tour can be jumped through.
        dotsEl.replaceChildren();
        steps.forEach(function (s, i) {
            const state = i < __tourStep ? 'pf-m-success'
                : i === __tourStep ? 'pf-m-current' : 'pf-m-pending';
            const li = document.createElement('li');
            li.className = 'pf-v6-c-progress-stepper__step ' + state;
            if (i === __tourStep) li.setAttribute('aria-current', 'step');
            const connector = document.createElement('div');
            connector.className = 'pf-v6-c-progress-stepper__step-connector';
            const icon = document.createElement('span');
            icon.className = 'pf-v6-c-progress-stepper__step-icon';
            // A finished step is ticked; the current and the coming ones are
            // the plain circles PatternFly draws for them.
            if (state === 'pf-m-success') icon.innerHTML = svgIcon('check');
            connector.appendChild(icon);
            const main = document.createElement('div');
            main.className = 'pf-v6-c-progress-stepper__step-main';
            const title = document.createElement('button');
            title.type = 'button';
            title.className = 'pf-v6-c-progress-stepper__step-title pf-v6-c-button pf-m-inline pf-m-link';
            title.textContent = t(s.titleKey, s.titleFb);
            title.onclick = function () { __tourStep = i; __renderTour(); };
            main.appendChild(title);
            li.append(connector, main);
            dotsEl.appendChild(li);
        });
    }
    if (progEl) progEl.textContent = (__tourStep + 1) + ' / ' + total;
    if (prevBtn) prevBtn.disabled = (__tourStep === 0);
    if (nextBtn) {
        // Writing to the button flattened PatternFly's markup: the text span
        // it carries is what the button lays out, and its data-i18n key is
        // what re-translates it when the reading language changes.
        const label = nextBtn.querySelector('.pf-v6-c-button__text') || nextBtn;
        const last = __tourStep === total - 1;
        label.setAttribute('data-i18n', last ? 'tour_done' : 'tour_next');
        label.textContent = last ? t('tour_done', 'Done') : t('tour_next', 'Next');
    }
}
function showTour() {
    __tourStep = 0;
    const m = document.getElementById('tourModal');
    if (m) {
        m.classList.add('active');
        __renderTour();
    }
    // also mark welcome as seen
    try { localStorage.setItem('onboardingSeen_v1', '1'); } catch (e) {}
}
function hideTour(event) {
    if (event && event.target !== event.currentTarget) return;
    const m = document.getElementById('tourModal');
    if (m) m.classList.remove('active');
}
function tourPrev() { __tourStep--; __renderTour(); }
function tourNext() {
    const total = __tourSteps().length;
    if (__tourStep >= total - 1) { hideTour(); return; }
    __tourStep++;
    __renderTour();
}

/* ===================================
   Translation cache metadata (additive)
   Tracks whether a cacheKey result came from the server-side cache.
   =================================== */
window.__translationCacheMeta = window.__translationCacheMeta || {};

function markCacheHit(elem) {
    if (!elem) return;
    // The marks sit in the meta row, next to the corrected label.
    const marks = elem.querySelector('.card-marks');
    if (!marks || marks.querySelector('.card-badge.cache-hit')) return;
    const badge = document.createElement('span');
    badge.className = 'pf-v6-c-label pf-m-compact pf-m-outline card-badge cache-hit';
    badge.title = t('cacheHitTooltip', 'Served from translation cache');
    const content = document.createElement('span');
    content.className = 'pf-v6-c-label__content';
    const text = document.createElement('span');
    text.className = 'pf-v6-c-label__text';
    text.textContent = t('cacheHit', 'Cached');
    content.appendChild(text);
    badge.appendChild(content);
    marks.appendChild(badge);
}


function updateFontSize() {
    fontSize = parseInt(document.getElementById('fontSizeSlider').value);
    localStorage.setItem('fontSize', fontSize);
    applyFontSize();
}

function applyFontSize() {
    const style = document.getElementById('dynamicFontStyle');
    if (style) {
        style.textContent = `.text-target, .sc-line { font-size: ${fontSize}px !important; }`;
    } else {
        const newStyle = document.createElement('style');
        newStyle.id = 'dynamicFontStyle';
        newStyle.textContent = `.text-target, .sc-line { font-size: ${fontSize}px !important; }`;
        document.head.appendChild(newStyle);
    }
}

/* ===================================
   Search Functionality
   =================================== */

function handleSearch() {
    const desktopInput = document.getElementById('searchInput');
    const mobileInput = document.getElementById('searchInputMobile');
    const clearBtn = document.getElementById('searchClear');
    const clearBtnMobile = document.getElementById('searchClearMobile');

    if (document.activeElement === desktopInput && mobileInput) {
        mobileInput.value = desktopInput.value;
    } else if (document.activeElement === mobileInput && desktopInput) {
        desktopInput.value = mobileInput.value;
    }

    const rawQuery = (desktopInput ? desktopInput.value : mobileInput.value).trim();

    // Validate and sanitize search input
    if (rawQuery.length > 500) {
        console.warn('Search query too long');
        return;
    }

    searchQuery = sanitizeInput(rawQuery).toLowerCase();

    if (searchQuery) {
        if (clearBtn) clearBtn.style.display = 'block';
        if (clearBtnMobile) clearBtnMobile.style.display = 'block';
    } else {
        if (clearBtn) clearBtn.style.display = 'none';
        if (clearBtnMobile) clearBtnMobile.style.display = 'none';
    }

    performSearch();
}

/* ===================================
   Page Visibility Management (Resource Optimization)
   =================================== */
function handleVisibilityChange() {
    pageVisible = !document.hidden;
    
    if (pageVisible) {
        console.log('Page visible - resuming translations');
        // Optionally sync when page becomes visible again
    } else {
        console.log('Page hidden - pausing translation loads');
        // Clear the loading flag so scroll doesn't get stuck
        isLoadingMore = false;
    }
}

function clearSearch() {
    const desktopInput = document.getElementById('searchInput');
    const mobileInput = document.getElementById('searchInputMobile');
    const clearBtn = document.getElementById('searchClear');
    const clearBtnMobile = document.getElementById('searchClearMobile');

    if (desktopInput) desktopInput.value = '';
    if (mobileInput) mobileInput.value = '';
    searchQuery = '';

    if (clearBtn) clearBtn.style.display = 'none';
    if (clearBtnMobile) clearBtnMobile.style.display = 'none';

    performSearch();
}

function performSearch() {
    visibleTranslationIds.clear();
    let matchCount = 0;

    translations.forEach(function (item) {
        const searchableText = (item.corrected + ' ' + (item.translated || '')).toLowerCase();
        const matches = !searchQuery || searchableText.includes(searchQuery);

        if (matches) {
            visibleTranslationIds.add(item.id);
            matchCount++;
        }

        const card = document.getElementById('translation-' + item.id);
        if (card) {
            if (matches) {
                card.style.display = 'block';
                highlightSearchText(card, searchQuery);
            } else {
                card.style.display = 'none';
            }
        }
    });
}

function highlightSearchText(card, query) {
    const sourceDiv = card.querySelector('.text-source');
    const targetDiv = card.querySelector('.text-target');

    [sourceDiv, targetDiv].forEach(function (div) {
        if (!div) return;
        const originalText = div.getAttribute('data-original-text') || div.textContent;
        if (!div.getAttribute('data-original-text')) {
            div.setAttribute('data-original-text', originalText);
        }

        if (!query) {
            // Restore original plain text (no highlights, no HTML).
            div.textContent = originalText;
            div.removeAttribute('data-original-text');
            return;
        }

        // Build highlighted output safely using DOM nodes — never innerHTML
        // with user-controlled text. Splits the original on regex matches
        // and inserts <mark> elements with textContent for the hit pieces.
        const regex = new RegExp(escapeRegex(query), 'gi');
        div.textContent = '';
        let lastIndex = 0;
        let m;
        while ((m = regex.exec(originalText)) !== null) {
            if (m.index > lastIndex) {
                div.appendChild(document.createTextNode(
                    originalText.slice(lastIndex, m.index)
                ));
            }
            const mark = document.createElement('mark');
            mark.className = 'search-highlight';
            mark.textContent = m[0];
            div.appendChild(mark);
            lastIndex = m.index + m[0].length;
            // Guard against zero-width matches causing an infinite loop.
            if (m.index === regex.lastIndex) regex.lastIndex++;
        }
        if (lastIndex < originalText.length) {
            div.appendChild(document.createTextNode(originalText.slice(lastIndex)));
        }
    });
}

function escapeRegex(str) {
    return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/* ===================================
   Translation Functions
   =================================== */

async function translateText(text, targetLang) {
    const cacheKey = text + '_' + targetLang;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) return cached;

    try {
        // Map internal language codes to Google Translate API codes
        const GOOGLE_TRANSLATE_LANG_MAP = {
            'zh': 'zh-CN',      // Simplified Chinese
            'zh-tw': 'zh-TW',   // Traditional Chinese
            'yue': 'yue',       // Cantonese
            'ja': 'ja',
            'ko': 'ko',
            'es': 'es',
            'fr': 'fr',
            'de': 'de',
            'ru': 'ru',
            'ar': 'ar',
            'pt': 'pt',
            'it': 'it',
            'nl': 'nl',
            'pl': 'pl',
            'tr': 'tr',
            'vi': 'vi',
            'th': 'th',
            'id': 'id',
            'ms': 'ms',
            'hi': 'hi',
            'ta': 'ta',
            'en': 'en'
        };
        
        let translationLang = GOOGLE_TRANSLATE_LANG_MAP[targetLang] || targetLang;
        
        // Split long text into sentences to avoid truncation
        // Google Translate API can truncate responses for very long texts
        const splitThreshold = 1500; // Character threshold for splitting
        let translated = null;
        
        if (text.length > splitThreshold) {
            console.log('Text length:', text.length, '- splitting for better translation...');
            translated = await translateLongText(text, targetLang, translationLang);
        } else {
            translated = await performSingleTranslation(text, targetLang, translationLang);
        }

        if (translated && translated !== text && !translated.includes('(translation failed)')) {
            sessionStorage.setItem(cacheKey, translated);
            return translated;
        }
        
        return translated || text;
    } catch (error) {
        console.error('Translation error:', error);
        return text;
    }
}

async function performSingleTranslation(text, targetLang, translationLang) {
    try {
        let translated = text;

        // Try Cantonese first if target is Cantonese
        if (targetLang === 'yue') {
            try {
                const result = await translateViaApi(text, 'yue');
                if (result && result.length > 0) {
                    translated = result;
                    console.log('Cantonese translation successful (' + result.length + ' chars):', result.substring(0, 80) + (result.length > 80 ? '...' : ''));
                    return translated;
                }
                console.warn('Cantonese translation response empty or malformed');
            } catch (err) {
                console.warn('Cantonese translation failed, falling back to zh-TW:', err.message);
                translationLang = 'zh-TW';
            }
        }

        // Standard translation
        console.log('Translating to (' + translationLang + ') - text length:', text.length, 'chars');
        
        const result = await translateViaApi(text, translationLang);
        
        if (result && result.length > 0) {
            console.log('Translation successful (' + result.length + ' chars):', result.substring(0, 80) + (result.length > 80 ? '...' : ''));
            return result;
        }
        
        console.warn('Translation response empty or malformed');
        return text;
        
    } catch (error) {
        console.error('Translation error:', error.message);
        return text;
    }
}

async function translateViaApi(text, targetLang) {
    // Use Unit Separator (U+001F) — guaranteed to never appear in user text — to avoid
    // boundary ambiguity if the text itself contains a pipe character.
    const cacheKey = `${text}\u001f${targetLang}`;
    
    // 1️⃣ Check local cache first
    if (translationCache[cacheKey]) {
        console.log('Using local cache:', translationCache[cacheKey].substring(0, 80));
        return translationCache[cacheKey];
    }
    
    // 2️⃣ Throttle: wait for a slot in the translation queue
    await waitForTranslationSlot();

    // Re-check cache (another request may have translated while waiting)
    if (translationCache[cacheKey]) {
        releaseTranslationSlot();
        return translationCache[cacheKey];
    }

    // 3️⃣ Try backend translation (single attempt, no aggressive retry).
    // Wrap the slot-using region in try/finally so any unexpected throw
    // (network, parse, abort, refactor footgun) can never leak the
    // concurrency counter and deadlock subsequent translations.
    let backendResult = null;
    let rateLimited = false;
    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const response = await fetch('/api/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: text, target_lang: targetLang, room: window.CURRENT_ROOM_ID || 'main' }),
            signal: controller.signal
        });
        clearTimeout(timeoutId);

        if (response.status === 429) {
            console.warn('Rate limited, backing off 5s...');
            rateLimited = true;
        } else if (!response.ok) {
            throw new Error('Status ' + response.status);
        } else {
            const data = await response.json();
            if (data.success && data.translated) {
                translationCache[cacheKey] = data.translated;
                try { window.__translationCacheMeta[cacheKey] = !!data.cached; } catch (e) {}
                backendResult = data.translated;
            }
        }
    } catch (error) {
        console.warn('Backend translation failed:', error.message);
    } finally {
        releaseTranslationSlot();
    }

    if (backendResult) return backendResult;

    if (rateLimited) {
        await new Promise(resolve => setTimeout(resolve, 5000));
        return await translateViaClientFallback(text, targetLang, cacheKey);
    }

    // 4️⃣ Backend failed, try client-side translation
    return await translateViaClientFallback(text, targetLang, cacheKey);
}

function waitForTranslationSlot() {
    // Throttle concurrent translations to avoid hitting rate limits
    return new Promise(function(resolve) {
        function tryAcquire() {
            if (translationConcurrency < MAX_TRANSLATION_CONCURRENCY) {
                translationConcurrency++;
                resolve();
            } else {
                setTimeout(tryAcquire, TRANSLATION_DELAY_MS);
            }
        }
        tryAcquire();
    });
}

function releaseTranslationSlot() {
    translationConcurrency = Math.max(0, translationConcurrency - 1);
}

/* The reader's own browser, asking directly.
 *
 * The server cannot reach this endpoint: it is Google's undocumented gtx one,
 * and it answers a browser but refuses Python's TLS stack with 429 — measured
 * side by side on one machine, 200 in 0.9s from the browser against 429 every
 * time from requests and urllib. So every translation went to the server,
 * waited out three retries and 30 seconds, and came back as the English it
 * started with.
 *
 * The browser can simply ask. That is the whole fallback, and it is what this
 * function always claimed to be — what was here tried a browser API that does
 * not exist and then a table of word replacements.
 */
async function translateViaClientFallback(text, targetLang, cacheKey) {
    try {
        const url = 'https://translate.googleapis.com/translate_a/single'
            + '?client=gtx&sl=auto&dt=t&tl=' + encodeURIComponent(targetLang)
            + '&q=' + encodeURIComponent(text);
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 8000);
        const response = await fetch(url, { signal: controller.signal });
        clearTimeout(timer);
        if (response.ok) {
            const data = await response.json();
            // The response is [[[chunk, source, ...], ...], ...]; a long
            // sentence comes back in several chunks and they join in order.
            const chunks = (data && data[0]) || [];
            const translated = chunks.map(c => (c && c[0]) || '').join('').trim();
            if (translated && translated !== text) {
                translationCache[cacheKey] = translated;
                return translated;
            }
        }
    } catch (e) {
        console.warn('Direct translation failed:', e.message);
    }

    try {
        const clientTranslated = await tryClientTranslation(text, targetLang);
        if (clientTranslated && clientTranslated !== text) {
            translationCache[cacheKey] = clientTranslated;
            return clientTranslated;
        }
    } catch (e) {
        console.warn('Client translation fallback failed:', e.message);
    }
    console.warn('All translation methods failed, showing original text');
    return '';
}

async function tryClientTranslation(text, targetLang) {
    // Simple client-side translation using available resources
    // This is a minimal fallback - you can enhance with better translation engines
    
    try {
        // Try to use Web Translate API if available (Chrome, etc.)
        if (typeof browser !== 'undefined' && browser.translations) {
            try {
                const translator = await browser.translations.getTranslator({
                    sourceLanguage: 'en',
                    targetLanguage: targetLang
                });
                return await translator.translate(text);
            } catch (e) {
                console.debug('Browser Translation API unavailable:', e.message);
            }
        }
        
        // Fallback: Try simple word replacement for common languages
        return tryBasicTranslation(text, targetLang);
    } catch (e) {
        console.error('Client translation error:', e);
        return null;
    }
}

function tryBasicTranslation(text, targetLang) {
    // Very basic fallback dictionary for common words
    // This is minimal and only helps with very simple cases
    const basicDict = {
        'zh-tw': {
            'hello': '你好', 'goodbye': '再見', 'thank you': '謝謝', 'please': '請',
            'yes': '是', 'no': '不是', 'ok': '好的', 'good': '很好'
        },
        'zh': {
            'hello': '你好', 'goodbye': '再见', 'thank you': '谢谢', 'please': '请',
            'yes': '是', 'no': '不是', 'ok': '好的', 'good': '很好'
        }
    };
    
    const dict = basicDict[targetLang];
    if (!dict) return null;
    
    let result = text.toLowerCase();
    for (const [en, translated] of Object.entries(dict)) {
        result = result.replace(new RegExp('\\b' + en + '\\b', 'gi'), translated);
    }
    
    // Only return if something was actually translated
    return (result !== text.toLowerCase()) ? result : null;
}

function extractAllTranslations(data) {
    // Google Translate API returns different structures for different languages
    // Simplified Chinese: splits into multiple segments in data[0]
    // Traditional Chinese: returns as single complete segment in data[0][0][0]
    
    if (!data || !Array.isArray(data) || data.length === 0) {
        console.warn('extractAllTranslations: data is empty or not array');
        return '';
    }
    
    console.log('API Response - data[0] length:', data[0] ? data[0].length : 'undefined');
    
    // Method 1: Iterate through all items in data[0] and collect all translations
    // This handles BOTH single-segment (zh-tw) and multi-segment (zh) responses
    if (data[0] && Array.isArray(data[0])) {
        let result = '';
        let foundCount = 0;
        
        for (let i = 0; i < data[0].length; i++) {
            const item = data[0][i];
            
            // Check if item is [translation, original, ...]
            if (Array.isArray(item) && item.length > 0) {
                const segment = item[0];
                if (typeof segment === 'string' && segment.trim().length > 0) {
                    result += segment;
                    foundCount++;
                }
            }
        }
        
        if (foundCount > 0) {
            console.log('Merged', foundCount, 'segment(s):', result.substring(0, 80) + (result.length > 80 ? '...' : ''));
            return result;
        }
    }
    
    // Method 2: Deep search for any string values in the response (fallback)
    console.log('Trying deep search...');
    const allText = searchForTranslations(data);
    if (allText && allText.length > 0) {
        console.log('Deep search found:', allText.length, 'chars');
        return allText;
    }
    
    console.warn('Could not extract translation from any method');
    return '';
}

function searchForTranslations(obj, visited = new Set(), maxDepth = 10) {
    // Recursively search for text that looks like translations
    if (maxDepth <= 0 || visited.has(obj)) return '';
    
    if (typeof obj === 'string') {
        // Return strings that look like they could be translations (not URLs, metadata, etc)
        if (obj.length > 2 && obj.length < 5000 && !obj.includes('://')) {
            return obj;
        }
        return '';
    }
    
    if (!obj || typeof obj !== 'object') return '';
    
    visited.add(obj);
    let result = '';
    
    if (Array.isArray(obj)) {
        for (let i = 0; i < Math.min(obj.length, 20); i++) {
            const nested = searchForTranslations(obj[i], visited, maxDepth - 1);
            if (nested && nested.length > 0) {
                result = nested; // Return the first non-empty string found
                break;
            }
        }
    } else {
        const keys = Object.keys(obj);
        for (let key of keys) {
            const nested = searchForTranslations(obj[key], visited, maxDepth - 1);
            if (nested && nested.length > 0) {
                result = nested;
                break;
            }
        }
    }
    
    return result;
}

async function translateLongText(text, targetLang, translationLang) {
    try {
        // Split by sentences: periods, question marks, exclamation marks, or newlines
        const sentenceRegex = /[。！？!?.；;\n]+/;
        let sentences = text.split(sentenceRegex).filter(s => s.trim().length > 0);
        
        // If still too few sentences, split by commas for longer segments
        if (sentences.length < 3) {
            sentences = text.split(/[，,、；;\n]+/).filter(s => s.trim().length > 0);
        }
        
        console.log('Splitting long text into', sentences.length, 'segments');
        
        // Translate each sentence
        const translatedSentences = [];
        for (let i = 0; i < sentences.length; i++) {
            const segment = sentences[i].trim();
            if (segment.length === 0) continue;
            
            try {
                const result = await performSingleTranslation(segment, targetLang, translationLang);
                translatedSentences.push(result);
                
                // Add small delay to avoid rate limiting
                if (i < sentences.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 100));
                }
            } catch (err) {
                console.warn('Failed to translate segment', i, ':', err.message);
                translatedSentences.push(segment); // Fallback to original
            }
        }
        
        // Rejoin with original delimiters preserved
        let result = translatedSentences.join('');
        console.log('Long text translation complete:', result.substring(0, 50) + '...');
        return result;
        
    } catch (error) {
        console.error('Long text translation error:', error.message);
        return text;
    }
}

/* ===================================
   Text-to-Speech Functions
   =================================== */

function speakText(text, isAutoPlay = false) {
    // Validate and sanitize text before speaking
    const validation = validateText(text, 5000);
    if (!validation.valid) {
        console.error('Invalid text for TTS:', validation.error);
        return;
    }

    const cleanText = validation.text.replace(/\s*\([^)]*\)\s*/g, '').trim();
    if (!cleanText) return;

    // Enqueue instead of playing directly
    enqueueTTSPlayback(cleanText, isAutoPlay);
}

// ===== NEW: TTS Queue Management =====
function enqueueTTSPlayback(text, isAutoPlay = false) {
    const now = Date.now();
    
    // Check if this is a double-tap on the same text (within 500ms)
    if (!isAutoPlay && text === lastTTSClickText && (now - lastTTSClickTime) < TTS_DOUBLE_TAP_THRESHOLD) {
        console.log('Double-tap detected! Stopping TTS playback...');
        clearTTSQueue();
        lastTTSClickText = '';
        lastTTSClickTime = 0;
        return;
    }
    
    // Update click tracking for manual plays (not auto)
    if (!isAutoPlay) {
        lastTTSClickText = text;
        lastTTSClickTime = now;
    }
    
    // Add to queue instead of playing immediately
    ttsQueue.push({text, isAutoPlay});
    console.log(`Queued TTS (auto=${isAutoPlay}): ${text.substring(0, 50)}... Queue length: ${ttsQueue.length}`);
    
    // Start processing queue if nothing is currently playing
    if (!isTTSPlaying) {
        processTTSQueue();
    }
}

function processTTSQueue() {
    // Process next item in queue
    if (ttsQueue.length === 0) {
        isTTSPlaying = false;
        console.log('TTS Queue empty');
        return;
    }
    
    if (isTTSPlaying) {
        console.log('TTS still playing, waiting...');
        return;
    }
    
    const item = ttsQueue.shift();
    console.log(`Playing from queue (auto=${item.isAutoPlay}): ${item.text.substring(0, 50)}...`);
    
    isTTSPlaying = true;
    
    if (ttsEngine === 'system') {
        speakTextSystem(item.text);
    } else if (ttsEngine === 'edge') {
        speakTextEdge(item.text);
    }
}

function clearTTSQueue() {
    // Clear all pending TTS and stop current playback
    console.log(`Clearing TTS queue (${ttsQueue.length} items)`);
    ttsQueue = [];
    isTTSPlaying = false;
    
    // Stop current playback
    if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
    }
    if (currentAudioElement) {
        currentAudioElement.pause();
        currentAudioElement.src = '';
        currentAudioElement = null;
    }
    currentUtterance = null;
}

function speakTextSystem(text) {
    // Use Web Speech API (System TTS) 
    if (!('speechSynthesis' in window)) {
        showToast(t('toast_ttsUnsupported', 'Your browser does not support text-to-speech'), 'warning');
        isTTSPlaying = false;
        processTTSQueue();
        return;
    }

    // Cancel any previous utterance
    if (currentUtterance) {
        speechSynthesis.cancel();
    }
    
    speechSynthesis.cancel();

    const utterance = new SpeechSynthesisUtterance(text);
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
    utterance.lang = ttsLang;
    utterance.rate = ttsRate;
    utterance.volume = ttsVolume;

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log('Using selected system voice: ' + selectedVoice.name);
    } else {
        const voices = speechSynthesis.getVoices();
        let autoVoice = voices.find(function (v) {
            return v.lang === ttsLang;
        });
        if (!autoVoice) {
            const baseLang = ttsLang.split('-')[0];
            autoVoice = voices.find(function (v) {
                return v.lang.startsWith(baseLang + '-');
            });
        }
        if (autoVoice) {
            utterance.voice = autoVoice;
            console.log('Using auto system voice: ' + autoVoice.name);
        }
    }

    utterance.onend = function () {
        console.log('System TTS finished');
        currentUtterance = null;
        isTTSPlaying = false;
        // Process next in queue
        processTTSQueue();
    };

    utterance.onerror = function (e) {
        console.error('System TTS error:', e);
        isTTSPlaying = false;
        // Process next in queue even on error
        processTTSQueue();
    };

    currentUtterance = utterance;
    speechSynthesis.speak(utterance);
}

async function speakTextEdge(text) {
    // Use Edge TTS (Cloud-based)
    try {
        console.log('Sending text to Edge TTS...');

        // Token is delivered asynchronously via the 'ready' socket event.
        // Briefly poll for it (up to ~2s) before failing — otherwise an
        // early click after page load would error out with "no token".
        if (!apiSessionToken) {
            for (let i = 0; i < 20 && !apiSessionToken; i++) {
                await new Promise(r => setTimeout(r, 100));
            }
        }
        if (!apiSessionToken) {
            throw new Error('Waiting for server connection... Please try again in a moment');
        }
        
        const selectedVoiceValue = document.getElementById('voiceSelect').value;
        
        const response = await fetch('/api/tts/synthesize', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${apiSessionToken}`
            },
            body: JSON.stringify({
                text: text,
                lang: TTS_LANG_MAP[targetLang] || targetLang,
                voice: selectedVoiceValue || null
            })
        });
        
        if (!response.ok) {
            const contentType = response.headers.get('content-type');
            let error = 'TTS synthesis failed';
            let errorDetail = '';
            
            if (contentType && contentType.includes('application/json')) {
                try {
                    const errorData = await response.json();
                    error = errorData.error || error;
                    errorDetail = errorData.error || '';
                } catch (e) {
                    // Couldn't parse JSON
                }
            }
            
            console.error(`TTS Response error: status=${response.status}, content-type=${contentType}`);
            console.error(`Error detail: ${errorDetail}`);
            
            // Provide user-friendly error messages
            if (response.status === 503) {
                throw new Error('Edge TTS service is temporarily unavailable. Please try again later.');
            } else if (response.status === 429) {
                throw new Error('Too many TTS requests. Please wait a moment and try again.');
            } else {
                throw new Error(error);
            }
        }
        
        // Log response details
        const contentType = response.headers.get('content-type');
        console.log(`TTS Response: status=${response.status}, content-type=${contentType}`);
        
        // Get audio blob
        const audioBlob = await response.blob();
        console.log(`Audio blob: size=${audioBlob.size}, type=${audioBlob.type}`);
        
        // Play audio
        const audioUrl = URL.createObjectURL(audioBlob);
        const audio = new Audio();
        audio.src = audioUrl;
        audio.volume = ttsVolume;
        
        currentAudioElement = audio;
        
        audio.onerror = function (e) {
            console.error('Edge TTS playback error:', e);
            isTTSPlaying = false;
            processTTSQueue();
        };
        
        audio.onended = function () {
            console.log('Edge TTS finished');
            URL.revokeObjectURL(audioUrl);
            currentAudioElement = null;
            isTTSPlaying = false;
            // Process next in queue
            processTTSQueue();
        };
        
        audio.play().catch(function (e) {
            console.error('Failed to play Edge TTS audio:', e);
            isTTSPlaying = false;
            processTTSQueue();
        });
        
        console.log('Edge TTS audio playing...');
    } catch (error) {
        console.error('Edge TTS error:', error);
        isTTSPlaying = false;
        processTTSQueue();
        showToast(t('toast_ttsError', 'TTS error') + ': ' + error.message, 'danger');
    }
}

/* The masthead's speaker button and the one in the settings dialog are the
   same switch; this keeps the masthead one showing the state. */
function syncTTSQuickToggle() {
    const quick = document.getElementById('ttsQuickToggle');
    if (!quick) return;
    /* PatternFly does have a pressed look for a plain button: pf-m-clicked,
       which is what its own masthead toggles use. What was here instead was a
       grey box and a blue icon written by hand, a combination belonging to no
       state in the design system, and beside five plain black icons it read as
       a button stuck under the cursor rather than a switch that is on.

       The plate is quiet by design, so the icon carries the state as well: a
       speaker with waves when it is reading, a crossed-out one when it is
       not. That is the same signal every media player gives, and it does not
       depend on telling two shades of grey apart. */
    quick.classList.toggle('pf-m-clicked', ttsEnabled);
    quick.setAttribute('aria-pressed', String(ttsEnabled));
    quick.innerHTML = svgIcon(ttsEnabled ? 'volume-up' : 'volume-mute');
    const label = ttsEnabled
        ? t('textToSpeechOff', 'Stop reading aloud')
        : t('textToSpeech', 'Read aloud');
    quick.setAttribute('title', label);
    quick.setAttribute('aria-label', label);
}

function toggleTTS(next) {
    /* Called by the switch in the settings, by the icon in the masthead and by
       the wizard, so the new state is passed in when the caller knows it and
       worked out here when it does not. The switch shows the state itself;
       nothing has to relabel a button any more. */
    ttsEnabled = typeof next === 'boolean' ? next : !ttsEnabled;
    localStorage.setItem('ttsEnabled', ttsEnabled);

    const box = document.getElementById('toggleTTS');
    if (box && box.checked !== ttsEnabled) box.checked = ttsEnabled;
    syncTTSQuickToggle();

    if (ttsEnabled) {
        showToast(t('textToSpeechOn', 'Reading translations aloud'), 'success');
    } else {
        showToast(t('textToSpeechOff', 'Stop reading aloud'), 'info');
        // Clear TTS queue and stop current playback when disabling
        clearTTSQueue();
    }
}

/* Hearing the voice before the sermon starts is the point of the setting, and
   there was no way to do it without waiting for a line to arrive. Reads the
   most recent translation if there is one, so what is heard is the real
   thing, and a sample sentence otherwise. */
function testVoice() {
    const latest = translations.find(function (item) {
        return item && item.translated;
    });
    const sample = latest ? latest.translated : t('tts_sample',
        'This is how the translations will sound.');
    clearTTSQueue();
    speakText(sample, false);
}

function updateRate() {
    ttsRate = parseFloat(document.getElementById('rateSlider').value);
    localStorage.setItem('ttsRate', ttsRate);
}

function updateVolume() {
    ttsVolume = parseFloat(document.getElementById('volumeSlider').value) / 100;
    localStorage.setItem('ttsVolume', ttsVolume);
}

/* ===================================
   Copy Functionality
   =================================== */

function copyTranslation(id) {
    const idStr = String(id);
    const item = translations.find(function (t) {
        return String(t.id) === idStr;
    });

    if (!item) {
        console.error('Translation not found:', id, 'Available IDs:', translations.map(t => t.id));
        return;
    }

    // In transcription mode, copy original text; in translation mode, copy translated text
    const textToCopy = displayMode === 'transcription' ? item.corrected : (item.translated || item.corrected);
    console.log('Attempting to copy:', textToCopy);

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(textToCopy).then(function () {
            console.log('Copied successfully with clipboard API');
            showCopyFeedback(id);
        }).catch(function (err) {
            console.log('Clipboard API failed, trying fallback:', err);
            copyWithFallback(id, textToCopy);
        });
    } else {
        console.log('Clipboard API not available, using fallback');
        copyWithFallback(id, textToCopy);
    }
}

function copyWithFallback(id, text) {
    try {
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.top = '0';
        textArea.style.left = '0';
        textArea.style.width = '2em';
        textArea.style.height = '2em';
        textArea.style.padding = '0';
        textArea.style.border = 'none';
        textArea.style.outline = 'none';
        textArea.style.boxShadow = 'none';
        textArea.style.background = 'transparent';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();

        const successful = document.execCommand('copy');
        document.body.removeChild(textArea);

        if (successful) {
            console.log('Copied successfully with fallback method');
            showCopyFeedback(id);
        } else {
            console.error('Fallback copy failed');
            showToast(t('toast_copyFailed', 'Failed to copy to clipboard'), 'danger');
        }
    } catch (err) {
        console.error('Fallback copy error:', err);
        showToast(t('toast_copyFailed', 'Failed to copy to clipboard'), 'danger');
    }
}

function showCopyFeedback(id) {
    const btn = document.getElementById('copy-btn-' + id);
    if (btn) {
        const span = btn.querySelector('span') || btn;
        const original = span.innerHTML;

        span.innerHTML = svgIcon('check');
        btn.classList.add('copied');

        setTimeout(function () {
            span.innerHTML = original;
            btn.classList.remove('copied');
        }, 2000);
    }
    // Also announce via toast (uses previously-unused i18n key)
    if (typeof showToast === 'function') {
        showToast(t('toast_copied', 'Copied to clipboard'), 'success', 1500);
    }
}

/* ===================================
   Rendering Functions
   =================================== */

async function renderTranslations() {
    const list = document.getElementById('translationsList');
    const itemCount = document.getElementById('itemCount');
    
    // Show total from server
    if (itemCount) itemCount.textContent = translationsTotal;

    if (translations.length === 0) {
        // Use i18n for translated empty state text
        const titleKey = (displayMode === 'transcription') ? 'waitingTranscriptions' : 'waitingTranslations';
        const descKey = 'waitingDesc';
        const emptyText = (i18n[displayLanguage] && i18n[displayLanguage][titleKey]) || (i18n['en'] && i18n['en'][titleKey]) || (displayMode === 'transcription' ? 'Waiting for transcriptions...' : 'Waiting for translations...');
        const emptyDesc = (i18n[displayLanguage] && i18n[displayLanguage][descKey]) || (i18n['en'] && i18n['en'][descKey]) || 'Translations will appear here in real-time';

        list.innerHTML = '\
            <div class="pf-v6-c-empty-state empty-state">\
                <div class="pf-v6-c-empty-state__content">\
                    <div class="pf-v6-c-empty-state__title">\
                        <h2 class="pf-v6-c-empty-state__title-text">' + emptyText + '</h2>\
                    </div>\
                    <div class="pf-v6-c-empty-state__body">' + emptyDesc + '</div>\
                </div>\
            </div>\
        ';
        return;
    }

    // ===== PERFORMANCE FIX: Virtual Scrolling with incremental rendering =====
    renderedCount = 0;
    isRenderingMore = false;
    list.innerHTML = '';  // Clear existing content
    
    // Render only first batch initially (30 items instead of ALL!)
    const initialBatch = Math.min(renderBatchSize, translations.length);
    console.log('Initial render: ' + initialBatch + ' of ' + translations.length + ' items (virtual scrolling)');
    await renderTranslationsBatch(0, initialBatch);
    
    // Setup virtual scrolling for remaining items
    setupVirtualScrolling();
    
    if (searchQuery) {
        performSearch();
    }
}

async function renderTranslationsBatch(startIdx, endIdx) {
    // Render a batch of translations - cards show immediately with original text,
    // translations fill in asynchronously in the background
    const list = document.getElementById('translationsList');
    
    if (startIdx >= translations.length) return;
    
    endIdx = Math.min(endIdx, translations.length);
    const batch = translations.slice(startIdx, endIdx);
    
    // Take the button off the end before appending; it goes back after.
    const oldFoot = document.getElementById('loadMoreRow');
    if (oldFoot) oldFoot.remove();
    
    // Build HTML for all items in batch synchronously
    // (createTranslationHTML no longer awaits translation - it fires translation in background)
    let htmlBatch = '';
    for (const item of batch) {
        htmlBatch += createTranslationHTML(item);
    }
    
    // Insert all at once
    if (startIdx === 0) {
        list.innerHTML = htmlBatch;
    } else {
        list.insertAdjacentHTML('beforeend', htmlBatch);
    }

    // Load Bible verse panels for this batch (async fetch from /api/bible/lookup).
    if (showBibleVerse && bibleFeatureAvailable) {
        for (const item of batch) {
            if (item.bible_refs && item.bible_refs.length) {
                const card = document.getElementById('translation-' + item.id);
                loadBiblePanel(card, item.bible_refs);
            }
        }
    }

    renderedCount = endIdx;
    console.log('Rendered items ' + startIdx + '-' + endIdx + '/' + translations.length);
    
    paintLoadMore();
}

/* The end of the list.
 *
 * What was here was a one-pixel sentinel and an IntersectionObserver with a
 * 500px margin: scrolling near the bottom fetched the next thirty lines and
 * rendered them, and then the next thirty, with no end and nobody asking. A
 * service with a thousand lines in it ended up with a thousand rows in the
 * page, every one of them holding its text, its buttons and any verse it
 * found, on a phone that has been in someone's hand for an hour.
 *
 * A button instead. Nothing is fetched or drawn until someone asks for it, and
 * what it costs is visible in the number on the button. */
function paintLoadMore() {
    const list = document.getElementById('translationsList');
    if (!list) return;
    const existing = document.getElementById('loadMoreRow');
    if (existing) existing.remove();

    const inMemory = translations.length - renderedCount;
    const remaining = Math.max(0, inMemory) + (hasMoreTranslations
        ? Math.max(0, translationsTotal - translations.length) : 0);
    if (remaining <= 0) return;

    const row = document.createElement('div');
    row.className = 'load-more';
    row.id = 'loadMoreRow';

    const button = document.createElement('button');
    button.className = 'pf-v6-c-button pf-m-secondary';
    button.type = 'button';
    button.id = 'loadMoreButton';
    button.onclick = loadMoreClicked;

    const label = document.createElement('span');
    label.className = 'pf-v6-c-button__text';
    label.setAttribute('data-i18n', 'loadMore');
    label.textContent = t('loadMore', 'Show earlier lines');
    button.appendChild(label);

    // How many are waiting, in the badge the headings on this page use. A
    // reader deciding whether to press it should be able to see the size of
    // what they are asking for.
    const count = document.createElement('span');
    count.className = 'pf-v6-c-badge pf-m-read';
    count.textContent = String(remaining);
    button.appendChild(document.createTextNode(' '));
    button.appendChild(count);

    row.appendChild(button);
    list.appendChild(row);
}

/* Draw what is already here first, and only go to the server when this
   browser has run out of lines to draw. */
async function loadMoreClicked() {
    const button = document.getElementById('loadMoreButton');
    if (button) {
        button.disabled = true;
        /* Going to the server for the next batch takes as long as it takes,
           and a button that only greys out does not say whether it heard the
           press. PatternFly's in-progress button does: the spinner is part of
           the component, not something drawn beside it. */
        button.classList.add('pf-m-progress', 'pf-m-in-progress');
        const progress = document.createElement('span');
        progress.className = 'pf-v6-c-button__progress';
        progress.innerHTML = '<span class="pf-v6-c-spinner pf-m-md" role="progressbar"'
            + ' aria-label="Loading">'
            + '<span class="pf-v6-c-spinner__clipper"></span>'
            + '<span class="pf-v6-c-spinner__lead-ball"></span>'
            + '<span class="pf-v6-c-spinner__ball"></span></span>';
        button.insertBefore(progress, button.firstChild);
    }
    try {
        if (renderedCount < translations.length) {
            await renderMoreVisibleItems();
        } else if (hasMoreTranslations && !isLoadingMore) {
            await loadMoreTranslations();
        }
    } finally {
        paintLoadMore();
    }
}
window.loadMoreClicked = loadMoreClicked;

/* The list draws in batches, and the button at its end asks for the next one.
   Nothing here watches the scroll position any more. */

function setupVirtualScrolling() {
    paintLoadMore();
}

async function renderMoreVisibleItems() {
    // Render next batch of items when user scrolls near bottom
    if (isRenderingMore || renderedCount >= translations.length) return;
    
    isRenderingMore = true;
    var nextBatchEnd = Math.min(renderedCount + renderBatchSize, translations.length);
    
    console.log('Virtual scroll: rendering items ' + renderedCount + '-' + nextBatchEnd + '...');
    await renderTranslationsBatch(renderedCount, nextBatchEnd);
    
    isRenderingMore = false;
}

/* Kept because other code still calls them. Nothing watches the scroll
   position: the list ends in a button, and it is pressed or it is not. */
function setupScrollListener() {}

function onTranslationsScroll(event) {}

async function loadInitialTranslations() {
    // Load first batch of translations from server
    if (!apiSessionToken) {
        console.warn('No API token yet, skipping translation load');
        return;
    }

    // Claim this call's sequence slot; only the last caller may commit.
    const mySeq = ++_translationsLoadSeq;

    try {
        translationsOffset = 0;
        const response = await fetch(
            '/api/translations?offset=0&limit=' + translationsLimit
            + '&api_token=' + encodeURIComponent(apiSessionToken)
            + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main')
        );

        if (mySeq !== _translationsLoadSeq) return; // a newer call already won

        if (response.ok) {
            const data = await response.json();
            if (mySeq !== _translationsLoadSeq) return; // check again after await

            translations = data.translations || [];
            translationsTotal = data.total || 0;
            hasMoreTranslations = data.has_more || false;
            translationsOffset = 0;

            // Persist to localStorage so the next page-load shows cached data
            // immediately rather than waiting for the server round-trip.
            if (translations.length) {
                try {
                    localStorage.setItem(_CACHE_KEY, JSON.stringify(translations.slice(0, _CACHE_LIMIT)));
                } catch (e) {}
            }

            console.log('Loaded ' + translations.length + ' translations (total: ' + translationsTotal + ')');
            await renderTranslations();
        } else if (response.status === 401) {
            console.warn('API token rejected (401) — waiting for ready event with fresh token');
        } else {
            console.warn('Failed to load translations: ' + response.status);
        }
    } catch (error) {
        console.error('Error loading translations:', error);
    }
}

async function loadMoreTranslations() {
    // Load next batch of translations
    if (isLoadingMore || !hasMoreTranslations) {
        console.log(`Cannot load more: isLoadingMore=${isLoadingMore}, hasMore=${hasMoreTranslations}`);
        return;
    }
    
    isLoadingMore = true;
    translationsOffset += translationsLimit;
    
    console.log(`Loading more at offset ${translationsOffset}, limit ${translationsLimit}...`);
    
    try {
        const response = await fetch(
            '/api/translations?offset=' + translationsOffset + '&limit=' + translationsLimit
            + '&api_token=' + encodeURIComponent(apiSessionToken)
            + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main')
        );
        
        if (response.ok) {
            const data = await response.json();
            const newTranslations = data.translations || [];
            
            console.log(`Got ${newTranslations.length} more items (has_more=${data.has_more})`);
            
            // Append to existing translations (newest at bottom)
            translations.push(...newTranslations);
            hasMoreTranslations = data.has_more || false;
            translationsTotal = data.total || 0;
            
            console.log(`Loaded ${newTranslations.length} more translations (${translations.length} visible, ${translationsTotal} total, has_more=${hasMoreTranslations})`);
            
            // Only render the new items (append to DOM)
            if (newTranslations.length > 0) {
                const startIdx = renderedCount;
                renderedCount = translations.length;
                await renderTranslationsBatch(startIdx, translations.length);
            }
        } else {
            console.error(`Failed to load more: ${response.status}`);
        }
    } catch (error) {
        console.error('Error loading more translations:', error);
        translationsOffset -= translationsLimit;  // Rollback offset
    } finally {
        isLoadingMore = false;
    }
}

// Keep the DOM bounded: remove the oldest (bottom) cards once we exceed the cap.
// Only trims while the user is near the top reading the newest items, so it never
// yanks away a card someone has scrolled down to read. The trimmed items remain in
// the `translations` array and are re-rendered from memory on scroll-down via the
// virtual-scroll sentinel.
function trimRenderedCards() {
    const list = document.getElementById('translationsList');
    if (!list) return;
    const mainSection = document.querySelector('.pf-c-page__main-section');
    if (mainSection && mainSection.scrollTop > 1200) return;

    const cards = list.getElementsByClassName('translation-card'); // live collection
    if (cards.length <= MAX_RENDERED_CARDS) return;
    while (cards.length > MAX_RENDERED_CARDS) {
        cards[cards.length - 1].remove();
        if (renderedCount > 0) renderedCount--;
    }

    // The trimmed lines are still in memory, so the button offers them again.
    paintLoadMore();
}

async function addTranslation(data) {
    const list = document.getElementById('translationsList');
    const emptyState = list.querySelector('.empty-state');

    // Clear empty state if present
    if (emptyState) {
        list.innerHTML = '';
    }

    // Add to translations array (at beginning since it's newest)
    translations.unshift(data);
    translationsTotal++;
    renderedCount++;  // Track that we rendered one more item

    // Keep client-side cache fresh (newest _CACHE_LIMIT items)
    try {
        localStorage.setItem(_CACHE_KEY, JSON.stringify(translations.slice(0, _CACHE_LIMIT)));
    } catch (e) {}
    
    // Create HTML for new item (synchronous - translation happens in background)
    const html = createTranslationHTML(data);
    
    // Insert at beginning of list instead of re-rendering all
    if (list.firstChild) {
        list.insertAdjacentHTML('afterbegin', html);
    } else {
        list.innerHTML = html;
    }
    
    // Update count to show server total
    const itemCount = document.getElementById('itemCount');
    if (itemCount) itemCount.textContent = translationsTotal;

    // Bound the DOM so a long live session doesn't accumulate thousands of cards.
    trimRenderedCards();

    // Load Bible verse panel (async fetch from /api/bible/lookup)
    if (showBibleVerse && bibleFeatureAvailable && data.bible_refs && data.bible_refs.length) {
        const card = document.getElementById('translation-' + data.id);
        loadBiblePanel(card, data.bible_refs);
    }

    // Trigger background translation if needed
    const itemId = 'translation-' + data.id;
    if (displayMode !== 'transcription' && data.id) {
        translateInBackground(data, itemId);
    }

    if (searchQuery) {
        performSearch();
    }
}

async function processPendingTranslations() {
    // Process queued new_translation events in batch to avoid rate limiting
    newTranslationTimer = null;
    
    if (pendingNewTranslations.length === 0) return;
    
    // Take all pending translations
    const batch = pendingNewTranslations.splice(0);
    console.log('Processing ' + batch.length + ' pending translations');
    
    // Add them one at a time with a small delay between each
    for (let i = 0; i < batch.length; i++) {
        const data = batch[i];
        await addTranslation(data);
        
        // Only speak the latest one (translation mode only)
        if (ttsEnabled && displayMode !== 'transcription' && i === 0 && data.translated) {
            const row = document.getElementById('translation-' + data.id);
            if (willBecomeVerse(data)) deferSpeech(row);
            else speakText(data.translated, true);
        }
        
        // Small delay between items to avoid UI freeze and rate limits
        if (i < batch.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 100));
        }
    }
}

/* PatternFly's label, in the green outline the design system uses for a
   quiet positive mark. The pill this replaces was drawn by hand in the
   stylesheet and looked like nothing else on the page. */
/* The short tag that says which language the quiet line under a translation
   is in. Without it the two lines are just a big one and a small one, and
   which is the original is anyone's guess. */
function langTag(code) {
    const c = String(code || '').toLowerCase();
    // Typed in by the admin rather than spoken: there is no language to name.
    if (!c || c === 'manual' || c === 'auto') return '';
    if (c.startsWith('yue')) return 'YUE';
    if (c.startsWith('zh-tw') || c.includes('-hant')) return 'ZH-TW';
    return (c.split('-')[0] || '').toUpperCase();
}

function correctedLabel() {
    return '<span class="pf-v6-c-label pf-m-green pf-m-compact pf-m-outline card-badge">'
        + '<span class="pf-v6-c-label__content">'
        + '<span class="pf-v6-c-label__text">' + escapeHtml(t('corrected', 'Corrected'))
        + '</span></span></span>';
}

/* Said plainly, on the line the translation should have been on. The words
   above it are the English that was spoken — all the app has — and a reader
   who cannot read them is entitled to know that is why, and to ask again. */
function failedNote(id) {
    return '<p class="sc-offer translate-failed">'
        + '<span>' + escapeHtml(t('translateFailed', 'Could not translate this line'))
        + ' — </span>'
        + '<button class="pf-v6-c-button pf-m-inline pf-m-link" type="button"'
        + ' onclick="retryTranslation(' + id + ')">'
        + '<span class="pf-v6-c-button__text">' + escapeHtml(t('retry', 'Try again'))
        + '</span></button></p>';
}

function retryTranslation(id) {
    const item = translations.find(t => String(t.id) === String(id));
    if (!item) return;
    item.translated = null;
    item.translationFailed = false;
    renderTranslations();
    translateInBackground(item, 'translation-' + item.id);
}
window.retryTranslation = retryTranslation;

/* A stored "translation" that is word for word the English it came from is not
   a translation — it is the fallback a failed call returned, saved as though
   it had worked. Lines translated while the server could not reach the
   endpoint are all like this, and they would never try again. */
function echoesSource(item) {
    return (item.translated || '').trim() === (item.corrected || '').trim();
}

function createTranslationHTML(item) {
    const itemId = 'translation-' + item.id;
    const itemSourceLang = item.source_language || item.language || 'en';

    // ── transcription mode: the spoken words are the answer ──────────────
    if (displayMode === 'transcription') {
        return streamGroup({
            id: itemId,
            timestamp: item.timestamp,
            tag: '',
            body: '<p class="stream-zh text-target">' + escapeHtml(item.corrected || '') + '</p>',
            meta: '',
            marks: item.is_corrected ? correctedLabel() : '',
            itemNo: item.id,
            speakText: item.corrected || '',
            playing: false
        });
    }

    // ── translation mode ─────────────────────────────────────────────────
    const langMap = {
        en: 'en', zh: 'zh', yue: 'yue', ja: 'ja', ko: 'ko', es: 'es', fr: 'fr',
        de: 'de', ru: 'ru', ar: 'ar', pt: 'pt', it: 'it', nl: 'nl', pl: 'pl',
        tr: 'tr', vi: 'vi', th: 'th', id: 'id', ms: 'ms', hi: 'hi', ta: 'ta'
    };
    const normalizedSourceLang = langMap[itemSourceLang] || itemSourceLang;

    if (sameLanguage(itemSourceLang, targetLang)) {
        // Nothing to translate when the listener is reading the language being
        // spoken: the original is the answer.
        item.translated = item.corrected;
        item.currentLang = targetLang;
    } else if (item.translated && item.translated_lang === targetLang
               && !echoesSource(item)) {
        item.currentLang = targetLang;
    } else if (!item.translated || item.currentLang !== targetLang
               || echoesSource(item)) {
        item.currentLang = targetLang;
        item.translated = null;
        translateInBackground(item, itemId);
    }

    const isTranslating = !item.translated;
    const translatedText = item.translated || '';

    // The English under the line, when it says something the line does not.
    const sourceDiffers = (item.corrected || '').trim() !== (translatedText || '').trim();
    const showSource = showSourceText
        && !sameLanguage(normalizedSourceLang, targetLang)
        && (isTranslating || sourceDiffers);
    const meta = showSource ? escapeHtml(item.corrected || '') : '';

    // While the round trip is out, the row holds a bar the width of a line
    // rather than a spinner: the space is what carries the wait.
    const body = isTranslating
        ? '<p class="stream-zh text-target stream-pending"><span class="wait-bar"></span>'
          + '<span class="wait">' + escapeHtml(t('translating', 'Translating…')) + '</span></p>'
        : '<p class="stream-zh text-target">' + escapeHtml(translatedText) + '</p>'
          + (item.translationFailed ? failedNote(item.id) : '');

    return streamGroup({
        id: itemId,
        timestamp: item.timestamp,
        tag: '',
        body: body,
        meta: meta,
        marks: item.is_corrected ? correctedLabel() : '',
        itemNo: item.id,
        speakText: translatedText,
        playing: false
    });
}

/* One row of the stream, as the design spec lays it out: the timestamp is the
   term, the translation the value, the English the quiet line under it, and
   the two buttons sit at the end of the row. Everything user.js used to build
   as a card goes through here, so there is one shape to keep right. */
function streamGroup(o) {
    return '\
        <div class="pf-v6-c-description-list__group translation-card' + (o.playing ? ' is-playing' : '') + '" id="' + o.id + '">\
            <dt class="pf-v6-c-description-list__term">\
                <span class="pf-v6-c-description-list__text">\
                    <span class="card-time">' + escapeHtml(o.timestamp || '') + '</span>' + (o.tag || '') + '\
                </span>\
            </dt>\
            <dd class="pf-v6-c-description-list__description">\
                <div class="pf-v6-c-description-list__text stream-row">\
                    <div class="stream-text">\
                        ' + o.body + '\
                        <span class="meta text-source"' + (o.meta ? ' data-original-text="' + o.meta + '"' : '') + '>' + (o.meta || '') + '</span>\
                        <div class="card-marks">' + (o.marks || '') + '</div>\
                    </div>\
                    <div class="stream-actions card-actions">\
                        <button class="pf-v6-c-button pf-m-plain copy-btn" type="button" id="copy-btn-' + o.itemNo + '" data-translation-id="' + o.itemNo + '" onclick="copyTranslationFromButton(this)" aria-label="Copy this line">\
                            <span class="pf-v6-c-button__icon">' + svgIcon('copy') + '</span>\
                        </button>\
                        <button class="pf-v6-c-button pf-m-plain tts-icon" type="button" onclick="speakText(this.getAttribute(\'data-text\'))" data-text="' + escapeHtml(o.speakText || '') + '" aria-label="Read this line aloud">\
                            <span class="pf-v6-c-button__icon">' + svgIcon('volume-up') + '</span>\
                        </button>\
                    </div>\
                </div>\
            </dd>\
        </div>\
    ';
}

/* ===================================
   AI Thinking Status Machine
   =================================== */

function getRandomStatus(lang, stage) {
    const lib = window.sharedAiStatusLibrary || {};
    const statuses = (lib[lang] || lib['en'] || {})[stage] || [];
    return statuses[Math.floor(Math.random() * statuses.length)] || 'Processing...';
}

// Status machine for element
function startListeningStateMachine(element, tempId) {
    // Enhanced state rotation with smart transition to understanding
    if (!element || element._listeningMachine) return;
    
    element._listeningMachine = true;
    const lang = displayLanguage;
    const lib = window.sharedAiStatusLibrary || {};
    const listeningStatuses = (lib[lang] || lib['en'] || {}).listening || [];
    let statusIndex = 0;
    const startTime = Date.now();
    
    const listeningTimer = setInterval(() => {
        if (!element || !element.parentElement) {
            clearInterval(listeningTimer);
            element._listeningMachine = false;
            // Clean up tracking
            if (tempId && activeChunkTracking[tempId]) {
                delete activeChunkTracking[tempId];
            }
            return;
        }
        
        // Cycle through listening statuses every ~1 second (psychological effect)
        const status = listeningStatuses[statusIndex % listeningStatuses.length];
        element.textContent = status;
        statusIndex++;
    }, PSYCHOLOGICAL_STATUS_CHANGE_MS);
    
    element._listeningTimer = listeningTimer;
    
    // Return the timer for external control
    return listeningTimer;
}

function stopListeningStateMachine(element) {
    if (!element) return;
    if (element._listeningTimer) {
        clearInterval(element._listeningTimer);
        element._listeningTimer = null;
    }
    element._listeningMachine = false;
}

function checkAndTransitionToUnderstanding(element, tempId, currentText) {
    // Intelligent check: should we transition from listening to understanding?
    // Criteria: word count >= threshold OR punctuation detected
    
    if (!element || !tempId) return false;
    
    const tracking = activeChunkTracking[tempId];
    if (!tracking) return false;
    
    // Already transitioned
    if (tracking.hasTransitionedToUnderstanding) return false;
    
    // Check word count
    const words = currentText.trim().split(WORD_BOUNDARY_REGEX).filter(w => w.length > 0);
    const wordCount = words.length;
    
    // Check for punctuation
    const hasPunctuation = PUNCTUATION_MARKERS.test(currentText);
    
    // Transition if: reached min words OR detected punctuation
    if (wordCount >= LISTENING_MIN_WORD_COUNT || hasPunctuation) {
        console.log('Transitioning to understanding: wordCount=' + wordCount + ', hasPunctuation=' + hasPunctuation);
        tracking.hasTransitionedToUnderstanding = true;
        
        // Stop listening state machine
        stopListeningStateMachine(element);
        element._listeningMachine = false;
        
        // Start understanding state machine
        startIntermediateStateMachine(element, tempId, 'understanding');
        return true;
    }
    
    return false;
}

function startIntermediateStateMachine(element, tempId, startStage = 'understanding') {
    // Psychological buffer stage machine for "thinking" effect with adaptive timing
    // Implements: understanding (0-4s) → preparing (4-6s) → translating (6s+) → translated (showing results)
    // With animation effects and adaptive speed based on text length
    
    if (!element || element._intermediateMachine) return;
    
    element._intermediateMachine = true;
    const lang = displayLanguage;
    const lib = window.sharedAiStatusLibrary || {};
    const stages = ['understanding', 'preparing', 'translating', 'translated'];
    const startIndex = stages.indexOf(startStage);
    const stageIndex = startIndex >= 0 ? startIndex : 0;
    
    const startTime = Date.now();
    let currentStageIndex = stageIndex;
    let statusIndex = 0;
    let animIndex = 0;
    
    // Calculate adaptive speed based on tracked text length
    const tracking = tempId ? activeChunkTracking[tempId] : null;
    const textLength = tracking ? tracking.text.length : 0;
    const wordCount = tracking ? tracking.text.split(WORD_BOUNDARY_REGEX).length : 0;
    
    // Always use dot animation (...) for all stages
    const DOT_PULSE = ['.', '..', '...', '..'];
    
    // Get adaptive status change duration based on stage and text length
    const getStatusChangeDuration = (stage) => {
        if (stage === 'understanding') {
            return 1200; // Understanding is always slow (dot animation)
        } else if (stage === 'preparing') {
            return wordCount > 20 ? 1200 : 800;
        } else {
            return wordCount > 20 ? 1200 : 800;
        }
    };
    
    const baseStatusChangeDuration = getStatusChangeDuration(startStage);
    
    console.log('Intermediate machine started:', { stage: startStage, wordCount, animStyle: 'dots', duration: baseStatusChangeDuration + 'ms' });
    
    let lastStatusChangeTime = startTime;
    const updateInterval = 200; // Update animation every 200ms
    let currentStatusChangeDuration = baseStatusChangeDuration;
    const isLongText = wordCount > 20;
    
    // For long text, can pick from any stage; for short text, stay in current stage
    // 'translated' is only used in explicit API response phase, not during thinking
    const allStages = ['listening', 'understanding', 'preparing', 'translating'];
    
    const intermediateTimer = setInterval(() => {
        if (!element || !element.parentElement) {
            clearInterval(intermediateTimer);
            element._intermediateMachine = false;
            return;
        }
        
        const elapsedMs = Date.now() - startTime;
        
        // Auto-progress through stages based on time (psychological timing)
        if (elapsedMs > PREPARING_AUTO_PROGRESS_MS && currentStageIndex < 2) {
            currentStageIndex = 2; // Jump to translating
            currentStatusChangeDuration = 1200; // Long sentences always slow
        } else if (elapsedMs > UNDERSTANDING_AUTO_PROGRESS_MS && currentStageIndex < 1) {
            currentStageIndex = 1; // Jump to preparing
            currentStatusChangeDuration = isLongText ? 1200 : 800;
        }
        
        // Change status text at currentStatusChangeDuration intervals
        const timeSinceLastStatusChange = Date.now() - lastStatusChangeTime;
        if (timeSinceLastStatusChange > currentStatusChangeDuration) {
            // For long text: randomly pick from any of the 5 stages
            // For short text: stay within current stage
            let pickedStatus;
            if (isLongText) {
                const randomStage = allStages[Math.floor(Math.random() * allStages.length)];
                const stageOptions = (lib[lang] || lib['en'] || {})[randomStage] || [];
                if (stageOptions.length > 0) {
                    pickedStatus = stageOptions[Math.floor(Math.random() * stageOptions.length)];
                } else {
                    pickedStatus = 'Processing';
                }
            } else {
                // Short text: stick with current stage
                const currentStage = stages[currentStageIndex];
                const stageStatuses = (lib[lang] || lib['en'] || {})[currentStage] || [];
                if (stageStatuses.length > 0) {
                    pickedStatus = stageStatuses[statusIndex % stageStatuses.length];
                    statusIndex++;
                } else {
                    pickedStatus = 'Processing';
                }
            }
            
            const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
            element.textContent = (pickedStatus || 'Processing') + ' ' + animChar;
            animIndex++;
            lastStatusChangeTime = Date.now();
        } else {
            // Between status changes, just update the animation character
            const currentText = element.textContent || '';
            const parts = currentText.lastIndexOf(' ');
            if (parts > 0) {
                const statusText = currentText.substring(0, parts);
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = (statusText || 'Processing') + ' ' + animChar;
                animIndex++;
            } else if (currentText.length > 0) {
                // Ensure animation shows even if there's existing text
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = currentText + ' ' + animChar;
                animIndex++;
            } else {
                // No text yet, show animation with fallback
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = 'Processing ' + animChar;
                animIndex++;
            }
        }
    }, updateInterval);
    
    element._intermediateTimer = intermediateTimer;
    return intermediateTimer;
}

function stopIntermediateStateMachine(element) {
    if (!element) return;
    if (element._intermediateTimer) {
        clearInterval(element._intermediateTimer);
        element._intermediateTimer = null;
    }
    element._intermediateMachine = false;
}

function startAIThinkingMachine(element, startStage = 'understanding', maxDurationMs = 30000, sourceText = '') {
    if (!element || element._thinkingMachine) return; // Already running
    
    element._thinkingMachine = true;
    
    const lang = displayLanguage;
    const lib = window.sharedAiStatusLibrary || {};
    const stages = ['understanding', 'preparing', 'translating', 'translated'];
    // Only include 'translated' in allStages if explicitly starting with it
    const allStages = startStage === 'translated' 
        ? ['translated'] 
        : ['listening', 'understanding', 'preparing', 'translating'];
    const startIndex = stages.indexOf(startStage);
    const stageIndex = startIndex >= 0 ? startIndex : 0;
    
    const startTime = Date.now();
    let currentStageIndex = stageIndex;
    let lastStatusChangeTime = startTime;
    let animIndex = 0;
    
    // Always use dot animation (...)
    const DOT_PULSE = ['.', '..', '...', '..'];
    
    // Determine text length
    const wordCount = sourceText ? sourceText.split(WORD_BOUNDARY_REGEX).length : 0;
    const isLongText = wordCount > 20;
    
    console.log('AI thinking machine started:', { startStage, wordCount, isLongText, animStyle: 'dots' });
    
    const updateInterval = 200; // Update animation every 200ms
    
    const getStatusChangeDuration = (stage) => {
        // All stages use 1200ms for long text, 800ms / 700ms for short text
        if (isLongText) {
            return 1200;
        } else {
            return stage === 'understanding' ? 1200 : 700;
        }
    };
    
    const thinkingTimer = setInterval(() => {
        if (!element || !element.parentElement) {
            // Element removed, stop machine
            clearInterval(thinkingTimer);
            element._thinkingMachine = false;
            return;
        }
        
        const elapsedMs = Date.now() - startTime;
        
        // Progress through stages based on time (for short text only)
        if (!isLongText) {
            if (elapsedMs > 6000 && currentStageIndex < 2) {
                currentStageIndex = 2; // Jump to translating
            } else if (elapsedMs > 4000 && currentStageIndex < 1) {
                currentStageIndex = 1; // Jump to preparing
            }
        }
        
        // Get current stage (or random stage for long text)
        const currentStage = isLongText ? allStages[Math.floor(Math.random() * allStages.length)] : stages[currentStageIndex];
        const statusChangeDurationMs = getStatusChangeDuration(currentStage);
        
        // Change status text at statusChangeDurationMs intervals
        const timeSinceLastChange = Date.now() - lastStatusChangeTime;
        if (timeSinceLastChange > statusChangeDurationMs) {
            const statusOptions = (lib[lang] || lib['en'] || {})[currentStage] || [];
            let newStatus;
            if (statusOptions.length > 0) {
                newStatus = statusOptions[Math.floor(Math.random() * statusOptions.length)];
            } else {
                newStatus = 'Processing';
            }
            const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
            element.textContent = (newStatus || 'Processing') + ' ' + animChar;
            animIndex = 0; // Reset animation on new status
            lastStatusChangeTime = Date.now();
        } else {
            // Between status changes, just update the animation character
            const currentText = element.textContent || '';
            const parts = currentText.lastIndexOf(' ');
            if (parts > 0) {
                const statusText = currentText.substring(0, parts);
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = (statusText || 'Processing') + ' ' + animChar;
                animIndex++;
            } else if (currentText.length > 0) {
                // Ensure animation shows even if there's existing text
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = currentText + ' ' + animChar;
                animIndex++;
            } else {
                // No text yet, show animation with fallback
                const animChar = DOT_PULSE[animIndex % DOT_PULSE.length];
                element.textContent = 'Processing ' + animChar;
                animIndex++;
            }
        }
        
        // Stop if max duration exceeded
        if (elapsedMs > maxDurationMs) {
            clearInterval(thinkingTimer);
            element._thinkingMachine = false;
            console.log('Thinking machine stopped (max duration reached)');
        }
    }, updateInterval); // Update every 200ms
    
    element._thinkingTimer = thinkingTimer;
}

function stopAIThinkingMachine(element) {
    if (!element) return;
    
    if (element._thinkingTimer) {
        clearInterval(element._thinkingTimer);
        element._thinkingTimer = null;
    }
    element._thinkingMachine = false;
}

/* Hold the space a translation will need before it arrives.

   There is no streaming translation API: the English is final seconds before
   the translation lands. Until now the line was one row of status text that
   the translation then replaced, so every card below it jumped down the moment
   it arrived — and on a phone, mid-read. Measuring the English at the target's
   own size gives a close enough height (a CJK line runs about as wide as the
   English it came from), so the space is already there and nothing moves.

   Cheap to do and it never shrinks: min-height only ever holds a floor. */
function reserveTranslationSpace(textEl, sourceText) {
    if (!textEl || !sourceText) return;
    const held = textEl.textContent;
    textEl.style.minHeight = '';
    textEl.textContent = sourceText;
    const height = textEl.offsetHeight;
    const lineHeight = parseFloat(getComputedStyle(textEl).lineHeight) || 0;
    textEl.textContent = held;
    if (!height) return;
    // Capped at two lines. Reserving the full predicted height would hold the
    // card perfectly still, but a Chinese line runs shorter than the English it
    // came from, so a long source would leave a chasm under a short
    // translation — worse to look at than the shift it prevents. Two lines
    // covers what most lines turn out to be.
    const cap = lineHeight ? lineHeight * 2 : height;
    textEl.style.minHeight = Math.min(height, cap) + 'px';
}

/* What the speaker is speaking. Assumed English until a line says otherwise,
   because that is what this is usually used for; the moment a line arrives
   saying something else, it says so. */
let spokenLanguage = 'en';

function noteSpokenLanguage(item) {
    const said = (item && (item.source_language || item.language)) || '';
    if (!said || sameLanguage(said, spokenLanguage)) return;
    spokenLanguage = said;
    // The heading and the pair beneath it both describe the two languages, so
    // both have to be told when one of them turns out to be different.
    if (typeof updateDisplayMode === 'function') updateDisplayMode();
    if (typeof refreshReadingCard === 'function') refreshReadingCard();
}

/* Nothing is being translated when the reading language is the one being
   spoken: the page is showing what was said, not a translation of it. */
function readingWhatIsSpoken() {
    return sameLanguage(spokenLanguage, targetLang);
}

/* Is there anything to wait for? A line already in the language being read is
   not going to be translated, so nothing should behave as though it might be:
   no listening, no understanding, no refining. It is already the answer. */
function nothingToTranslate(item) {
    const spoken = (item && (item.source_language || item.language)) || '';
    return displayMode === 'transcription' || sameLanguage(spoken, targetLang);
}

/* The line, straight onto the row: no thinking sequence, no spinner, no round
   trip. Everything the finished translation would have done to the row is done
   here too — the play button, reading aloud, the stored text — because from
   the reader's side nothing about this row is different except that it was
   already in their language. */
function showWithoutTranslating(item, itemId, lang, textEl) {
    item.translated = item.corrected;
    item.currentLang = lang;
    item.translationFailed = false;

    const row = document.getElementById(itemId);
    if (!row) return;
    if (!textEl) textEl = row.querySelector('.text-target');

    if (textEl) {
        stopAIThinkingMachine(textEl);
        textEl.className = 'text-target';
        textEl.style.minHeight = '';
        textEl.textContent = item.translated;
        textEl.setAttribute('data-original-text', item.translated);
    }
    const spinner = row.querySelector('.card-actions .translating-indicator');
    if (spinner) spinner.remove();

    const ttsBtn = row.querySelector('.tts-icon');
    if (ttsBtn && row.getAttribute('data-speaks-verse') !== '1') {
        ttsBtn.setAttribute('data-text', item.translated);
    }
    if (ttsEnabled && displayMode !== 'transcription' && item.translated
            && row.getAttribute('data-await-verse') !== '1'
            && row.getAttribute('data-speaks-verse') !== '1') {
        speakText(item.translated, true);
    }
}

async function translateInBackground(item, itemId, textEl) {
    // Translate asynchronously and update DOM when done
    try {
        // Use item's current language if set, otherwise use global targetLang
        const lang = item.currentLang || targetLang;
        console.log('Starting translation for item ' + itemId + ', target lang: ' + lang + ', text length: ' + (item.corrected ? item.corrected.length : 0));

        /* Nothing to translate when the line is already in the language being
           read. The network call was skipped for this case, but the waiting
           was not: the row still ran the whole thinking sequence — reserving
           space, "Understanding", "Refining output" — before landing on the
           words it already had. English to English should simply appear. */
        if (sameLanguage(item.source_language || item.language || '', lang)) {
            showWithoutTranslating(item, itemId, lang, textEl);
            return;
        }

        // Immediately show "translated" status when API request starts
        const elem = document.getElementById(itemId);
        if (elem) {
            if (!textEl) {
                textEl = elem.querySelector('.text-target');
            }
            
            // Transition to "translated" state (showing "即將呈現翻譯")
            if (textEl) {
                stopAIThinkingMachine(textEl);
                textEl.className = 'text-target';
                reserveTranslationSpace(textEl, item.corrected);
                startAIThinkingMachine(textEl, 'translated', 30000, item.corrected);
                console.log('Switched to translated state, showing "即將呈現翻譯"');
            }
        }
        
        const spoken = item.source_language || item.language || '';
        const sameTongue = sameLanguage(spoken, lang);
        const translated = sameTongue
            ? item.corrected
            : await translateText(item.corrected, lang);
        item.translated = translated || item.corrected;
        item.currentLang = lang;

        // translateText hands back the original when the call times out or the
        // service refuses, so a failure and a success look identical: a reader
        // on 简体中文 just sees an English line and no reason for it. Two
        // different languages and the same words back is not a translation.
        item.translationFailed = !sameTongue
            && (item.translated || '').trim() === (item.corrected || '').trim();

        // Fire-and-forget: cache translation on server so future clients skip this call
        if (translated && item.id != null) {
            fetch('/api/translations/' + item.id + '/translated?api_token=' + encodeURIComponent(apiSessionToken) + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main'), {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ translated: translated, lang: lang })
            }).catch(() => {}); // silent — non-critical
        }

        console.log('Translation complete (' + item.translated.length + ' chars): ' + item.translated.substring(0, 100));
        
        // Update DOM if element still exists
        const elem2 = document.getElementById(itemId);
        if (elem2) {
            // Get text-target element if not already provided
            if (!textEl) {
                textEl = elem2.querySelector('.text-target');
            }
            
            // Stop AI thinking machine
            if (textEl) {
                stopAIThinkingMachine(textEl);
                console.log('Stopped AI thinking machine, showing translation');
            }
            
            // Remove the translating spinner from card-actions
            const cardActions = elem2.querySelector('.card-actions');
            if (cardActions) {
                const spinner = cardActions.querySelector('.translating-indicator');
                if (spinner) {
                    spinner.remove();
                }
            }

            if (textEl) {
                // Clear current thinking text, then animate the translation
                textEl.textContent = '';
                animateTextChange(textEl, '', item.translated, 300);
                
                textEl.setAttribute('data-original-text', item.translated);
                textEl.classList.remove('translating');
            }
            // If this translation came from server-side cache, surface a small badge
            try {
                const cKey = (item.corrected || '') + '\u001f' + lang;
                if (window.__translationCacheMeta && window.__translationCacheMeta[cKey]) {
                    markCacheHit(elem2);
                }
            } catch (e) {}
            // Update TTS button data
            const ttsBtn = elem2.querySelector('.tts-icon');
            if (ttsBtn && elem2.getAttribute('data-speaks-verse') !== '1') {
                ttsBtn.setAttribute('data-text', item.translated);
            }
            
            // Auto-play translated text if TTS is enabled (translation mode only)
            if (ttsEnabled && displayMode !== 'transcription' && item.translated
                    && elem2.getAttribute('data-await-verse') !== '1'
                    && elem2.getAttribute('data-speaks-verse') !== '1') {
                console.log('Auto-playing translation via TTS');
                speakText(item.translated, true);
            }
        }
    } catch (e) {
        console.warn('Background translation failed for item ' + itemId + ':', e.message);
    }
}

function copyTranslationFromButton(button) {
    const id = button.getAttribute('data-translation-id');
    console.log('Copy button clicked with ID:', id);
    copyTranslation(id);
}

// Keep escapeHtml for backward compatibility, but use sanitizeInput for consistency
function escapeHtml(text) {
    if (text === null || text === undefined) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}


/* ===================================
   Data Management
   =================================== */

// ── AI Summary via Web Share / clipboard ────────────────────────────────────
// The user sends the sermon text to their OWN AI app (ChatGPT, Gemini, Claude).
// Token cost is on the user's account — fully transparent, zero server cost.
async function shareForAI(service) {
    // Quick check before doing anything async
    if (translationsTotal === 0 && translations.length === 0) {
        showToast('No content to summarise yet.', 'warning');
        return;
    }

    // Prompt in target language + explicit instruction to reply in that language.
    // Sermon text is the original source (English) — don't use translated text
    // which would compound translation errors.
    const prompts = {
        zh:      '以下是一篇英文讲道的逐字稿。请用简体中文生成摘要，包含：主题、主要经文引用、3个核心要点。\n\n',
        'zh-tw': '以下是一篇英文講道的逐字稿。請用繁體中文生成摘要，包含：主題、主要經文引用、3個核心要點。\n\n',
        yue:     '以下係一篇英文講道嘅逐字稿。請用廣東話生成摘要，包含：主題、主要經文引用、3個核心要點。\n\n',
        ja:      '以下は英語の説教の逐語録です。日本語で要約を作成してください。内容：テーマ・主な聖書箇所・3つの重要ポイント。\n\n',
        ko:      '다음은 영어 설교의 축어록입니다. 한국어로 요약해 주세요. 주제, 주요 성경 구절, 핵심 포인트 3가지를 포함해 주세요.\n\n',
        id:      'Berikut adalah transkrip khotbah dalam bahasa Inggris. Tolong buat ringkasan dalam bahasa Indonesia, meliputi: tema, referensi Alkitab utama, dan 3 poin utama.\n\n',
        ms:      'Berikut ialah transkrip khotbah dalam bahasa Inggeris. Sila buat ringkasan dalam bahasa Melayu, termasuk: tema, rujukan Alkitab utama, dan 3 poin utama.\n\n',
        th:      'ต่อไปนี้คือบันทึกคำต่อคำของคำเทศนาภาษาอังกฤษ โปรดสรุปเป็นภาษาไทย โดยระบุ: หัวข้อ, ข้อพระคัมภีร์หลัก, และ 3 ประเด็นสำคัญ\n\n',
        vi:      'Sau đây là bản ghi chép nguyên văn bài giảng tiếng Anh. Vui lòng tóm tắt bằng tiếng Việt, bao gồm: chủ đề, các câu Kinh Thánh chính, và 3 điểm chính.\n\n',
        hi:      'निम्नलिखित अंग्रेजी उपदेश का शब्दशः प्रतिलेख है। कृपया हिंदी में सारांश बनाएं, जिसमें: विषय, मुख्य बाइबल संदर्भ और 3 मुख्य बिंदु शामिल हों।\n\n',
        ar:      'فيما يلي نص حرفي لعظة باللغة الإنجليزية. يرجى تلخيصها بالعربية، مع تضمين: الموضوع، الآيات الكتابية الرئيسية، و3 نقاط أساسية.\n\n',
        es:      'A continuación está la transcripción literal de un sermón en inglés. Por favor, resume en español: tema, referencias bíblicas clave y 3 puntos principales.\n\n',
        pt:      'A seguir está a transcrição literal de um sermão em inglês. Por favor, resuma em português: tema, referências bíblicas principais e 3 pontos principais.\n\n',
        fr:      'Voici la transcription littérale d\'un sermon en anglais. Veuillez résumer en français : thème, références bibliques clés et 3 points principaux.\n\n',
        de:      'Im Folgenden steht die wörtliche Abschrift einer englischen Predigt. Bitte fasse auf Deutsch zusammen: Thema, wichtige Bibelstellen und 3 Hauptpunkte.\n\n',
        it:      'Di seguito è la trascrizione letterale di un sermone in inglese. Per favore riassumi in italiano: tema, riferimenti biblici principali e 3 punti chiave.\n\n',
        nl:      'Hieronder staat de woordelijke transcriptie van een Engelse preek. Geef een samenvatting in het Nederlands: thema, belangrijkste Bijbelverwijzingen en 3 hoofdpunten.\n\n',
        ru:      'Ниже приведена дословная транскрипция проповеди на английском языке. Пожалуйста, составьте краткое изложение на русском: тема, ключевые библейские ссылки и 3 основных тезиса.\n\n',
        pl:      'Poniżej znajduje się dosłowna transkrypcja kazania po angielsku. Proszę streścić po polsku: temat, kluczowe odniesienia biblijne i 3 główne punkty.\n\n',
        tr:      'Aşağıda İngilizce bir vaazın sözcüğü sözcüğüne dökümü yer almaktadır. Lütfen Türkçe özetleyin: konu, temel İncil referansları ve 3 ana nokta.\n\n',
        ta:      'கீழே ஆங்கிலத்தில் ஒரு பிரசங்கத்தின் வரிக்கு வரி படியெடுப்பு உள்ளது. தயவுசெய்து தமிழில் சுருக்கவும்: தலைப்பு, முக்கிய வேத வசனங்கள் மற்றும் 3 முக்கிய கருத்துக்கள்.\n\n',
    };
    const langKey = (typeof targetLang !== 'undefined' ? targetLang : 'en').toLowerCase();
    const intro = prompts[langKey] || 'Please summarise the following sermon. Include: theme, key Bible references, and 3 main points.\n\n';

    // Open a blank tab NOW (synchronously, inside user gesture) to avoid popup blockers.
    // Must NOT use noopener — that returns null and kills the reference we need to navigate.
    // eslint-disable-next-line no-restricted-globals
    const aiTab = window.open('about:blank', '_blank');

    // Show loading state
    const btn = document.getElementById('ai-summary-btn');
    const origLabel = btn ? btn.innerHTML : '';
    if (btn) btn.innerHTML = '<span class="pf-v6-c-spinner pf-m-sm" role="progressbar" aria-label="Loading">'
        + '<span class="pf-v6-c-spinner__clipper"></span><span class="pf-v6-c-spinner__lead-ball"></span>'
        + '<span class="pf-v6-c-spinner__ball"></span></span> Loading…';

    // Fetch ALL translations from server (not just what's in memory) to avoid
    // missing early-sermon content lost to lazy loading
    let allItems = [];
    try {
        const resp = await fetch(
            '/api/translations?offset=0&limit=1000&api_token=' + encodeURIComponent(apiSessionToken)
        );
        if (resp.ok) {
            const data = await resp.json();
            // API returns newest-first; reverse to chronological order
            allItems = (data.translations || []).filter(t => t.corrected).reverse();
        }
    } catch (_) { /* fall through to in-memory fallback */ }

    // Fallback: use what's already in memory (reverse to chronological)
    if (allItems.length === 0) {
        allItems = translations.filter(t => t.corrected).slice().reverse();
    }

    if (btn) btn.innerHTML = origLabel;

    if (allItems.length === 0) {
        showToast('No content to summarise yet.', 'warning');
        return;
    }

    // Use original corrected source text — avoids compounding translation errors
    const segments = allItems.map(t => (t.corrected || '').trim()).filter(Boolean);

    // Build a URL-safe sermon skeleton so ChatGPT always gets a complete picture,
    // even for long sermons. Strategy:
    //   1. Always include first 6 segments (theme / intro)
    //   2. Always include last 6 segments (conclusion / application)
    //   3. Prefer segments that contain a Bible reference
    //   4. Fill remaining budget with evenly-sampled middle segments
    const URL_CHAR_LIMIT = 5500;  // conservative — leaves room for prompt + encoding headroom
    const fullText = segments.join('\n');

    let sermonText;
    if (fullText.length <= URL_CHAR_LIMIT) {
        sermonText = fullText;
    } else {
        const BIBLE_RE = /\b(gen|exo|lev|num|deu|jos|jdg|rut|sam|kgs|chr|ezr|neh|est|job|ps|prov|ecc|song|isa|jer|lam|eze|dan|hos|joel|amos|oba|jon|mic|nah|hab|zep|hag|zec|mal|mat|mar|luk|joh|act|rom|cor|gal|eph|phi|col|the|tim|tit|phm|heb|jam|pet|rev|john|luke|mark|matthew|acts|romans|genesis|psalm|proverbs|revelation|ephesians|philippians|colossians)\s*\d/i;
        const n = segments.length;
        const HEAD = Math.min(6, n);
        const TAIL = Math.min(6, Math.max(0, n - HEAD));
        const head = segments.slice(0, HEAD);
        const tail = segments.slice(n - TAIL);
        const middle = segments.slice(HEAD, n - TAIL);

        // Bible-ref segments from the middle (unique, up to 10)
        const bibleSegs = middle.filter(s => BIBLE_RE.test(s)).slice(0, 10);

        // Budget left after head + tail + bible refs
        const reserved = head.join('\n') + '\n' + bibleSegs.join('\n') + '\n' + tail.join('\n');
        const budget = URL_CHAR_LIMIT - reserved.length - 100;  // 100 for ellipsis markers

        // Evenly sample remaining middle segments to fill budget
        const remaining = middle.filter(s => !BIBLE_RE.test(s));
        const sampled = [];
        if (budget > 0 && remaining.length > 0) {
            const step = Math.max(1, Math.floor(remaining.length / Math.max(1, Math.floor(budget / 120))));
            for (let i = 0; i < remaining.length && sampled.join('\n').length < budget; i += step) {
                sampled.push(remaining[i]);
            }
        }

        // Assemble: head → [bible refs] → [sampled middle] → tail
        const parts = [
            ...head,
            ...(bibleSegs.length ? ['[…]', ...bibleSegs] : []),
            ...(sampled.length  ? ['[…]', ...sampled]   : []),
            ...(tail.length     ? ['[…]', ...tail]       : []),
        ];
        sermonText = parts.join('\n');
    }

    const prompt = intro + sermonText;

    const AI_URLS = {
        chatgpt: 'https://chatgpt.com/?q=',
        gemini:  'https://gemini.google.com/app?q=',
        claude:  'https://claude.ai/new?q=',
    };
    const baseUrl = AI_URLS[service] || AI_URLS.chatgpt;

    // Copy the prompt to the clipboard as a fallback. ChatGPT (and others) may
    // redirect logged-out browsers to a sign-in page instead of auto-loading the
    // `?q=` prompt — that gate is OpenAI's, not ours. Copying first means the user
    // can simply paste the sermon after signing in (or into a temporary chat).
    try {
        if (navigator.clipboard && window.isSecureContext) {
            navigator.clipboard.writeText(prompt).catch(() => {});
        }
    } catch (e) { /* clipboard unavailable — non-fatal */ }

    const target = baseUrl + encodeURIComponent(prompt);
    if (aiTab) {
        aiTab.location.href = target;
    } else {
        window.open(target, '_blank');
    }

    // Let the user know the prompt is on the clipboard in case they hit a login wall.
    showToast(t('aiSummaryCopied', 'Sermon copied — if the AI page asks you to sign in, just paste it.'), 'info', 6000);
}

function clearLocal() {
    if (translations.length === 0) return;
    if (confirm(i18n[displayLanguage]?.confirmClear || 'Clear all translations from display?')) {
        translations = [];
        translationsTotal = 0;
        hasMoreTranslations = false;
        renderedCount = 0;
        // Drop any queued incoming translations and cancel the debounce
        // timer; otherwise they would be re-rendered moments after the
        // user explicitly cleared the view.
        pendingNewTranslations = [];
        if (newTranslationTimer) {
            clearTimeout(newTranslationTimer);
            newTranslationTimer = null;
        }
        const itemCount = document.getElementById('itemCount');
        if (itemCount) itemCount.textContent = '0';
        renderTranslations();
        clearSearch();
    }
}

/* The same text the download would hold, on the clipboard instead. Some
   listeners want to paste a few lines into a message, not keep a file. */
async function copyExport() {
    if (translations.length === 0) {
        showToast(t('toast_exportEmpty', 'No translations to export'), 'warning');
        return;
    }
    const format = document.getElementById('exportFormat').value;
    const content = format === 'json' ? exportAsJSON()
        : format === 'csv' ? exportAsCSV()
        : format === 'srt' ? exportAsSRT()
        : exportAsTXT();
    try {
        await navigator.clipboard.writeText(content);
        showToast(t('toast_copied', 'Copied to clipboard'), 'success');
    } catch (err) {
        console.error('copyExport failed', err);
        showToast(t('toast_copyFailed', 'Failed to copy to clipboard'), 'danger');
    }
}
window.copyExport = copyExport;

function exportData() {
    if (translations.length === 0) {
        showToast(t('toast_exportEmpty', 'No translations to export'), 'warning');
        return;
    }

    const format = document.getElementById('exportFormat').value;
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);

    let content, mimeType, extension;

    switch (format) {
        case 'json':
            content = exportAsJSON();
            mimeType = 'application/json';
            extension = 'json';
            break;
        case 'csv':
            content = exportAsCSV();
            mimeType = 'text/csv';
            extension = 'csv';
            break;
        case 'srt':
            content = exportAsSRT();
            mimeType = 'text/plain';
            extension = 'srt';
            break;
        default:
            content = exportAsTXT();
            mimeType = 'text/plain';
            extension = 'txt';
    }

    // Add UTF-8 BOM for text files to ensure proper encoding on Windows and other devices
    // BOM (Byte Order Mark) \uFEFF helps Windows and Excel correctly identify UTF-8 encoding
    if (format !== 'json') {
        content = '\uFEFF' + content;
    }

    const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    
    // Generate filename based on mode
    const modeLabel = displayMode === 'transcription' ? 'Transcription' : targetLang.toUpperCase();
    a.download = 'EzySpeech_' + modeLabel + '_' + timestamp + '.' + extension;
    
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function exportAsTXT() {
    let content = '═══════════════════════════════════════════════════\n';
    content += '       EzySpeechTranslate Export\n';
    content += '═══════════════════════════════════════════════════\n\n';
    content += 'Generated: ' + new Date().toLocaleString() + '\n';

    if (displayMode === 'transcription') {
        content += 'Mode: Transcription Only\n';
    } else {
        const langSelect = document.getElementById('targetLang');
        const langName = langSelect && langSelect.selectedOptions[0] ? langSelect.selectedOptions[0].text : targetLang;
        content += 'Mode: Translation\n';
        content += 'Target Language: ' + langName + '\n';
    }

    content += 'Total Entries: ' + translations.length + '\n\n';
    content += '═══════════════════════════════════════════════════\n\n';

    translations.forEach((item, index) => {
        content += '[' + String(index + 1).padStart(3, '0') + '] ' + item.timestamp + '\n';
        if (item.is_corrected) {
            content += '      [CORRECTED]\n';
        }

        if (displayMode === 'transcription') {
            content += '\n      Transcription:\n      ' + item.corrected + '\n';
        } else {
            content += '\n      Original:\n      ' + item.corrected + '\n';
            content += '\n      Translation (' + targetLang.toUpperCase() + '):\n      ' + (item.translated || 'Not translated') + '\n';
        }

        content += '\n' + '─'.repeat(55) + '\n\n';
    });

    content += '═══════════════════════════════════════════════════\n';
    content += '              End of Export\n';
    content += '═══════════════════════════════════════════════════\n';

    return content;
}

function exportAsJSON() {
    // Mirror the server-side admin export shape exactly:
    //   { "translations": [ ...raw items... ] }
    // Items are kept as-is (snake_case fields, full payload) so an admin
    // JSON export and a user JSON export of the same history are diffable
    // and importable through the same code path.
    return JSON.stringify({ translations: translations }, null, 2);
}

function exportAsCSV() {
    let csv = '';

    if (displayMode === 'transcription') {
        csv = 'ID,Timestamp,Transcription,Is Corrected\n';
        translations.forEach(item => {
            const row = [
                item.id,
                item.timestamp,
                '"' + (item.corrected || '').replace(/"/g, '""') + '"',
                item.is_corrected ? 'Yes' : 'No'
            ];
            csv += row.join(',') + '\n';
        });
    } else {
        csv = 'ID,Timestamp,Original,Translation,Is Corrected\n';
        translations.forEach(item => {
            const row = [
                item.id,
                item.timestamp,
                '"' + (item.corrected || '').replace(/"/g, '""') + '"',
                '"' + (item.translated || '').replace(/"/g, '""') + '"',
                item.is_corrected ? 'Yes' : 'No'
            ];
            csv += row.join(',') + '\n';
        });
    }

    return csv;
}

function exportAsSRT() {
    let srt = '';

    translations.forEach((item, index) => {
        const sequenceNumber = index + 1;
        const time = item.timestamp;
        const startTime = time + ',000';

        const [hours, minutes, seconds] = time.split(':').map(Number);
        const totalSeconds = hours * 3600 + minutes * 60 + seconds + 3;
        const endHours = Math.floor(totalSeconds / 3600);
        const endMinutes = Math.floor((totalSeconds % 3600) / 60);
        const endSeconds = totalSeconds % 60;
        const endTime = String(endHours).padStart(2, '0') + ':' +
            String(endMinutes).padStart(2, '0') + ':' +
            String(endSeconds).padStart(2, '0') + ',000';

        srt += sequenceNumber + '\n';
        srt += startTime + ' --> ' + endTime + '\n';

        // In transcription mode, use original; in translation mode, use translated
        const text = displayMode === 'transcription' ? item.corrected : (item.translated || item.corrected);
        srt += text + '\n\n';
    });

    return srt;
}

/* ===================================
   Scroll to Top
   =================================== */

const scrollToTopBtn = document.getElementById('scrollToTopBtn');
const mainSection = document.querySelector('.pf-c-page__main-section');

if (mainSection) {
    mainSection.addEventListener('scroll', function () {
        if (mainSection.scrollTop > 300) {
            scrollToTopBtn.classList.add('show');
        } else {
            scrollToTopBtn.classList.remove('show');
        }
    });
}

function scrollToTop() {
    if (mainSection) {
        mainSection.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }
}

/* ===================================
   Event Listeners
   =================================== */

document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        hideAbout();
        hideShortcuts();
        hideWelcome();
        if (typeof hideTour === 'function') hideTour();
        closeMobileMenu();
        return;
    }
    if (e.ctrlKey || e.metaKey || e.altKey) return;

    // "?" should always work, even from <select>/<button> focus
    if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
        // only block when typing actual text
        const typingText = (tag === 'INPUT' && /^(text|search|email|number|password|tel|url)$/i.test(e.target.type || 'text'))
            || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable);
        if (typingText) return;
        e.preventDefault();
        showShortcuts();
        return;
    }

    // Other shortcuts: ignore while interacting with form controls
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toUpperCase() : '';
    const isFormControl = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || (e.target && e.target.isContentEditable);
    if (isFormControl) return;

    if (e.key === '/') {
        // The search is collapsed to its magnifier until someone opens it,
        // so focusing the field alone would put the caret in nothing.
        const bar = document.getElementById('mobileSearchBar');
        const search = document.getElementById('searchInput') || document.getElementById('searchInputMobile');
        if (bar && !bar.classList.contains('pf-m-expanded') && typeof toggleMobileSearch === 'function') {
            e.preventDefault();
            toggleMobileSearch();
            return;
        }
        if (search) { e.preventDefault(); search.focus(); search.select && search.select(); }
        return;
    }
    if (e.key === 'g') {
        if (typeof scrollToTop === 'function') { e.preventDefault(); scrollToTop(); }
        return;
    }
});

/* ===================================
   Socket.IO Events
   =================================== */

function setupSocketEventListeners() {
    // Prevent multiple registrations of the same listeners
    if (socketListenersSetup) {
        console.log('Socket listeners already setup, skipping');
        return;
    }

    if (!socket) {
        console.warn('Socket not initialized, cannot setup listeners');
        return;
    }

    socketListenersSetup = true;
    console.log('Setting up Socket.IO event listeners...');

    socket.on('connect', async () => {
        console.log('Connected to server');
        setConnectionStatus('online');
        // Attempt fast load with cached token; ready event will retry if this returns 401.
        await loadInitialTranslations();
    });

    socket.on('ready', async (data) => {
        // Server sent a fresh API token for this session.
        if (data && data.api_token) {
            const prevToken = apiSessionToken;
            apiSessionToken = data.api_token;
            localStorage.setItem('apiSessionToken', apiSessionToken);
            console.log('Fresh API token received');
            // Only reload if the connect attempt used a stale/rejected token.
            if (!prevToken || prevToken !== apiSessionToken) {
                await loadInitialTranslations();
            }
        }
    });

    // Feature 2: Announcement from admin
    socket.on('announcement', (data) => {
        showAnnouncement(data.text || data.message || '', data.duration ?? 10000, data.type || 'info');
    });

    socket.on('disconnect', () => {
        console.log('Disconnected from server');
        setConnectionStatus('offline');
        // Cancel any pending render so it doesn't fire after disconnect
        // (it would try to use a stale socket and throw).
        if (newTranslationTimer) {
            clearTimeout(newTranslationTimer);
            newTranslationTimer = null;
        }
        showToast(t('toast_offline', 'Connection lost. Reconnecting…'), 'warning', 4000);
    });

    // Reconnection lifecycle (additive)
    if (socket.io && typeof socket.io.on === 'function') {
        socket.io.on('reconnect_attempt', () => {
            setConnectionStatus('waiting');
        });
        socket.io.on('reconnect', () => {
            setConnectionStatus('online');
            showToast(t('toast_reconnected', 'Back online'), 'success', 2500);
        });
        socket.io.on('reconnect_failed', () => {
            setConnectionStatus('offline');
            showToast(t('toast_reconnectFailed', 'Could not reconnect. Please refresh the page.'), 'danger', 8000);
        });
    }

    socket.on('history', async (history) => {
        // Legacy: server still sends history, but we ignore it
        // Instead, we load via HTTP pagination
        console.log('History message received (ignored, using HTTP API)');
    });

    socket.on('realtime_transcription', async (data) => {
        // In transcription mode, show interim transcriptions with typewriter effect
        // In translation mode, skip interim display (only show final results)
        
        const tempId = data.temp_id;
        if (!tempId) return;

        const list = document.getElementById('translationsList');
        if (!list) return;

        // Remove empty state if showing
        const emptyState = list.querySelector('.empty-state');
        if (emptyState) emptyState.remove();

        let tempCard = list.querySelector('[data-temp-id="' + tempId + '"]');
        if (!tempCard) {
            // Create interim card with proper structure: text-source + text-target.
            // Build via DOM nodes (NOT innerHTML) — data.timestamp / data.text
            // come from a websocket peer and must never reach innerHTML as
            // strings, or a malicious admin could inject script.
            // The same shape as a finished row, so nothing shifts when the
            // real one replaces it. Built as nodes, never innerHTML: the
            // timestamp and text come from a websocket peer.
            tempCard = document.createElement('div');
            tempCard.className = 'pf-v6-c-description-list__group translation-card';
            tempCard.setAttribute('data-temp-id', tempId);

            const dt = document.createElement('dt');
            dt.className = 'pf-v6-c-description-list__term';
            const dtText = document.createElement('span');
            dtText.className = 'pf-v6-c-description-list__text';
            const timeSpan = document.createElement('span');
            timeSpan.className = 'card-time';
            timeSpan.textContent = data.timestamp || new Date().toLocaleTimeString();
            dtText.appendChild(timeSpan);
            dt.appendChild(dtText);
            tempCard.appendChild(dt);

            const dd = document.createElement('dd');
            dd.className = 'pf-v6-c-description-list__description';
            const row = document.createElement('div');
            row.className = 'pf-v6-c-description-list__text stream-row';
            dd.appendChild(row);
            tempCard.appendChild(dd);

            const body = document.createElement('div');
            body.className = 'stream-text';
            row.appendChild(body);

            const target = document.createElement('p');
            target.className = 'stream-zh text-target';
            body.appendChild(target);

            const source = document.createElement('span');
            source.className = 'meta text-source';
            source.setAttribute('data-original-text', '');
            if (displayMode === 'transcription' || !showSourceText) source.hidden = true;
            body.appendChild(source);

            const marksDiv = document.createElement('div');
            marksDiv.className = 'card-marks';
            body.appendChild(marksDiv);

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'stream-actions card-actions';
            row.appendChild(actionsDiv);

            list.insertBefore(tempCard, list.firstChild);
            
            // Initialize chunk tracking
            activeChunkTracking[tempId] = {
                text: data.original || data.text || '',
                startTime: Date.now(),
                hasTransitionedToUnderstanding: false,
                statusChangeInterval: null
            };
            
            // Only while there is a translation on the way. Reading English
            // in English, the row used to sit through "Listening" and
            // "Understanding the speaker's context" before showing the words
            // it had all along.
            if (!nothingToTranslate(data)) {
                const textEl = tempCard.querySelector('.text-target');
                if (textEl) {
                    startListeningStateMachine(textEl, tempId);
                }
            }
        }

        // Update transcription text with typewriter effect
        if (nothingToTranslate(data)) {
            // Transcription mode, or the line is already in the language being
            // read: either way the words being said are the line, so they type
            // straight into it. Nothing is waiting on a round trip, so nothing
            // announces that it is.
            const textEl = tempCard.querySelector('.text-target');
            if (textEl) {
                const transcribedText = data.original || data.text || '';
                const currentText = textEl.textContent;
                
                // Animate with typewriter effect
                animateTextChange(textEl, currentText, transcribedText, 300);
                console.log('Updating transcription with typewriter effect:', transcribedText.substring(0, 50));
            }
        } else {
            // Update text-source with interim speech (animated typewriter)
            const sourceEl = tempCard.querySelector('.text-source');
            if (sourceEl) {
                const sourceText = data.original || data.text || '';
                const currentSourceText = sourceEl.textContent;
                sourceEl.setAttribute('data-original-text', escapeHtml(sourceText));
                
                // Animate text-source with typewriter effect
                if (tempCard._sourceAnimTimer) clearTimeout(tempCard._sourceAnimTimer);
                animateTextChange(sourceEl, currentSourceText, sourceText, 300);
                console.log('Updating text-source in interim card:', sourceText.substring(0, 50));
            }

            // Smart chunk detection: check if we should transition from listening to understanding
            const textEl = tempCard.querySelector('.text-target');
            if (textEl && activeChunkTracking[tempId]) {
                const finalText = data.original || data.text || '';
                activeChunkTracking[tempId].text = finalText;
                
                // Check if content is stable enough to transition
                checkAndTransitionToUnderstanding(textEl, tempId, finalText);
                console.log('Chunk state:', { tempId, wordCount: finalText.split(WORD_BOUNDARY_REGEX).length, hasPunctuation: PUNCTUATION_MARKERS.test(finalText) });
            }
        }
    });

    socket.on('new_translation', async (data) => {
        noteSpokenLanguage(data);
        // Check if an interim card exists for this temp_id — update in-place
        if (data.temp_id) {
            const list = document.getElementById('translationsList');
            if (list) {
                const tempCard = list.querySelector('[data-temp-id="' + data.temp_id + '"]');
                if (tempCard) {
                    // Convert interim card to final card in-place
                    const itemId = 'translation-' + data.id;
                    tempCard.removeAttribute('data-temp-id');
                    tempCard.id = itemId;

                    // Get the current interim text before modifying
                    const currentTextEl = tempCard.querySelector('.text-target');
                    const interimText = currentTextEl ? currentTextEl.textContent : (data.corrected || data.original);
                    
                    // Stop listening and intermediate state machines - now transitioning to AI thinking
                    if (currentTextEl) {
                        stopListeningStateMachine(currentTextEl);
                        stopIntermediateStateMachine(currentTextEl);
                        console.log('Stopped listening/intermediate state, starting AI thinking...');
                    }
                    
                    // Clean up chunk tracking for this temp_id
                    if (data.temp_id && activeChunkTracking[data.temp_id]) {
                        delete activeChunkTracking[data.temp_id];
                    }
                    
                    console.log('Upgrading interim card to final:', {
                        tempId: data.temp_id,
                        itemId: itemId,
                        interim: interimText.substring(0, 50),
                        corrected: (data.corrected || data.original).substring(0, 50)
                    });
                    
                    // Determine if we should show source text (for translation mode)
                    const itemSourceLang = data.source_language || data.language || 'en';
                    const normalizedSourceLang = itemSourceLang;
                    const normalizedTargetLang = targetLang;
                    const shouldShowSource = showSourceText
                        && !sameLanguage(normalizedSourceLang, normalizedTargetLang)
                        && displayMode !== 'transcription';

                    console.log('Source language check:', {
                        source: normalizedSourceLang,
                        target: normalizedTargetLang,
                        displayMode: displayMode,
                        showSourceText: showSourceText,
                        shouldShowSource: shouldShowSource
                    });

                    // Handle text-source element
                    let existingSourceDiv = tempCard.querySelector('.text-source');
                    
                    if (shouldShowSource) {
                        if (!existingSourceDiv) {
                            const sourceDiv = document.createElement('span');
                            sourceDiv.className = 'meta text-source';
                            sourceDiv.setAttribute('data-original-text', escapeHtml(data.corrected || data.original));
                            sourceDiv.textContent = data.corrected || data.original;
                            console.log('Adding text-source element');
                            // The source line reads under the translation.
                            currentTextEl.insertAdjacentElement('afterend', sourceDiv);
                        } else {
                            // Update existing source div with correct text
                            existingSourceDiv.hidden = false;
                            existingSourceDiv.textContent = data.corrected || data.original;
                            existingSourceDiv.setAttribute('data-original-text', escapeHtml(data.corrected || data.original));
                            console.log('Updating existing text-source element');
                        }
                    } else if (existingSourceDiv) {
                        existingSourceDiv.hidden = true;
                    }
                    
                    // Start AI thinking status machine (replaces old rotation)
                    // Only in translation mode - in transcription mode, we just show the final text
                    if (currentTextEl && !nothingToTranslate(data)) {
                        // Use same styling as final translation (no 'translating' class to hide the transition)
                        currentTextEl.className = 'text-target';
                        currentTextEl.setAttribute('data-original-text', '');
                        
                        // Start from 'understanding' stage, will auto-progress to translating
                        // Pass source text to determine animation style based on length
                        const sourceText = data.corrected || data.original || '';
                        startAIThinkingMachine(currentTextEl, 'preparing', 30000, sourceText);
                        console.log('Started AI thinking machine (preparingtranslating)');
                    } else if (currentTextEl) {
                        // Transcription mode, or the line is already in the
                        // language being read: the words are the answer.
                        stopAIThinkingMachine(currentTextEl);
                        currentTextEl.className = 'text-target';
                        currentTextEl.style.minHeight = '';
                        currentTextEl.textContent = data.corrected || data.original;
                        console.log('Completed line displayed without translating');
                    }

                    // Add copy + TTS buttons to card-actions.
                    //
                    // The same two buttons the row builder makes, in the same
                    // markup. These were bare <button> elements with the icon
                    // in a plain span: no PatternFly classes at all, so a line
                    // that arrived while an interim row was on screen got the
                    // browser's own grey boxed buttons, sitting beside rows
                    // whose buttons were plain icons.
                    const actions = tempCard.querySelector('.card-actions');
                    if (actions) {
                        actions.innerHTML =
                            '<button class="pf-v6-c-button pf-m-plain copy-btn" type="button"' +
                            ' id="copy-btn-' + data.id + '" data-translation-id="' + data.id + '"' +
                            ' onclick="copyTranslationFromButton(this)" aria-label="Copy this line">' +
                            '<span class="pf-v6-c-button__icon">' + svgIcon('copy') + '</span>' +
                            '</button>' +
                            '<button class="pf-v6-c-button pf-m-plain tts-icon" type="button"' +
                            ' onclick="speakText(this.getAttribute(\'data-text\'))"' +
                            ' data-text="' + escapeHtml(data.translated || data.corrected || data.original || '') + '"' +
                            ' aria-label="Read this line aloud">' +
                            '<span class="pf-v6-c-button__icon">' + svgIcon('volume-up') + '</span>' +
                            '</button>';
                    }

                    // Add to translations array
                    translations.unshift(data);
                    translationsTotal++;
                    renderedCount++;
                    const itemCount = document.getElementById('itemCount');
                    if (itemCount) itemCount.textContent = translationsTotal;

                    // Load Bible verse panel (async fetch from /api/bible/lookup)
                    if (showBibleVerse && bibleFeatureAvailable && data.bible_refs && data.bible_refs.length) {
                        loadBiblePanel(tempCard, data.bible_refs);
                    }

                    // Trigger background translation
                    if (displayMode !== 'transcription') {
                        translateInBackground(data, itemId, currentTextEl);
                    }

                    // Queue auto-TTS playback (translation mode only)
                    if (ttsEnabled && displayMode !== 'transcription' && data.translated) {
                        if (willBecomeVerse(data)) deferSpeech(tempCard);
                        else speakText(data.translated, true);
                    }
                    return;
                }
            }
        }

        // No interim card found — add normally
        pendingNewTranslations.push(data);
        if (!newTranslationTimer) {
            newTranslationTimer = setTimeout(processPendingTranslations, 200);
        }
    });

    socket.on('translation_corrected', async (data) => {
        console.log('Translation corrected:', data.id);
        const index = translations.findIndex(t => t.id === data.id);
        if (index !== -1) {
            translations[index] = data;
            await renderTranslations();
            // Force Bible panel reload: clear any stale cache entry for the
            // corrected item (server may have re-detected different refs)
            // and re-fetch for the freshly rendered card.
            if (showBibleVerse && bibleFeatureAvailable && data.bible_refs && data.bible_refs.length) {
                const cacheKey = JSON.stringify({ refs: data.bible_refs.map(r => r.display).sort(), tgt: bibleTargetTrans });
                _bibleLookupCache.delete(cacheKey);
                const card = document.getElementById('translation-' + data.id);
                if (card) loadBiblePanel(card, data.bible_refs);
            }
        }
    });

    socket.on('order_updated', async (data) => {
        console.log('Order updated from admin:', data.translations.length, 'items');
        translations = data.translations;
        await renderTranslations();
        showSyncIndicator();
    });

    socket.on('history_cleared', () => {
        console.log('History cleared');
        translations = [];
        translationsTotal = 0;
        hasMoreTranslations = false;
        renderedCount = 0;
        pendingNewTranslations = [];
        if (newTranslationTimer) {
            clearTimeout(newTranslationTimer);
            newTranslationTimer = null;
        }
        // Also wipe the client-side cache so a page refresh stays clean.
        try { localStorage.removeItem(_CACHE_KEY); } catch (e) {}
        const itemCount = document.getElementById('itemCount');
        if (itemCount) itemCount.textContent = '0';
        renderTranslations();
        clearSearch();
    });

    socket.on('items_deleted', (data) => {
        console.log('Items deleted:', data.ids);
        const idsToDelete = data.ids || [];
        const before = translations.length;
        translations = translations.filter(item => !idsToDelete.includes(item.id));
        const removed = before - translations.length;
        translationsTotal = Math.max(0, translationsTotal - removed);
        const itemCount = document.getElementById('itemCount');
        if (itemCount) itemCount.textContent = translationsTotal;
        renderTranslations();
    });
}

/* ===================================
   Initialization
   =================================== */

if ('speechSynthesis' in window) {
    loadSettings();
    applyDisplayLanguageLocal();

    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    loadVoices();
    setTimeout(loadVoices, 100);

    console.log('EzySpeechTranslate Ready with Auto Language Detection');
} else {
    console.warn('Speech Synthesis not supported');
}

// Setup socket event listeners when DOM is loaded (only once)
document.addEventListener('DOMContentLoaded', function () {
    ensureSocketConnected();
    initBibleFeature();
});

// ── Feature 2: Announcement Banner ─────────────────────────────────────
let _announcementTimer = null;

const _ANNOUNCEMENT_ICONS = {
    info:    'bullhorn',
    success: 'check-circle',
    warning: 'exclamation-triangle',
    danger:  'exclamation-circle',
};

function showAnnouncement(text, duration, type) {
    if (!text) return;
    const banner  = document.getElementById('announcementBanner');
    const msgEl   = document.getElementById('announcementMessage');
    const iconEl  = document.getElementById('announcementIcon');
    if (!banner || !msgEl) return;

    if (_announcementTimer) {
        clearTimeout(_announcementTimer);
        _announcementTimer = null;
    }

    if (iconEl) iconEl.innerHTML = svgIcon(_ANNOUNCEMENT_ICONS[type] || 'bullhorn');
    msgEl.textContent = text;

    // Map type to banner colour via data attribute
    banner.dataset.type = type || 'info';
    banner.hidden = false;
    banner.classList.remove('announcement-hide');
    banner.classList.add('announcement-show');

    if (duration && duration > 0) {
        _announcementTimer = setTimeout(() => dismissAnnouncement(), duration);
    }
}

function dismissAnnouncement() {
    const banner = document.getElementById('announcementBanner');
    if (!banner) return;
    if (_announcementTimer) { clearTimeout(_announcementTimer); _announcementTimer = null; }
    banner.classList.remove('announcement-show');
    banner.classList.add('announcement-hide');
    setTimeout(() => {
        banner.hidden = true;
        banner.classList.remove('announcement-hide');
    }, 300);
}

console.log('EzySpeechTranslate Client Ready');