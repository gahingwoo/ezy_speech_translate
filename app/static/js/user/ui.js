/* The listener page, part of: Settings, voices, view modes, toasts, the connection label, dialogs, the tour, search.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

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
    'ta': 'ta-IN',
    'tl': 'fil-PH',
    'mi': 'mi-NZ',
    'sm': 'sm-WS',
    'to': 'to-TO'
};

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
    const savedTTSEnabled = localStorage.getItem('ttsEnabled');

    // Load TTS enabled state
    if (savedTTSEnabled !== null) {
        ttsEnabled = savedTTSEnabled === 'true';
        trace('Loaded TTS enabled state:', ttsEnabled);
    }
    // Unconditionally: the masthead icon says which state it is in, and with
    // nothing stored yet it would otherwise keep the speaking icon while
    // silent.
    const ttsBox = document.getElementById('toggleTTS');
    if (ttsBox) ttsBox.checked = ttsEnabled;
    syncTTSQuickToggle();

    // Load display language (be tolerant of variants like 'en-US')
    if (savedDisplayLanguage) {
        if (i18n[savedDisplayLanguage]) {
            displayLanguage = savedDisplayLanguage;
            trace('Using saved display language:', savedDisplayLanguage);
        } else {
            const base = savedDisplayLanguage.split('-')[0];
            if (i18n[base]) {
                displayLanguage = base;
                trace('Using base of saved display language:', base);
            } else {
                displayLanguage = detectDisplayLanguageLocal();
                trace('Saved display language not supported, auto-detected:', displayLanguage);
            }
        }
    } else {
        displayLanguage = detectDisplayLanguageLocal();
        localStorage.setItem('displayLanguage', displayLanguage);
        trace('Auto-detected and saved display language:', displayLanguage);
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
        trace('Using saved language:', savedLang);
    } else {
        targetLang = detectUserLanguage();
        targetLangDetected = true;
        localStorage.setItem('targetLang', targetLang);
        trace('Auto-detected and saved language:', targetLang);
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
        // paintTheme, not the attribute on its own: PatternFly switches its
        // tokens on a class, and setting only data-theme left the page light
        // after every reload while the toggle believed it was dark. The other
        // three pages call this; this one had its own copy of half of it.
        paintTheme(savedTheme);
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
    loadSystemVoices();
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

    trace('Loaded ' + availableVoices.length + ' system voices, showing ' + voicesToShow.length + ' for ' + targetLang);
}

function changeVoice() {
    const voiceSelect = document.getElementById('voiceSelect');
    const voiceName = voiceSelect.value;

    // Clear TTS queue when changing voice to prevent wrong voice playback
    clearTTSQueue();

    if (voiceName) {
        selectedVoice = availableVoices.find(function (v) {
            return v.name === voiceName;
        });
        localStorage.setItem('selectedVoice', voiceName);
    } else {
        selectedVoice = null;
        localStorage.removeItem('selectedVoice');
    }
}

function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    localStorage.setItem('targetLang', targetLang);
    announceReadingLanguage();

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
    announceReadingLanguage();

    trace('Display mode changed to:', displayMode);
    
    // Clear any pending interim cards when switching modes
    const list = document.getElementById('translationsList');
    if (list) {
        const interimCards = list.querySelectorAll('[data-temp-id]');
        trace('Removing ' + interimCards.length + ' interim cards');
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
    trace(transcribing ? 'Showing what was said' : 'Showing translations');
}

/* ===================================
   UI Controls
   =================================== */

/* The drawer is sidebar.js's, not this file's. A copy of it lived here, and
   because this script loads after that one it shadowed the original: the panel
   opened, but through the older version, so the backdrop was switched on rather
   than faded and Escape did nothing. sidebar.js puts toggleMobileMenu,
   closeMobileMenu, setSidebarOpen, isSidebarOpen and sidebarIsWide on window,
   and every call in this file goes to those. */

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
    // The masthead button names what it does, so it changes with the theme.
    const quick = document.getElementById('themeToggle');
    if (quick) {
        const label = theme === 'dark' ? t('lightMode', 'Light Mode') : t('darkMode', 'Dark Mode');
        quick.setAttribute('aria-label', label);
        quick.setAttribute('title', label);
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

    trace('Settings reset to defaults');

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
        trace('[toast]', type, message);
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
    close.onclick = function () { leave(); };
    action.appendChild(close);

    alert.append(icon, title, action);
    item.appendChild(alert);
    container.appendChild(item);

    // PatternFly's toast group animates an item in from off-stage, and out to
    // it again. pf-m-offstage-right and pf-m-incoming are both states an item
    // starts in, not ones it moves to. This added pf-m-incoming as the item
    // arrived, which holds the first toast in the group at no height and no
    // opacity, so a message on its own was never seen at all; and the
    // off-stage class came off before the item had been laid out with it, so
    // there was nothing to animate from. Now it is laid out off-stage, then
    // released, and it leaves the same way whether it times out or is closed.
    item.classList.add('pf-m-offstage-right');
    void item.offsetHeight;
    item.classList.remove('pf-m-offstage-right');
    let gone = false;
    function leave() {
        if (gone) return;
        gone = true;
        item.classList.add('pf-m-outgoing');
        setTimeout(function () { item.remove(); }, 300);
    }
    setTimeout(leave, duration);
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
    // PatternFly's status variants, as the console's label uses: the two
    // mastheads showed the same state in two different greens. This function
    // rewrites className wholesale, so they are set here rather than in the
    // template, where they would be wiped on the first status change.
    const mod = { online: 'pf-m-success', offline: 'pf-m-danger', waiting: 'pf-m-warning' };
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
function showWelcome() {
    // The wizard's choice stands in for the settings' one, so it starts at
    // whatever that is now. It used to start at the first in its list,
    // English, while the page was already reading the phone's language.
    const sel = document.getElementById('setupTargetLanguage');
    if (sel) sel.value = targetLang;
    const note = document.getElementById('setupDetected');
    if (note && sel && targetLangDetected) {
        const name = sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].text : targetLang;
        note.textContent = t('setupDetected', 'Chosen from your phone\'s language: {lang}. If it is not right, choose another here.')
            .replace('{lang}', name);
        note.hidden = false;
    }
    __openModal('welcomeModal');
}
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
        trace('Page visible - resuming translations');
        // Optionally sync when page becomes visible again
    } else {
        trace('Page hidden - pausing translation loads');
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
