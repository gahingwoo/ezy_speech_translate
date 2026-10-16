/* The listener page, part of: Drawing the stream, and the AI status.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

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
    trace('Initial render: ' + initialBatch + ' of ' + translations.length + ' items (virtual scrolling)');
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
    trace('Rendered items ' + startIdx + '-' + endIdx + '/' + translations.length);
    
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
    
    trace('Virtual scroll: rendering items ' + renderedCount + '-' + nextBatchEnd + '...');
    await renderTranslationsBatch(renderedCount, nextBatchEnd);
    
    isRenderingMore = false;
}

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

            trace('Loaded ' + translations.length + ' translations (total: ' + translationsTotal + ')');
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
        trace(`Cannot load more: isLoadingMore=${isLoadingMore}, hasMore=${hasMoreTranslations}`);
        return;
    }
    
    isLoadingMore = true;
    translationsOffset += translationsLimit;
    
    trace(`Loading more at offset ${translationsOffset}, limit ${translationsLimit}...`);
    
    try {
        const response = await fetch(
            '/api/translations?offset=' + translationsOffset + '&limit=' + translationsLimit
            + '&api_token=' + encodeURIComponent(apiSessionToken)
            + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main')
        );
        
        if (response.ok) {
            const data = await response.json();
            const newTranslations = data.translations || [];
            
            trace(`Got ${newTranslations.length} more items (has_more=${data.has_more})`);
            
            // Append to existing translations (newest at bottom)
            translations.push(...newTranslations);
            hasMoreTranslations = data.has_more || false;
            translationsTotal = data.total || 0;
            
            trace(`Loaded ${newTranslations.length} more translations (${translations.length} visible, ${translationsTotal} total, has_more=${hasMoreTranslations})`);
            
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
    trace('Processing ' + batch.length + ' pending translations');
    
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
        trace('Transitioning to understanding: wordCount=' + wordCount + ', hasPunctuation=' + hasPunctuation);
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
    
    trace('Intermediate machine started:', { stage: startStage, wordCount, animStyle: 'dots', duration: baseStatusChangeDuration + 'ms' });
    
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
    
    trace('AI thinking machine started:', { startStage, wordCount, isLongText, animStyle: 'dots' });
    
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
            trace('Thinking machine stopped (max duration reached)');
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

/* Translations the server sends. Each screen says which language it reads in,
   and the server translates every line once per language and pushes it to the
   screens reading that language, where every screen used to ask for its own
   copy of each line. One that has not arrived in time is asked for as before. */
let serverTranslation = false;
const pushedTranslations = {};       // id|lang -> {source, translated}
const pushWaiters = {};              // id|lang -> [resolve]
const PUSH_WAIT_MS = 6000;

function announceReadingLanguage() {
    if (!socket || !socket.connected) return;
    socket.emit('reading_language', { lang: displayMode === 'transcription' ? null : targetLang });
}

function receivePushedTranslation(data) {
    if (!data || data.id == null || !data.lang) return;
    const key = data.id + '|' + data.lang;
    pushedTranslations[key] = { source: data.source, translated: data.translated };
    (pushWaiters[key] || []).forEach(function (done) { done(); });
    delete pushWaiters[key];
}

/* The server's translation of this line into lang, if it has one or sends one
   within PUSH_WAIT_MS: kept on the line from history, or pushed. Only for the
   words the line has now; a correction makes earlier ones stale. */
async function serverTranslationFor(item, lang) {
    const source = item.corrected || item.original || '';
    const key = item.id + '|' + lang;
    const pick = function () {
        const kept = item.translations && item.translations[lang];
        if (kept && kept.source === source) return kept.text;
        const pushed = pushedTranslations[key];
        if (pushed && pushed.source === source) return pushed.translated;
        return null;
    };
    const answered = function () {
        const pushed = pushedTranslations[key];
        return !!(pushed && pushed.source === source);
    };
    let found = pick();
    // An answer of null is the server saying it could not: ask straight away.
    if (found || answered() || !serverTranslation || item.id == null) return found;
    await new Promise(function (done) {
        const timer = setTimeout(done, PUSH_WAIT_MS);
        (pushWaiters[key] = pushWaiters[key] || []).push(function () { clearTimeout(timer); done(); });
    });
    return pick();
}

async function translateInBackground(item, itemId, textEl) {
    // Use item's current language if set, otherwise use global targetLang
    const lang = item.currentLang || targetLang;
    // Once per line and language at a time. A line arriving without an
    // interim row was translated twice: once as its row was built and again
    // as it was added, the second clearing what the first was typing.
    const inFlight = (item.corrected || '') + '\u001f' + lang;
    if (item._translating === inFlight) return;
    item._translating = inFlight;
    // Translate asynchronously and update DOM when done
    try {
        trace('Starting translation for item ' + itemId + ', target lang: ' + lang + ', text length: ' + (item.corrected ? item.corrected.length : 0));

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
                trace('Switched to translated state, showing "即將呈現翻譯"');
            }
        }
        
        const spoken = item.source_language || item.language || '';
        const sameTongue = sameLanguage(spoken, lang);
        const fromServer = sameTongue ? null : await serverTranslationFor(item, lang);
        const translated = sameTongue
            ? item.corrected
            : (fromServer || await translateText(item.corrected, lang));
        item.translated = translated || item.corrected;
        item.currentLang = lang;

        // translateText hands back the original when the call times out or the
        // service refuses, so a failure and a success look identical: a reader
        // on 简体中文 just sees an English line and no reason for it. Two
        // different languages and the same words back is not a translation.
        item.translationFailed = !sameTongue
            && (item.translated || '').trim() === (item.corrected || '').trim();

        // Fire-and-forget: cache translation on server so future clients skip
        // this call. Not when it came from the server, which has it already.
        if (translated && item.id != null && !fromServer) {
            fetch('/api/translations/' + item.id + '/translated?api_token=' + encodeURIComponent(apiSessionToken) + '&room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main'), {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ translated: translated, lang: lang })
            }).catch(() => {}); // silent — non-critical
        }

        trace('Translation complete (' + item.translated.length + ' chars): ' + item.translated.substring(0, 100));
        
        // Update DOM if element still exists
        const elem2 = document.getElementById(itemId);
        if (elem2) {
            // The one on the page now: the row may have been drawn again
            // while the translation was on its way, and writing into the copy
            // taken before it left the reader looking at an empty line.
            if (!textEl || !textEl.isConnected) {
                textEl = elem2.querySelector('.text-target');
            }
            
            // Stop AI thinking machine
            if (textEl) {
                stopAIThinkingMachine(textEl);
                trace('Stopped AI thinking machine, showing translation');
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
                trace('Auto-playing translation via TTS');
                speakText(item.translated, true);
            }
        }
    } catch (e) {
        console.warn('Background translation failed for item ' + itemId + ':', e.message);
    } finally {
        if (item._translating === inFlight) item._translating = null;
    }
}

function copyTranslationFromButton(button) {
    const id = button.getAttribute('data-translation-id');
    trace('Copy button clicked with ID:', id);
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
