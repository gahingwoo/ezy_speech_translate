/* The listener page, part of: The live connection, and announcements.
   One of the files user.html loads in order (see the list there); they
   share one scope, as the single user.js they were cut from did. */

/* ===================================
   Socket.IO Events
   =================================== */

function setupSocketEventListeners() {
    // Prevent multiple registrations of the same listeners
    if (socketListenersSetup) {
        trace('Socket listeners already setup, skipping');
        return;
    }

    if (!socket) {
        console.warn('Socket not initialized, cannot setup listeners');
        return;
    }

    socketListenersSetup = true;
    trace('Setting up Socket.IO event listeners...');

    socket.on('connect', async () => {
        trace('Connected to server');
        setConnectionStatus('online');
        // Attempt fast load with cached token; ready event will retry if this returns 401.
        await loadInitialTranslations();
    });

    socket.on('line_translated', receivePushedTranslation);

    socket.on('ready', async (data) => {
        // A new connection is a new socket on the server: say again which
        // language this one reads, before the history is asked for.
        serverTranslation = !!(data && data.server_translation);
        announceReadingLanguage();
        // Server sent a fresh API token for this session.
        if (data && data.api_token) {
            const prevToken = apiSessionToken;
            apiSessionToken = data.api_token;
            localStorage.setItem('apiSessionToken', apiSessionToken);
            trace('Fresh API token received');
            // Only reload if the connect attempt used a stale/rejected token.
            if (!prevToken || prevToken !== apiSessionToken) {
                await loadInitialTranslations();
            }
            loadScriptureRecord();
        }
    });

    // Feature 2: Announcement from admin
    socket.on('announcement', (data) => {
        showAnnouncement(data.text || data.message || '', data.duration ?? 10000, data.type || 'info');
    });

    socket.on('disconnect', () => {
        trace('Disconnected from server');
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
        trace('History message received (ignored, using HTTP API)');
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
            }

            // Smart chunk detection: check if we should transition from listening to understanding
            const textEl = tempCard.querySelector('.text-target');
            if (textEl && activeChunkTracking[tempId]) {
                const finalText = data.original || data.text || '';
                activeChunkTracking[tempId].text = finalText;
                
                // Check if content is stable enough to transition
                checkAndTransitionToUnderstanding(textEl, tempId, finalText);
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
                        trace('Stopped listening/intermediate state, starting AI thinking...');
                    }
                    
                    // Clean up chunk tracking for this temp_id
                    if (data.temp_id && activeChunkTracking[data.temp_id]) {
                        delete activeChunkTracking[data.temp_id];
                    }
                    
                    trace('Upgrading interim card to final:', {
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

                    trace('Source language check:', {
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
                            trace('Adding text-source element');
                            // The source line reads under the translation.
                            currentTextEl.insertAdjacentElement('afterend', sourceDiv);
                        } else {
                            // Update existing source div with correct text
                            existingSourceDiv.hidden = false;
                            existingSourceDiv.textContent = data.corrected || data.original;
                            existingSourceDiv.setAttribute('data-original-text', escapeHtml(data.corrected || data.original));
                            trace('Updating existing text-source element');
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
                        trace('Started AI thinking machine (preparingtranslating)');
                    } else if (currentTextEl) {
                        // Transcription mode, or the line is already in the
                        // language being read: the words are the answer.
                        stopAIThinkingMachine(currentTextEl);
                        currentTextEl.className = 'text-target';
                        currentTextEl.style.minHeight = '';
                        currentTextEl.textContent = data.corrected || data.original;
                        trace('Completed line displayed without translating');
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
        trace('Translation corrected:', data.id);
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
        trace('Order updated from admin:', data.translations.length, 'items');
        translations = data.translations;
        await renderTranslations();
        showSyncIndicator();
    });

    socket.on('history_cleared', () => {
        trace('History cleared');
        // The service is gone, and its readings with it: they were left
        // listed under a stream that no longer had any of them.
        clearScripture();
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
        trace('Items deleted:', data.ids);
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

/* Start-up is init(), once, at DOMContentLoaded. Settings, the interface
   language, voices, the socket and the Bible feature were also run here, at
   parse time and in a second DOMContentLoaded handler, so each happened two
   or three times on every load. */

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

trace('EzySpeechTranslate Client Ready');
