const socket = io();

// TTS Settings
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let selectedVoice = null;
let availableVoices = [];

// Translation Data
let translations = [];
let targetLang = 'yue';
let displayMode = 'translation'; // 'translation' or 'transcription'
let sourceLanguage = null; // ASR source language from admin

// Search State
let searchQuery = '';
let visibleTranslationIds = new Set();

// Display Settings
let fontSize = 18;

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
    'zh-cn': 'zh-CN',
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
const BROWSER_LANG_MAP = {
    'zh-HK': 'yue',
    'zh-MO': 'yue',
    'yue': 'yue',
    'zh-CN': 'zh-cn',
    'zh-SG': 'zh-cn',
    'zh': 'zh-cn',
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

/* ===================================
   Auto Language Detection
   =================================== */

function detectUserLanguage() {
    const browserLang = navigator.language || navigator.userLanguage;
    console.log('🌍 Browser language detected:', browserLang);

    // Try exact match first
    if (BROWSER_LANG_MAP[browserLang]) {
        console.log('✅ Exact match found:', BROWSER_LANG_MAP[browserLang]);
        return BROWSER_LANG_MAP[browserLang];
    }

    // Try base language (e.g., 'zh' from 'zh-Hans')
    const baseLang = browserLang.split('-')[0];
    if (BROWSER_LANG_MAP[baseLang]) {
        console.log('✅ Base language match found:', BROWSER_LANG_MAP[baseLang]);
        return BROWSER_LANG_MAP[baseLang];
    }

    // Check all browser languages
    if (navigator.languages && navigator.languages.length > 0) {
        for (let lang of navigator.languages) {
            if (BROWSER_LANG_MAP[lang]) {
                console.log('✅ Alternative language match found:', BROWSER_LANG_MAP[lang]);
                return BROWSER_LANG_MAP[lang];
            }
            const base = lang.split('-')[0];
            if (BROWSER_LANG_MAP[base]) {
                console.log('✅ Alternative base language match found:', BROWSER_LANG_MAP[base]);
                return BROWSER_LANG_MAP[base];
            }
        }
    }

    // Default to Cantonese
    console.log('ℹ️ No match found, using default: yue');
    return 'yue';
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

    // Load display mode
    if (savedMode) {
        displayMode = savedMode;
        document.getElementById('displayMode').value = savedMode;
        updateDisplayMode();
    }

    // Auto-detect language if not saved
    if (savedLang) {
        targetLang = savedLang;
        console.log('✅ Using saved language:', savedLang);
    } else {
        targetLang = detectUserLanguage();
        localStorage.setItem('targetLang', targetLang);
        console.log('🔍 Auto-detected and saved language:', targetLang);
    }

    document.getElementById('targetLang').value = targetLang;

    if (savedRate) {
        ttsRate = parseFloat(savedRate);
        document.getElementById('rateSlider').value = ttsRate;
        document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    }

    if (savedVolume) {
        ttsVolume = parseFloat(savedVolume);
        document.getElementById('volumeSlider').value = ttsVolume;
        document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    }

    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeUI(savedTheme);
    }

    if (savedFontSize) {
        fontSize = parseInt(savedFontSize);
        document.getElementById('fontSizeSlider').value = fontSize;
        document.getElementById('fontSizeValue').textContent = fontSize + 'px';
        applyFontSize();
    }

    return savedVoice;
}

/* ===================================
   Voice Management
   =================================== */

function loadVoices() {
    availableVoices = speechSynthesis.getVoices();

    if (availableVoices.length === 0) {
        return;
    }

    const voiceSelect = document.getElementById('voiceSelect');
    const savedVoice = localStorage.getItem('selectedVoice');
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;

    // Filter voices based on target language
    const matchingVoices = availableVoices.filter(function(voice) {
        const voiceLang = voice.lang.toLowerCase();
        const targetLangLower = ttsLang.toLowerCase();

        // Special handling for Chinese variants
        if (targetLang === 'yue') {
            return voiceLang === 'zh-hk' ||
                voiceLang.includes('yue') ||
                (voice.name.includes('粵語') || voice.name.includes('粤语'));
        } else if (targetLang === 'zh-cn') {
            return voiceLang === 'zh-cn' ||
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
    autoOption.textContent = '🤖 Auto (System Default)';
    voiceSelect.appendChild(autoOption);

    // Group voices by language
    const grouped = {};
    voicesToShow.forEach(function(voice) {
        const lang = voice.lang;
        if (!grouped[lang]) grouped[lang] = [];
        grouped[lang].push(voice);
    });

    // Add voice options
    Object.keys(grouped).sort().forEach(function(lang) {
        grouped[lang].forEach(function(voice) {
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
        const voiceExists = voicesToShow.find(function(v) {
            return v.name === savedVoice;
        });
        if (voiceExists) {
            voiceSelect.value = savedVoice;
            selectedVoice = voiceExists;
        } else {
            selectedVoice = null;
        }
    }

    console.log('✅ Loaded ' + availableVoices.length + ' voices, showing ' + voicesToShow.length + ' for ' + targetLang);
}

function changeVoice() {
    const voiceSelect = document.getElementById('voiceSelect');
    const voiceName = voiceSelect.value;

    if (voiceName) {
        selectedVoice = availableVoices.find(function(v) {
            return v.name === voiceName;
        });
        localStorage.setItem('selectedVoice', voiceName);
        console.log('Selected voice: ' + voiceName);
    } else {
        selectedVoice = null;
        localStorage.removeItem('selectedVoice');
        console.log('Using auto voice selection');
    }
}

function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    localStorage.setItem('targetLang', targetLang);

    loadVoices();

    // Clear cached translations
    translations.forEach(function(item) {
        item.translated = null;
        item.currentLang = null;
    });
    renderTranslations();
}

function changeDisplayMode() {
    const select = document.getElementById('displayMode');
    displayMode = select.value;
    localStorage.setItem('displayMode', displayMode);

    console.log('🔄 Display mode changed to:', displayMode);
    updateDisplayMode();
    renderTranslations();
}

function updateDisplayMode() {
    const languageGroup = document.getElementById('languageSelectGroup');
    const ttsSection = document.querySelector('.sidebar-section:has(#toggleTTS)');
    const mainTitleText = document.getElementById('mainTitleText');
    const emptyStateText = document.getElementById('emptyStateText');
    const emptyStateDesc = document.getElementById('emptyStateDesc');

    if (displayMode === 'transcription') {
        // Hide language selector and TTS in transcription mode
        if (languageGroup) languageGroup.style.display = 'none';
        if (ttsSection) ttsSection.style.display = 'none';

        // Update title
        if (mainTitleText) mainTitleText.textContent = 'Live Transcriptions';

        // Update empty state
        if (emptyStateText) emptyStateText.textContent = 'Waiting for transcriptions...';
        if (emptyStateDesc) emptyStateDesc.textContent = 'Transcriptions will appear here in real-time';

        console.log('📝 Transcription mode enabled');
    } else {
        // Show language selector and TTS in translation mode
        if (languageGroup) languageGroup.style.display = 'block';
        if (ttsSection) ttsSection.style.display = 'block';

        // Update title
        if (mainTitleText) mainTitleText.textContent = 'Live Translations';

        // Update empty state
        if (emptyStateText) emptyStateText.textContent = 'Waiting for translations...';
        if (emptyStateDesc) emptyStateDesc.textContent = 'Translations will appear here in real-time';

        console.log('🌐 Translation mode enabled');
    }
}

/* ===================================
   UI Controls
   =================================== */

function toggleMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');
    const isOpen = sidebar.classList.contains('mobile-open');

    if (isOpen) {
        sidebar.classList.remove('mobile-open');
        overlay.classList.remove('active');
        toggle.classList.remove('active');
    } else {
        sidebar.classList.add('mobile-open');
        overlay.classList.add('active');
        toggle.classList.add('active');
    }
}

function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');

    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
    toggle.classList.remove('active');
}

function toggleMobileSearch() {
    const searchBar = document.getElementById('mobileSearchBar');
    const toggle = document.getElementById('mobileSearchToggle');
    const isOpen = searchBar.classList.contains('active');

    if (isOpen) {
        searchBar.classList.remove('active');
        toggle.classList.remove('active');
    } else {
        searchBar.classList.add('active');
        toggle.classList.add('active');
        const searchInput = document.getElementById('searchInputMobile');
        if (searchInput) {
            setTimeout(() => searchInput.focus(), 100);
        }
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
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeUI(newTheme);
}

function updateThemeUI(theme) {
    const icon = document.getElementById('themeIcon');
    const text = document.getElementById('themeText');
    if (theme === 'dark') {
        if (icon) icon.textContent = '☀️';
        if (text) text.textContent = 'Light Mode';
    } else {
        if (icon) icon.textContent = '🌙';
        if (text) text.textContent = 'Dark Mode';
    }
}

function resetSettings() {
    if (!confirm('Reset all settings to default?\n\nThis will:\n• Reset display mode to Translation\n• Reset language to auto-detected\n• Reset theme to Light\n• Reset font size to 18px\n• Reset TTS settings\n• Keep your translations')) {
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

    console.log('🔄 Settings reset to defaults');

    // Reload page to apply defaults
    location.reload();
}

function showSyncIndicator() {
    const indicator = document.getElementById('syncIndicator');
    indicator.classList.add('show');
    setTimeout(function() {
        indicator.classList.remove('show');
    }, 3000);
}

function updateFontSize() {
    fontSize = parseInt(document.getElementById('fontSizeSlider').value);
    document.getElementById('fontSizeValue').textContent = fontSize + 'px';
    localStorage.setItem('fontSize', fontSize);
    applyFontSize();
}

function applyFontSize() {
    const style = document.getElementById('dynamicFontStyle');
    if (style) {
        style.textContent = `.text-target { font-size: ${fontSize}px !important; }`;
    } else {
        const newStyle = document.createElement('style');
        newStyle.id = 'dynamicFontStyle';
        newStyle.textContent = `.text-target { font-size: ${fontSize}px !important; }`;
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

    translations.forEach(function(item) {
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
    if (!query) {
        const sourceDiv = card.querySelector('.text-source');
        const targetDiv = card.querySelector('.text-target');

        [sourceDiv, targetDiv].forEach(function(div) {
            if (!div) return;
            const originalText = div.getAttribute('data-original-text');
            if (originalText) {
                div.textContent = originalText;
                div.removeAttribute('data-original-text');
            }
        });
        return;
    }

    const sourceDiv = card.querySelector('.text-source');
    const targetDiv = card.querySelector('.text-target');

    [sourceDiv, targetDiv].forEach(function(div) {
        if (!div) return;

        const originalText = div.getAttribute('data-original-text') || div.textContent;
        if (!div.getAttribute('data-original-text')) {
            div.setAttribute('data-original-text', originalText);
        }

        const regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
        const highlightedText = originalText.replace(regex, '<mark class="search-highlight">$1</mark>');
        div.innerHTML = highlightedText;
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
        let translationLang = targetLang;
        let translated = text;

        if (targetLang === 'yue') {
            try {
                const yueUrl = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=yue&dt=t&q=' + encodeURIComponent(text);
                const yueResponse = await fetch(yueUrl);
                const yueData = await yueResponse.json();
                if (yueData && yueData[0] && yueData[0][0] && yueData[0][0][0]) {
                    translated = yueData[0][0][0];
                }
            } catch (err) {
                console.log('Cantonese translation fallback to zh-TW');
                translationLang = 'zh-TW';
            }
        }

        if (translated === text) {
            const url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=' + translationLang + '&dt=t&q=' + encodeURIComponent(text);
            const response = await fetch(url);
            const data = await response.json();
            if (data && data[0] && data[0][0] && data[0][0][0]) {
                translated = data[0][0][0];
            }
        }

        sessionStorage.setItem(cacheKey, translated);
        return translated;
    } catch (error) {
        console.error('Translation error:', error);
        return text + ' (translation failed)';
    }
}

/* ===================================
   Text-to-Speech Functions
   =================================== */

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        alert('Your browser does not support text-to-speech');
        return;
    }

    speechSynthesis.cancel();

    // Validate and sanitize text before speaking
    const validation = validateText(text, 5000);
    if (!validation.valid) {
        console.error('Invalid text for TTS:', validation.error);
        return;
    }

    const cleanText = validation.text.replace(/\s*\([^)]*\)\s*/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
    utterance.lang = ttsLang;
    utterance.rate = ttsRate;
    utterance.volume = ttsVolume;

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log('Using selected voice: ' + selectedVoice.name);
    } else {
        const voices = speechSynthesis.getVoices();
        let autoVoice = voices.find(function(v) {
            return v.lang === ttsLang;
        });
        if (!autoVoice) {
            const baseLang = ttsLang.split('-')[0];
            autoVoice = voices.find(function(v) {
                return v.lang.startsWith(baseLang + '-');
            });
        }
        if (autoVoice) {
            utterance.voice = autoVoice;
            console.log('Using auto voice: ' + autoVoice.name);
        }
    }

    utterance.onerror = function(e) {
        console.error('TTS error:', e);
    };

    speechSynthesis.speak(utterance);
}

function toggleTTS() {
    ttsEnabled = !ttsEnabled;
    const btn = document.getElementById('toggleTTS');
    const icon = btn.querySelector('span:first-child');
    const text = btn.querySelector('span:last-child');

    if (ttsEnabled) {
        btn.classList.add('active');
        icon.textContent = '🔇';
        text.textContent = 'Disable TTS';
    } else {
        btn.classList.remove('active');
        icon.textContent = '🔊';
        text.textContent = 'Enable TTS';
        speechSynthesis.cancel();
    }
}

function updateRate() {
    ttsRate = parseFloat(document.getElementById('rateSlider').value);
    document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    localStorage.setItem('ttsRate', ttsRate);
}

function updateVolume() {
    ttsVolume = parseFloat(document.getElementById('volumeSlider').value);
    document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    localStorage.setItem('ttsVolume', ttsVolume);
}

/* ===================================
   Copy Functionality
   =================================== */

function copyTranslation(id) {
    const idStr = String(id);
    const item = translations.find(function(t) {
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
        navigator.clipboard.writeText(textToCopy).then(function() {
            console.log('Copied successfully with clipboard API');
            showCopyFeedback(id);
        }).catch(function(err) {
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
            alert('Failed to copy to clipboard');
        }
    } catch (err) {
        console.error('Fallback copy error:', err);
        alert('Failed to copy to clipboard');
    }
}

function showCopyFeedback(id) {
    const btn = document.getElementById('copy-btn-' + id);
    if (btn) {
        const span = btn.querySelector('span');
        const originalText = span.textContent;

        span.textContent = '✓';
        btn.classList.add('copied');

        setTimeout(function() {
            span.textContent = originalText;
            btn.classList.remove('copied');
        }, 2000);
    }
}

/* ===================================
   Rendering Functions
   =================================== */

async function renderTranslations() {
    const list = document.getElementById('translationsList');
    const itemCount = document.getElementById('itemCount');
    if (itemCount) itemCount.textContent = translations.length;

    if (translations.length === 0) {
        const emptyText = displayMode === 'transcription' ? 'Waiting for transcriptions...' : 'Waiting for translations...';
        const emptyDesc = displayMode === 'transcription' ?
            'Transcriptions will appear here in real-time' :
            'Translations will appear here in real-time';

        list.innerHTML = '\
            <div class="empty-state">\
                <div class="empty-icon">💬</div>\
                <div>' + emptyText + '</div>\
                <small style="display: block; margin-top: 0.5rem; opacity: 0.7;">\
                    ' + emptyDesc + '\
                </small>\
            </div>\
        ';
        return;
    }

    const reversed = [...translations].reverse();
    const items = await Promise.all(
        reversed.map(item => createTranslationHTML(item))
    );

    list.innerHTML = items.join('');

    if (searchQuery) {
        performSearch();
    }
}

async function addTranslation(data) {
    const list = document.getElementById('translationsList');
    const emptyState = list.querySelector('.empty-state');

    if (emptyState) {
        list.innerHTML = '';
    }

    const html = await createTranslationHTML(data);
    list.innerHTML = html + list.innerHTML;
    document.getElementById('itemCount').textContent = translations.length;

    if (searchQuery) {
        performSearch();
    }
}

async function createTranslationHTML(item) {
    const itemId = 'translation-' + item.id;

    // Get source language from item
    const itemSourceLang = item.source_language || item.language || 'en';

    // In transcription mode, only show original text
    if (displayMode === 'transcription') {
        const correctedBadge = item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : '';
        const correctedClass = item.is_corrected ? 'corrected' : '';

        return '\
            <div class="translation-card ' + correctedClass + '" id="' + itemId + '">\
                <div class="card-header">\
                    <span class="card-time">' + item.timestamp + '</span>\
                    <div class="card-actions">\
                        ' + correctedBadge + '\
                        <button class="copy-btn" id="copy-btn-' + item.id + '" data-translation-id="' + item.id + '" onclick="copyTranslationFromButton(this)" title="Copy transcription">\
                            <span>📋</span>\
                        </button>\
                    </div>\
                </div>\
                <div class="text-target" data-original-text="' + escapeHtml(item.corrected) + '">' + escapeHtml(item.corrected) + '</div>\
            </div>\
        ';
    }

    // Translation mode logic
    // Map source language codes
    const langMap = {
        'en': 'en',
        'zh': 'zh-cn',
        'yue': 'yue',
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
        'ta': 'ta'
    };

    const normalizedSourceLang = langMap[itemSourceLang] || itemSourceLang;
    const normalizedTargetLang = targetLang;

    // If source language matches target language, don't show source text
    const shouldHideSource = normalizedSourceLang === normalizedTargetLang;

    if (!item.translated || item.currentLang !== targetLang) {
        item.currentLang = targetLang;

        setTimeout(async () => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.innerHTML = '<span class="loading">Translating...</span>';
                }
            }
        }, 0);

        item.translated = await translateText(item.corrected, targetLang);

        setTimeout(() => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.textContent = item.translated;
                    targetDiv.setAttribute('data-original-text', item.translated);
                }
            }
        }, 0);
    }

    const correctedBadge = item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : '';
    const correctedClass = item.is_corrected ? 'corrected' : '';
    const translatedText = item.translated || 'Translating...';

    // Show source text only if languages don't match
    const sourceHtml = shouldHideSource ? '' :
        '<div class="text-source" data-original-text="' + escapeHtml(item.corrected) + '">' + escapeHtml(item.corrected) + '</div>';

    return '\
        <div class="translation-card ' + correctedClass + '" id="' + itemId + '">\
            <div class="card-header">\
                <span class="card-time">' + item.timestamp + '</span>\
                <div class="card-actions">\
                    ' + correctedBadge + '\
                    <button class="copy-btn" id="copy-btn-' + item.id + '" data-translation-id="' + item.id + '" onclick="copyTranslationFromButton(this)" title="Copy translation">\
                        <span>📋</span>\
                    </button>\
                    <button class="tts-icon" onclick="speakText(this.getAttribute(\'data-text\'))" data-text="' + escapeHtml(translatedText) + '" title="Speak translation">🔊</button>\
                </div>\
            </div>\
            ' + sourceHtml + '\
            <div class="text-target" data-original-text="' + escapeHtml(translatedText) + '">' + escapeHtml(translatedText) + '</div>\
        </div>\
    ';
}

function copyTranslationFromButton(button) {
    const id = button.getAttribute('data-translation-id');
    console.log('Copy button clicked with ID:', id);
    copyTranslation(id);
}

// Keep escapeHtml for backward compatibility, but use sanitizeInput for consistency
function escapeHtml(text) {
    return sanitizeInput(text);
}

/* ===================================
   Data Management
   =================================== */

function clearLocal() {
    if (translations.length === 0) return;
    if (confirm('Clear all translations from display?\n\nNote: This only clears your local view.')) {
        translations = [];
        renderTranslations();
        clearSearch();
    }
}

function exportData() {
    if (translations.length === 0) {
        alert('No translations to export');
        return;
    }

    const format = document.getElementById('exportFormat').value;
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);

    let content, mimeType, extension;

    switch(format) {
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

    const blob = new Blob([content], { type: mimeType + ';charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'EzySpeech_' + targetLang + '_' + timestamp + '.' + extension;
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
        const langName = document.getElementById('targetLang').selectedOptions[0].text;
        content += 'Mode: Translation\n';
        content += 'Target Language: ' + langName + '\n';
    }

    content += 'Total Entries: ' + translations.length + '\n\n';
    content += '═══════════════════════════════════════════════════\n\n';

    translations.forEach((item, index) => {
        content += '[' + String(index + 1).padStart(3, '0') + '] ' + item.timestamp + '\n';
        if (item.is_corrected) {
            content += '      [✓ CORRECTED]\n';
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
    const exportData = {
        metadata: {
            generated: new Date().toISOString(),
            mode: displayMode,
            targetLanguage: displayMode === 'translation' ? targetLang : null,
            totalEntries: translations.length
        },
        translations: translations.map(item => ({
            id: item.id,
            timestamp: item.timestamp,
            original: item.corrected,
            translated: displayMode === 'translation' ? (item.translated || null) : null,
            isCorrected: item.is_corrected
        }))
    };

    return JSON.stringify(exportData, null, 2);
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
    mainSection.addEventListener('scroll', function() {
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

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
    }
});

/* ===================================
   Socket.IO Events
   =================================== */

socket.on('connect', () => {
    console.log('Connected to server');
    const badge = document.getElementById('statusBadge');
    badge.className = 'connection-badge online';
    badge.querySelector('span:last-child').textContent = 'Online';
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    const badge = document.getElementById('statusBadge');
    badge.className = 'connection-badge offline';
    badge.querySelector('span:last-child').textContent = 'Offline';
});

socket.on('history', async (history) => {
    console.log('Received history:', history.length, 'items');
    translations = history;
    await renderTranslations();
});

socket.on('new_translation', async (data) => {
    console.log('Received new translation:', data);
    translations.push(data);
    await addTranslation(data);

    if (ttsEnabled && data.translated) {
        speakText(data.translated);
    }
});

socket.on('translation_corrected', async (data) => {
    console.log('Translation corrected:', data.id);
    const index = translations.findIndex(t => t.id === data.id);
    if (index !== -1) {
        translations[index] = data;
        await renderTranslations();
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
    renderTranslations();
    clearSearch();
});

/* ===================================
   Initialization
   =================================== */

if ('speechSynthesis' in window) {
    loadSettings();

    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    loadVoices();
    setTimeout(loadVoices, 100);

    console.log('✅ EzySpeechTranslate Ready with Auto Language Detection');
} else {
    console.warn('⚠️ Speech Synthesis not supported');
}

console.log('✅ EzySpeechTranslate Client Ready');