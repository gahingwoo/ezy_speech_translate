/* The listener page, part of: Translation, reading aloud, copying.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

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
            trace('Text length:', text.length, '- splitting for better translation...');
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
                    trace('Cantonese translation successful (' + result.length + ' chars):', result.substring(0, 80) + (result.length > 80 ? '...' : ''));
                    return translated;
                }
                console.warn('Cantonese translation response empty or malformed');
            } catch (err) {
                console.warn('Cantonese translation failed, falling back to zh-TW:', err.message);
                translationLang = 'zh-TW';
            }
        }

        // Standard translation
        trace('Translating to (' + translationLang + ') - text length:', text.length, 'chars');
        
        const result = await translateViaApi(text, translationLang);
        
        if (result && result.length > 0) {
            trace('Translation successful (' + result.length + ' chars):', result.substring(0, 80) + (result.length > 80 ? '...' : ''));
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
        trace('Using local cache:', translationCache[cacheKey].substring(0, 80));
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

async function translateLongText(text, targetLang, translationLang) {
    try {
        // Split by sentences: periods, question marks, exclamation marks, or newlines
        const sentenceRegex = /[。！？!?.；;\n]+/;
        let sentences = text.split(sentenceRegex).filter(s => s.trim().length > 0);
        
        // If still too few sentences, split by commas for longer segments
        if (sentences.length < 3) {
            sentences = text.split(/[，,、；;\n]+/).filter(s => s.trim().length > 0);
        }
        
        trace('Splitting long text into', sentences.length, 'segments');
        
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
        trace('Long text translation complete:', result.substring(0, 50) + '...');
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
        trace('Double-tap detected! Stopping TTS playback...');
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
    trace(`Queued TTS (auto=${isAutoPlay}): ${text.substring(0, 50)}... Queue length: ${ttsQueue.length}`);
    
    // Start processing queue if nothing is currently playing
    if (!isTTSPlaying) {
        processTTSQueue();
    }
}

function processTTSQueue() {
    // Process next item in queue
    if (ttsQueue.length === 0) {
        isTTSPlaying = false;
        trace('TTS Queue empty');
        return;
    }
    
    if (isTTSPlaying) {
        trace('TTS still playing, waiting...');
        return;
    }
    
    const item = ttsQueue.shift();
    trace(`Playing from queue (auto=${item.isAutoPlay}): ${item.text.substring(0, 50)}...`);
    
    isTTSPlaying = true;
    
    speakTextSystem(item.text);
}

function clearTTSQueue() {
    // Clear all pending TTS and stop current playback
    trace(`Clearing TTS queue (${ttsQueue.length} items)`);
    ttsQueue = [];
    isTTSPlaying = false;
    
    // Stop current playback
    if ('speechSynthesis' in window) {
        speechSynthesis.cancel();
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
        trace('Using selected system voice: ' + selectedVoice.name);
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
            trace('Using auto system voice: ' + autoVoice.name);
        }
    }

    utterance.onend = function () {
        trace('System TTS finished');
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
    trace('Attempting to copy:', textToCopy);

    if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(textToCopy).then(function () {
            trace('Copied successfully with clipboard API');
            showCopyFeedback(id);
        }).catch(function (err) {
            trace('Clipboard API failed, trying fallback:', err);
            copyWithFallback(id, textToCopy);
        });
    } else {
        trace('Clipboard API not available, using fallback');
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
            trace('Copied successfully with fallback method');
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
