/* The listener page, part of: Saving and exporting, the AI summary, scrolling, keys.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

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
