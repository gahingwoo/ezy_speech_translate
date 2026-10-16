/* The listener page, part of: Diagnostics, the room, display language and reading settings, the translation cache.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

/* Diagnostics, silent unless asked for with ?debug in the address or
   ezyDebug=1 in local storage. These ran on every interim update, two or
   three to a word, and a console holds on to everything it is given for as
   long as the page stays open, which in a service is hours. */
const trace = (function () {
    try {
        if (/[?&]debug\b/.test(location.search) || localStorage.getItem('ezyDebug') === '1') {
            return console.log.bind(console);
        }
    } catch (e) { /* storage blocked: stay quiet */ }
    return function () {};
})();

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
trace('Joining room:', window.CURRENT_ROOM_ID);

// Generate or retrieve persistent client ID (stored in localStorage)
function getOrCreateClientId() {
    let clientId = localStorage.getItem('_client_id');
    if (!clientId) {
        // Generate a new UUID-like client ID - stored for persistence across sessions
        clientId = 'user_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now();
        localStorage.setItem('_client_id', clientId);
        trace('Generated new persistent client ID:', clientId);
    } else {
        trace('Using persistent client ID:', clientId);
    }
    return clientId;
}

function initSocket() {
    if (socket && socket.connected) {
        trace('Socket already connected');
        return;
    }

    trace('Initializing Socket.IO connection...');
    
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
    // One socket for the life of the page. This used to build a new one
    // whenever the current one was not connected yet, and it is called twice
    // in the same tick at load, before either can connect: socket.io opens a
    // second connection for a second io() on the same namespace, so a listener
    // held two, every event arrived twice, and each line was translated twice.
    if (!socket) initSocket();
    else if (!socket.connected) socket.connect();
}

// TTS Settings
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let availableVoices = [];
let selectedVoice = null;

// TTS Queue Management - prevents parallel playback and maintains order
let ttsQueue = [];          // Queue of {text, isAutoPlay} waiting to be spoken
let isTTSPlaying = false;   // Currently playing TTS
let currentUtterance = null;     // Current utterance for System TTS
let lastTTSClickText = '';  // Track last clicked TTS text for double-tap stop
let lastTTSClickTime = 0;   // Track when user last clicked TTS button
const TTS_DOUBLE_TAP_THRESHOLD = 500;  // 500ms window for double-tap detection

// Use shared translations: js/i18n/core.js loads the languages this page needs
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
    'ta-IN': 'ta',
    'tl': 'tl',
    'fil': 'tl',
    'fil-PH': 'tl',
    'mi': 'mi',
    'mi-NZ': 'mi',
    'sm': 'sm',
    'sm-WS': 'sm',
    'to': 'to',
    'to-TO': 'to'
};

/* Moved here from the settings part: the line below runs it as the page
   loads, before that part has loaded. */
/* ===================================
   Auto Language Detection
   =================================== */

function detectUserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    trace('Browser language detected:', browserLang);

    // Try exact match first
    if (BROWSER_LANG_MAP[browserLang]) {
        trace('Exact match found:', BROWSER_LANG_MAP[browserLang]);
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
        trace('Base language match found:', BROWSER_LANG_MAP[baseLang]);
        return BROWSER_LANG_MAP[baseLang];
    }

    // Check all browser languages
    if (navigator.languages && navigator.languages.length > 0) {
        for (let lang of navigator.languages) {
            if (BROWSER_LANG_MAP[lang]) {
                trace('Alternative language match found:', BROWSER_LANG_MAP[lang]);
                return BROWSER_LANG_MAP[lang];
            }
            const base = lang.split('-')[0];
            if (BROWSER_LANG_MAP[base]) {
                trace('Alternative base language match found:', BROWSER_LANG_MAP[base]);
                return BROWSER_LANG_MAP[base];
            }
        }
    }

    // Default to Cantonese
    trace('No match found, using default: yue');
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
// True when no one chose it: it was taken from the phone's language this visit.
let targetLangDetected = false;
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
            trace('Restored ' + _cached.length + ' translations from local cache');
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
let isRenderingMore = false;         // Prevent duplicate render operations

// Translation queue - prevents rate limit when admin bulk imports
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

// PatternFly icons for the markup this file builds as strings. The paths are
// in the page once, as <symbol>s in the sprite render_user.py emits; this only
// points at them. Never put an emoji here — the page is PatternFly 6.
function svgIcon(name, cls) {
    return '<svg class="pf-v6-svg' + (cls ? ' ' + cls : '') + '" aria-hidden="true"'
        + ' role="img" width="1em" height="1em" fill="currentColor">'
        + '<use href="#i-' + name + '"></use></svg>';
}
const DOT_PULSE = ['.', '..', '...', '..'];  // Dot animation
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
        trace('Updating ' + interimCards.length + ' interim cards: showSourceText=' + showSourceText);
        
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
    
    trace('Updating source text toggle UI: showSourceText=' + showSourceText);
    
    if (btn && textSpan) {
        // Update text based on current state
        // If showing source (true) → button says "Hide Source"
        // If hiding source (false) → button says "Show Source"
        textSpan.textContent = showSourceText ? 'Hide Source' : 'Show Source';
        trace('Button text set to: ' + textSpan.textContent);
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
