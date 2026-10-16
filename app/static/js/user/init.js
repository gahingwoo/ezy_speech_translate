/* The listener page, part of: Start-up, and keeping the screen awake.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

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

    if ('speechSynthesis' in window) {
        loadVoices();
        speechSynthesis.addEventListener('voiceschanged', loadVoices);
        // Some browsers fill the list a moment later without the event.
        setTimeout(loadVoices, 100);
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

    trace('user.js initialized');
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
