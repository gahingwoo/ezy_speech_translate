// ===================================
// Global Variables
// ===================================
const socket = io();
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let selectedVoice = null;
let translations = [];
let targetLang = 'yue';
let availableVoices = [];

// Language code mapping for TTS
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

// ===================================
// Settings Management
// ===================================

/**
 * Load all settings from localStorage
 * @returns {string|null} savedVoice - Previously saved voice name
 */
function loadSettings() {
    const savedLang = localStorage.getItem('targetLang');
    const savedVoice = localStorage.getItem('selectedVoice');
    const savedRate = localStorage.getItem('ttsRate');
    const savedVolume = localStorage.getItem('ttsVolume');
    const savedTheme = localStorage.getItem('theme');

    // Restore target language
    if (savedLang) {
        targetLang = savedLang;
        document.getElementById('targetLang').value = savedLang;
    }

    // Restore TTS rate
    if (savedRate) {
        ttsRate = parseFloat(savedRate);
        document.getElementById('rateSlider').value = ttsRate;
        document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    }

    // Restore TTS volume
    if (savedVolume) {
        ttsVolume = parseFloat(savedVolume);
        document.getElementById('volumeSlider').value = ttsVolume;
        document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    }

    // Restore theme
    if (savedTheme) {
        document.documentElement.setAttribute('data-theme', savedTheme);
        updateThemeUI(savedTheme);
    }

    return savedVoice;
}

// ===================================
// Voice Management
// ===================================

/**
 * Load available voices and populate the voice selector
 */
function loadVoices() {
    availableVoices = speechSynthesis.getVoices();

    if (availableVoices.length === 0) {
        return;
    }

    const voiceSelect = document.getElementById('voiceSelect');
    const savedVoice = localStorage.getItem('selectedVoice');

    // Get current language's TTS code
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;

    // Filter voices with precise matching for Chinese variants
    const matchingVoices = availableVoices.filter(voice => {
        const voiceLang = voice.lang.toLowerCase();
        const targetLangLower = ttsLang.toLowerCase();

        // Special handling for Chinese variants
        if (targetLang === 'yue') {
            // Cantonese: only HK voices
            return voiceLang === 'zh-hk' ||
                voiceLang.includes('yue') ||
                (voice.name.includes('粵語') || voice.name.includes('粤语'));
        } else if (targetLang === 'zh-cn') {
            // Simplified Chinese: only mainland China voices
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
            // Traditional Chinese: only Taiwan voices
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
            // For other languages, exact match
            return voiceLang === targetLangLower || voiceLang.startsWith(targetLangLower.split('-')[0] + '-');
        }
    });

    // Use matching voices if available, otherwise show all
    const voicesToShow = matchingVoices.length > 0 ? matchingVoices : availableVoices;

    voiceSelect.innerHTML = '';

    // Add auto-select option
    const autoOption = document.createElement('option');
    autoOption.value = '';
    autoOption.textContent = '🤖 Auto (System Default)';
    voiceSelect.appendChild(autoOption);

    // Group voices by language
    const grouped = {};
    voicesToShow.forEach(voice => {
        const lang = voice.lang;
        if (!grouped[lang]) grouped[lang] = [];
        grouped[lang].push(voice);
    });

    // Add voice options (clean voice name - remove ALL parentheses content)
    Object.keys(grouped).sort().forEach(lang => {
        grouped[lang].forEach(voice => {
            const option = document.createElement('option');
            option.value = voice.name;

            // Remove ALL parentheses and their content from voice name
            // Example: "Eddy (Chinese (China mainland))" -> "Eddy"
            // Also remove any stray '(' or ')' left over
            let cleanName = voice.name.replace(/\s*\([^)]*\)|[()]/g, '').trim();

            option.textContent = cleanName;
            voiceSelect.appendChild(option);
        });
    });

    // Restore previously selected voice if it's still available in current language
    if (savedVoice) {
        const voiceExists = voicesToShow.find(v => v.name === savedVoice);
        if (voiceExists) {
            voiceSelect.value = savedVoice;
            selectedVoice = voiceExists;
        } else {
            // Clear saved voice if not available for current language
            selectedVoice = null;
        }
    }

    console.log(`✅ Loaded ${availableVoices.length} voices, showing ${voicesToShow.length} for ${targetLang}`);
}

/**
 * Handle voice selection change
 */
function changeVoice() {
    const voiceSelect = document.getElementById('voiceSelect');
    const voiceName = voiceSelect.value;

    if (voiceName) {
        selectedVoice = availableVoices.find(v => v.name === voiceName);
        localStorage.setItem('selectedVoice', voiceName);
        console.log(`Selected voice: ${voiceName}`);
    } else {
        selectedVoice = null;
        localStorage.removeItem('selectedVoice');
        console.log('Using auto voice selection');
    }
}

/**
 * Handle language change - reload voice list and clear translations
 */
function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    localStorage.setItem('targetLang', targetLang);

    // Reload voice list to show appropriate voices
    loadVoices();

    // Clear cached translations for re-translation
    translations.forEach(item => {
        item.translated = null;
        item.currentLang = null;
    });
    renderTranslations();
}

// ===================================
// UI Management
// ===================================

/**
 * Toggle mobile menu visibility
 */
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

/**
 * Close mobile menu
 */
function closeMobileMenu() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');

    sidebar.classList.remove('mobile-open');
    overlay.classList.remove('active');
    toggle.classList.remove('active');
}

/**
 * Show about modal
 */
function showAbout() {
    document.getElementById('aboutModal').classList.add('active');
}

/**
 * Hide about modal
 * @param {Event} event - Click event
 */
function hideAbout(event) {
    if (!event || event.target.id === 'aboutModal' || event.target.classList.contains('about-close')) {
        document.getElementById('aboutModal').classList.remove('active');
    }
}

/**
 * Toggle between light and dark theme
 */
function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeUI(newTheme);
}

/**
 * Update theme toggle button UI
 * @param {string} theme - Current theme ('light' or 'dark')
 */
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

/**
 * Show sync indicator notification
 */
function showSyncIndicator() {
    const indicator = document.getElementById('syncIndicator');
    indicator.classList.add('show');
    setTimeout(() => indicator.classList.remove('show'), 3000);
}

// Handle ESC key to close modals and menus
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
    }
});

// ===================================
// Translation Functions
// ===================================

/**
 * Translate text using Google Translate API
 * @param {string} text - Text to translate
 * @param {string} targetLang - Target language code
 * @returns {Promise<string>} Translated text
 */
async function translateText(text, targetLang) {
    const cacheKey = `${text}_${targetLang}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) return cached;

    try {
        let translationLang = targetLang;
        let translated = text;

        // Special handling for Cantonese (yue)
        if (targetLang === 'yue') {
            try {
                const yueUrl = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=yue&dt=t&q=${encodeURIComponent(text)}`;
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

        // Fallback to standard translation if Cantonese failed
        if (translated === text) {
            const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${translationLang}&dt=t&q=${encodeURIComponent(text)}`;
            const response = await fetch(url);
            const data = await response.json();
            if (data && data[0] && data[0][0] && data[0][0][0]) {
                translated = data[0][0][0];
            }
        }

        // Cache the translation
        sessionStorage.setItem(cacheKey, translated);
        return translated;
    } catch (error) {
        console.error('Translation error:', error);
        return text + ' (translation failed)';
    }
}

// ===================================
// Text-to-Speech Functions
// ===================================

/**
 * Speak text using Web Speech API
 * @param {string} text - Text to speak
 */
function speakText(text) {
    if (!('speechSynthesis' in window)) {
        alert('Your browser does not support text-to-speech');
        return;
    }

    // Cancel any ongoing speech
    speechSynthesis.cancel();

    // Clean text (remove parentheses content)
    const cleanText = text.replace(/\s*\([^)]*\)\s*|[()]/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
    utterance.lang = ttsLang;
    utterance.rate = ttsRate;
    utterance.volume = ttsVolume;

    // Use user-selected voice if available
    if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log(`Using selected voice: ${selectedVoice.name}`);
    } else {
        // Auto-select appropriate voice
        const voices = speechSynthesis.getVoices();
        let autoVoice = voices.find(v => v.lang === ttsLang);
        if (!autoVoice) {
            const baseLang = ttsLang.split('-')[0];
            autoVoice = voices.find(v => v.lang.startsWith(baseLang + '-'));
        }
        if (autoVoice) {
            utterance.voice = autoVoice;
            console.log(`Using auto voice: ${autoVoice.name}`);
        }
    }

    utterance.onerror = (e) => {
        console.error('TTS error:', e);
    };

    speechSynthesis.speak(utterance);
}

/**
 * Toggle TTS on/off
 */
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

/**
 * Update TTS rate from slider
 */
function updateRate() {
    ttsRate = parseFloat(document.getElementById('rateSlider').value);
    document.getElementById('rateValue').textContent = ttsRate.toFixed(1) + 'x';
    localStorage.setItem('ttsRate', ttsRate);
}

/**
 * Update TTS volume from slider
 */
function updateVolume() {
    ttsVolume = parseFloat(document.getElementById('volumeSlider').value);
    document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
    localStorage.setItem('ttsVolume', ttsVolume);
}

// ===================================
// Translation Rendering
// ===================================

/**
 * Render all translations in the list
 */
async function renderTranslations() {
    const list = document.getElementById('translationsList');
    document.getElementById('itemCount').textContent = translations.length;

    if (translations.length === 0) {
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <div>Waiting for translations...</div>
                <small style="display: block; margin-top: 0.5rem; opacity: 0.7;">
                    Translations will appear here in real-time
                </small>
            </div>
        `;
        return;
    }

    // Reverse order to show newest first
    const reversed = [...translations].reverse();
    const items = await Promise.all(
        reversed.map(item => createTranslationHTML(item))
    );

    list.innerHTML = items.join('');
}

/**
 * Add a new translation to the list
 * @param {Object} data - Translation data
 */
async function addTranslation(data) {
    const list = document.getElementById('translationsList');
    const emptyState = list.querySelector('.empty-state');

    if (emptyState) {
        list.innerHTML = '';
    }

    const html = await createTranslationHTML(data);
    list.innerHTML = html + list.innerHTML;
    document.getElementById('itemCount').textContent = translations.length;
}

/**
 * Create HTML for a translation card
 * @param {Object} item - Translation item
 * @returns {Promise<string>} HTML string
 */
async function createTranslationHTML(item) {
    const itemId = `translation-${item.id}`;

    // Translate if needed
    if (!item.translated || item.currentLang !== targetLang) {
        item.currentLang = targetLang;

        // Show loading state
        setTimeout(async () => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.innerHTML = '<span style="color: var(--text-secondary); font-style: italic;">Translating...</span>';
                }
            }
        }, 0);

        // Perform translation
        item.translated = await translateText(item.corrected, targetLang);

        // Update with translated text
        setTimeout(() => {
            const elem = document.getElementById(itemId);
            if (elem) {
                const targetDiv = elem.querySelector('.text-target');
                if (targetDiv) {
                    targetDiv.textContent = item.translated;
                }
            }
        }, 0);
    }

    const correctedBadge = item.is_corrected
        ? '<span class="card-badge">✓ Corrected</span>'
        : '';
    const correctedClass = item.is_corrected ? 'corrected' : '';
    const translatedText = item.translated || 'Translating...';

    return `
        <div class="translation-card ${correctedClass}" id="${itemId}">
            <div class="card-header">
                <span class="card-time">${item.timestamp}</span>
                <div style="display: flex; align-items: center; gap: 0.5rem;">
                    ${correctedBadge}
                    <button class="tts-icon" onclick="speakText('${escapeHtml(translatedText)}')">🔊</button>
                </div>
            </div>
            <div class="text-source">${escapeHtml(item.corrected)}</div>
            <div class="text-target">${escapeHtml(translatedText)}</div>
        </div>
    `;
}

/**
 * Escape HTML and quotes for safe insertion
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, "\\'");
}

// ===================================
// Data Management Functions
// ===================================

/**
 * Clear local translations display
 */
function clearLocal() {
    if (translations.length === 0) return;
    if (confirm('Clear all translations from display?\n\nNote: This only clears your local view.')) {
        translations = [];
        renderTranslations();
    }
}

/**
 * Export translations to text file
 */
function exportData() {
    if (translations.length === 0) {
        alert('No translations to export');
        return;
    }

    const langName = document.getElementById('targetLang').selectedOptions[0].text;
    let content = '═══════════════════════════════════════════════════\n';
    content += '       EzySpeechTranslate Export\n';
    content += '═══════════════════════════════════════════════════\n\n';
    content += `Generated: ${new Date().toLocaleString()}\n`;
    content += `Target Language: ${langName}\n`;
    content += `Total Entries: ${translations.length}\n\n`;
    content += '═══════════════════════════════════════════════════\n\n';

    translations.forEach((item, index) => {
        content += `[${String(index + 1).padStart(3, '0')}] ${item.timestamp}\n`;
        if (item.is_corrected) {
            content += `      [✓ CORRECTED]\n`;
        }
        content += `\n      Original:\n      ${item.corrected}\n`;
        content += `\n      Translation (${targetLang.toUpperCase()}):\n      ${item.translated || 'Not translated'}\n`;
        content += `\n${'─'.repeat(55)}\n\n`;
    });

    content += '═══════════════════════════════════════════════════\n';
    content += '              End of Export\n';
    content += '═══════════════════════════════════════════════════\n';

    // Create and download file
    const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    const timestamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, -5);
    a.download = `EzySpeech_${targetLang}_${timestamp}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

// ===================================
// Socket.IO Event Handlers
// ===================================

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

    // Auto-speak if TTS is enabled
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
});

// ===================================
// Initialization
// ===================================

if ('speechSynthesis' in window) {
    // Load saved settings
    loadSettings();

    // Load available voices
    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    loadVoices();
    setTimeout(loadVoices, 100);

    console.log('✅ EzySpeechTranslate Ready with Voice Selection');
} else {
    console.warn('⚠️ Speech Synthesis not supported');
}

console.log('✅ EzySpeechTranslate Client Ready');