const socket = io();
let ttsEnabled = false;
let ttsRate = 1.0;
let ttsVolume = 1.0;
let translations = [];
let targetLang = 'yue';

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
    'hi': 'hi-IN'
};

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

function showAbout() {
    document.getElementById('aboutModal').classList.add('active');
}

function hideAbout(event) {
    if (!event || event.target.id === 'aboutModal' || event.target.classList.contains('about-close')) {
        document.getElementById('aboutModal').classList.remove('active');
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
    }
});

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    sessionStorage.setItem('theme', newTheme);

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

const savedTheme = sessionStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);

window.addEventListener('DOMContentLoaded', () => {
    updateThemeUI(savedTheme);
});

let isAdminRecording = false;

function updateConnectionStatus(connected, recording = false) {
    const badge = document.getElementById('statusBadge');
    const text = badge.querySelector('span:last-child');

    isAdminRecording = recording;

    if (!connected) {
        badge.className = 'connection-badge offline';
        text.textContent = 'Offline';
    } else if (recording) {
        badge.className = 'connection-badge online';
        text.textContent = 'Live';
    } else {
        badge.className = 'connection-badge waiting';
        text.textContent = 'Waiting';
    }
}

function showSyncIndicator() {
    const indicator = document.getElementById('syncIndicator');
    indicator.classList.add('show');
    setTimeout(() => {
        indicator.classList.remove('show');
    }, 3000);
}

async function translateText(text, targetLang) {
    const cacheKey = `${text}_${targetLang}`;
    const cached = sessionStorage.getItem(cacheKey);
    if (cached) return cached;

    try {
        let translationLang = targetLang;
        let translated = text;

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

        if (translated === text) {
            const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${translationLang}&dt=t&q=${encodeURIComponent(text)}`;
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

socket.on('connect', () => {
    console.log('Connected to server');
    updateConnectionStatus(true);
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    updateConnectionStatus(false);
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
});

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

    const reversed = [...translations].reverse();
    const items = await Promise.all(
        reversed.map(item => createTranslationHTML(item))
    );

    list.innerHTML = items.join('');
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
}

async function createTranslationHTML(item) {
    const itemId = `translation-${item.id}`;

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
                }
            }
        }, 0);
    }

    const correctedBadge = item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : '';
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

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML.replace(/'/g, "\\'");
}

function speakText(text) {
    if (!('speechSynthesis' in window)) {
        alert('Your browser does not support text-to-speech');
        return;
    }

    speechSynthesis.cancel();

    const cleanText = text.replace(/\s*\([^)]*\)\s*/g, '').trim();
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);

    const ttsLang = TTS_LANG_MAP[targetLang] || targetLang;
    utterance.lang = ttsLang;
    utterance.rate = ttsRate;
    utterance.volume = ttsVolume;

    const voices = speechSynthesis.getVoices();
    let selectedVoice = voices.find(v => v.lang === ttsLang);

    if (!selectedVoice) {
        const baseLang = ttsLang.split('-')[0];
        selectedVoice = voices.find(v => v.lang.startsWith(baseLang + '-'));
    }

    if (selectedVoice) {
        utterance.voice = selectedVoice;
        console.log(`Using voice: ${selectedVoice.name} (${selectedVoice.lang})`);
    }

    utterance.onerror = (e) => {
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
}

function updateVolume() {
    ttsVolume = parseFloat(document.getElementById('volumeSlider').value);
    document.getElementById('volumeValue').textContent = Math.round(ttsVolume * 100) + '%';
}

async function changeLanguage() {
    const select = document.getElementById('targetLang');
    targetLang = select.value;
    translations.forEach(item => {
        item.translated = null;
        item.currentLang = null;
    });
    await renderTranslations();
}

function clearLocal() {
    if (translations.length === 0) return;
    if (confirm('Clear all translations from display?\n\nNote: This only clears your local view.')) {
        translations = [];
        renderTranslations();
    }
}

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

if ('speechSynthesis' in window) {
    let voicesLoaded = false;

    function loadVoices() {
        if (voicesLoaded) return;
        const voices = speechSynthesis.getVoices();
        if (voices.length > 0) {
            voicesLoaded = true;
            console.log(`Loaded ${voices.length} TTS voices`);
            const langs = [...new Set(voices.map(v => v.lang))].sort();
            console.log('Available TTS languages:', langs);
        }
    }

    speechSynthesis.addEventListener('voiceschanged', loadVoices);
    loadVoices();
    setTimeout(loadVoices, 100);
}

console.log('✅ EzySpeechTranslate Client Ready');