let SERVER_URL = '';
let socket = null;
let authToken = null;
let translations = [];
let selectedItem = null;
let isRecording = false;
let recognition = null;
let recognitionLanguage = 'en-US';
let autoRestartEnabled = true;
let restartTimeout = null;
let finalTranscript = '';
let recognitionAttempts = 0;
const MAX_SILENT_TIME = 15000;
let lastSpeechTimestamp = Date.now();
let currentTempId = null;     // Temporary ID for linking interim->final (per utterance)

/* ===================================
   Toast helper (additive, mirrors user.js)
   =================================== */
const ADMIN_MAX_TOASTS = 4;

// PatternFly icons for the markup this file builds as strings. The paths are
// in the page once, as <symbol>s in the sprite render_admin.py emits; this only
// points at them. Never put an emoji here — the page is PatternFly 6.
function svgIcon(name, cls) {
    return '<svg class="pf-v6-svg' + (cls ? ' ' + cls : '') + '" aria-hidden="true"'
        + ' role="img" width="1em" height="1em" fill="currentColor">'
        + '<use href="#i-' + name + '"></use></svg>';
}
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    const container = document.getElementById('toastContainer');
    if (!container) { console.log('[toast]', type, message); return; }
    while (container.children.length >= ADMIN_MAX_TOASTS) container.firstChild.remove();

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
    close.onclick = function () { item.remove(); };
    action.appendChild(close);

    alert.append(icon, title, action);
    item.appendChild(alert);
    container.appendChild(item);

    // The group animates an item in from off-stage and out again.
    item.classList.add('pf-m-offstage-right');
    requestAnimationFrame(function () {
        item.classList.remove('pf-m-offstage-right');
        item.classList.add('pf-m-incoming');
    });
    setTimeout(function () {
        item.classList.add('pf-m-outgoing');
        setTimeout(function () { item.remove(); }, 300);
    }, duration);
}

/* ===================================
   i18n lookup helper (with English fallback)
   =================================== */
function t(key, fallback) {
    try {
        const lang = localStorage.getItem('displayLanguage') || 'en';
        const lib = window.sharedI18n || {};
        const langDict = lib[lang] || {};
        const enDict = lib.en || {};
        return langDict[key] || enDict[key] || fallback || key;
    } catch (e) {
        return fallback || key;
    }
}

let interimThrottleTimer = null;  // Throttle interim sends

// XSS Protection
function sanitizeInput(input) {
    if (typeof input !== 'string') return '';
    return input
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
        .replace(/\//g, '&#x2F;')
        .trim();
}

function validateText(text, maxLength = 5000) {
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

    return { valid: true, text: trimmed };
}

function toggleMobileMenu() {
    setSidebarOpen(!isSidebarOpen());
}

/* PatternFly owns the sidebar's state. Below xl the panel is a drawer that
   .pf-m-expanded slides in; from xl it is a column that .pf-m-collapsed folds
   away, and the page's main container widens into the space. One toggle, two
   classes, because which one applies depends on the width. */
function sidebarIsWide() {
    return window.matchMedia('(min-width: 75rem)').matches;
}

function isSidebarOpen() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return false;
    return sidebarIsWide()
        ? !sidebar.classList.contains('pf-m-collapsed')
        : sidebar.classList.contains('pf-m-expanded');
}

function setSidebarOpen(open) {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    const toggle = document.getElementById('mobileMenuToggle');
    if (!sidebar) return;
    const wide = sidebarIsWide();
    sidebar.classList.toggle('pf-m-collapsed', wide && !open);
    sidebar.classList.toggle('pf-m-expanded', !wide && open);
    if (overlay) overlay.classList.toggle('active', open && !wide);
    if (toggle) {
        toggle.classList.toggle('active', open);
        toggle.setAttribute('aria-expanded', String(open));
    }
}

function closeMobileMenu() {
    // Only the drawer closes on its own; folding the desktop panel away
    // because someone pressed a button in it would be a surprise.
    if (!sidebarIsWide()) setSidebarOpen(false);
}

function showAbout() {
    document.getElementById('aboutModal').classList.add('active');
}

function hideAbout(event) {
    if (!event || event.target.id === 'aboutModal' || event.target.classList.contains('about-close')) {
        document.getElementById('aboutModal').classList.remove('active');
    }
}

function showShortcuts() {
    const m = document.getElementById('shortcutsModal');
    if (m) m.classList.add('active');
}
function hideShortcuts(event) {
    if (event && event.target !== event.currentTarget) return;
    const m = document.getElementById('shortcutsModal');
    if (m) m.classList.remove('active');
}

/* ===================================
   Input / Export modals (replace prompt())
   =================================== */
let __inputModalCallback = null;
function showInputModal(opts) {
    opts = opts || {};
    const m = document.getElementById('inputModal');
    const titleEl = document.getElementById('inputModalTitle');
    const labelEl = document.getElementById('inputModalLabel');
    const fieldEl = document.getElementById('inputModalField');
    if (!m || !fieldEl) return;
    if (opts.title && titleEl) titleEl.textContent = opts.title;
    if (opts.label && labelEl) labelEl.textContent = opts.label;
    fieldEl.value = opts.value || '';
    __inputModalCallback = opts.onConfirm || null;
    m.classList.add('active');
    setTimeout(function () { try { fieldEl.focus(); } catch (e) {} }, 50);
}
function hideInputModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const m = document.getElementById('inputModal');
    if (m) m.classList.remove('active');
    __inputModalCallback = null;
}
function __inputModalConfirm() {
    const fieldEl = document.getElementById('inputModalField');
    const val = fieldEl ? fieldEl.value : '';
    const cb = __inputModalCallback;
    hideInputModal();
    if (cb) cb(val);
}

function showExportModal() {
    const m = document.getElementById('exportModal');
    if (m) m.classList.add('active');
}
function hideExportModal(event) {
    if (event && event.target !== event.currentTarget) return;
    const m = document.getElementById('exportModal');
    if (m) m.classList.remove('active');
}
function __doExport(format) {
    hideExportModal();
    if (!format) return;
    const exportUrl = `${SERVER_URL}/api/export/${format}?token=${encodeURIComponent(authToken)}`;
    const link = document.createElement('a');
    link.href = exportUrl;
    link.target = '_blank';
    link.download = `transcriptions.${format}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    document.documentElement.classList.toggle('pf-v6-theme-dark', newTheme === 'dark');
    localStorage.setItem('theme', newTheme);

    updateThemeUI(newTheme);
}

function updateThemeUI(theme) {
    // The sun and the moon are both in the button; the stylesheet shows the
    // one that matches the theme, so only the label changes here.
    const text = document.getElementById('themeText');
    if (text) {
        text.textContent = theme === 'dark'
            ? t('lightMode', 'Light Mode')
            : t('darkMode', 'Dark Mode');
    }
}

function logout() {
    if (confirm('Are you sure you want to logout?')) {
        localStorage.removeItem('authToken');
        if (recognition && isRecording) {
            stopRecording();
        }
        if (socket) {
            socket.disconnect();
        }
        window.location.href = '/login';
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', async () => {
    // Apply saved theme
    const storedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', storedTheme);
    document.documentElement.classList.toggle('pf-v6-theme-dark', storedTheme === 'dark');
    updateThemeUI(storedTheme);

    // Load server config
    try {
        const response = await fetch('/api/config', {
            credentials: 'include',
            headers: {'Accept': 'application/json'}
        });
        const config = await response.json();

        // Prefer external URL if configured (for CF Tunnel or reverse proxy)
        if (config.mainServerUrl) {
            SERVER_URL = config.mainServerUrl;
        } else {
            // Fallback to building URL from protocol and port
            const protocol = config.mainServerProtocol || window.location.protocol.replace(':', '');
            SERVER_URL = `${protocol}://${window.location.hostname}:${config.mainServerPort}`;
        }

        console.log('Main server URL:', SERVER_URL);
    } catch (error) {
        console.error('Failed to load config:', error);
        SERVER_URL = `${window.location.protocol}//${window.location.hostname}:1915`;
    }

    // Check authentication
    authToken = localStorage.getItem('authToken');
    if (!authToken) {
        window.location.href = '/login';
        return;
    }

    // Listen for display language changes
    const displayLangSelect = document.getElementById('displayLanguage');
    if (displayLangSelect) {
        displayLangSelect.addEventListener('change', () => {
            renderTranscriptions();
            updateRecordButton();
            updateSystemInfo();
        });
    }

    // Initialize app
    loadAudioDevices();
    startSystemMonitor();
    connectWebSocket();
    
    // Load TTS cache stats on page load
    setTimeout(() => {
        refreshTTSCacheStats();
    }, 1000);
    
    // Auto-refresh TTS cache stats every 30 seconds
    setInterval(() => {
        refreshTTSCacheStats();
    }, 30000);
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    const tag = (e.target && e.target.tagName) || '';
    const isText = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target && e.target.isContentEditable);

    if (e.key === 'Escape') {
        hideAbout();
        hideShortcuts();
        hideInputModal();
        hideExportModal();
        closeMobileMenu();
        if (selectedItem) {
            cancelCorrection();
        }
        return;
    }

    // "?" opens shortcuts (allow even when select is focused; block only on text fields)
    if (e.key === '?' && !isText && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault();
        showShortcuts();
        return;
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
        e.preventDefault();
        toggleRecording();
    }

    if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        if (selectedItem) {
            saveCorrection();
        }
    }
});

function connectWebSocket() {
    console.log('Connecting to WebSocket:', SERVER_URL);
    console.log('Using token:', authToken ? 'Yes' : 'No');
    
    // Admin should use separate persistent client ID (distinct from user client)
    const adminClientIdKey = '_admin_client_id';
    let clientId = localStorage.getItem(adminClientIdKey);
    if (!clientId) {
        clientId = 'admin_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now();
        localStorage.setItem(adminClientIdKey, clientId);
    }

    // Resolve target room: URL ?room= overrides localStorage; fall back to 'main'
    const urlParams = new URLSearchParams(window.location.search);
    const urlRoom = (urlParams.get('room') || '').trim();
    if (urlRoom && /^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/.test(urlRoom)) {
        localStorage.setItem('_admin_room_id', urlRoom);
    }
    window.CURRENT_ROOM_ID = localStorage.getItem('_admin_room_id') || 'main';
    console.log('Admin room scope:', window.CURRENT_ROOM_ID);

    socket = io(SERVER_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        query: {
            client_id: clientId,  // Send persistent client ID to server
            type: 'admin',  // Identify as admin client
            room: window.CURRENT_ROOM_ID
        }
    });

    socket.on('connect', () => {
        console.log('WebSocket connected - SID:', socket.id);
        updateStatus(true);

        if (authToken) {
            console.log('Sending admin_connect (room:', window.CURRENT_ROOM_ID, ')');
            socket.emit('admin_connect', {token: authToken, room: window.CURRENT_ROOM_ID});
        }
    });

    socket.on('admin_connected', (response) => {
        console.log('Admin connected response:', response);
        if (!response.success) {
            console.error('Admin connection rejected:', response.error);
            showToast('Session expired. Please login again.', 'danger');
            localStorage.removeItem('authToken');
            window.location.href = '/login';
        } else {
            if (response.room_id) {
                window.CURRENT_ROOM_ID = response.room_id;
                localStorage.setItem('_admin_room_id', response.room_id);
                updateRoomIndicator(response.room_id);
            }
            fetchTranslationHistory();
        }
    });

    socket.on('room_switched', (response) => {
        if (response && response.success && response.room_id) {
            window.CURRENT_ROOM_ID = response.room_id;
            localStorage.setItem('_admin_room_id', response.room_id);
            updateRoomIndicator(response.room_id);
            showToast('Switched to room: ' + response.room_id, 'success');
            if (typeof refreshQrRoomDropdown === 'function') refreshQrRoomDropdown();
            updateSystemInfo();
        }
    });

    socket.on('clients_update', (data) => {
        // Live-update the room-scoped listener count in System Info
        if (data && data.room_id === (window.CURRENT_ROOM_ID || 'main')) {
            const el = document.getElementById('sys-clients');
            if (el) el.textContent = data.count ?? 0;
        }
    });

    socket.on('disconnect', () => {
        console.log('Disconnected');
        updateStatus(false);
    });

    socket.on('connect_error', (error) => {
        console.error('Connection error:', error);
        updateStatus(false);
    });

    socket.on('error', (error) => {
        console.error('Socket error:', error);

        if (error.message && (error.message.includes('Unauthorized') || error.message.includes('Invalid token'))) {
            showToast('Session expired. Please login again.', 'danger');
            localStorage.removeItem('authToken');
            window.location.href = '/login';
        }
    });

    socket.on('history', (history) => {
        translations = history;
        renderTranscriptions();
    });

    socket.on('new_translation', (data) => {
        // Only process if not sent by this admin (server skips sender,
        // but handle edge cases like import from another admin)
        console.log('Received translation:', data);
        const exists = translations.some(t => t.id === data.id);
        if (!exists) {
            translations.push(data);
            renderTranscriptions();
        }
    });

    // Confirmation that our transcription was stored with its server-assigned ID
    socket.on('transcription_confirmed', (data) => {
        console.log('Transcription confirmed, id:', data.id);
        translations.push(data);
        renderTranscriptions();
    });

    socket.on('translation_corrected', (data) => {
        const index = translations.findIndex(t => t.id === data.id);
        if (index !== -1) {
            translations[index] = data;
            renderTranscriptions();
        }
    });

    socket.on('order_updated', (data) => {
        translations = data.translations;
        renderTranscriptions();
    });

    socket.on('history_cleared', () => {
        translations = [];
        renderTranscriptions();
    });

    socket.on('items_deleted', (data) => {
        // Remove deleted items from translations array
        const idsToDelete = data.ids || [];
        translations = translations.filter(item => !idsToDelete.includes(item.id));
        renderTranscriptions();
    });
}

function updateStatus(connected) {
    const badge = document.getElementById('statusBadge');
    if (connected) {
        // Short, because this sits in a masthead that has to fit a phone. The
        // element's title says which server it is.
        badge.className = 'pf-v6-c-label pf-m-green connection-badge online';
        badge.querySelector('.pf-v6-c-label__text').textContent = 'Online';
    } else {
        badge.className = 'pf-v6-c-label pf-m-red connection-badge offline';
        badge.querySelector('.pf-v6-c-label__text').textContent = 'Offline';
    }
}

async function fetchTranslationHistory() {
    try {
        console.log('Fetching translation history via HTTP...');
        const roomParam = window.CURRENT_ROOM_ID && window.CURRENT_ROOM_ID !== 'main'
            ? '?room=' + encodeURIComponent(window.CURRENT_ROOM_ID) : '';
        const response = await fetch(`${SERVER_URL}/api/history${roomParam}`, {
            credentials: 'include',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Accept': 'application/json'
            }
        });

        if (!response.ok) {
            console.warn(`Failed to fetch history: ${response.status}`);
            return;
        }

        const data = await response.json();
        if (data.success && Array.isArray(data.translations)) {
            translations = data.translations;
            console.log(`Loaded ${data.count} transcriptions from server`);
            renderTranscriptions();
        }
    } catch (error) {
        console.error('Failed to fetch translation history:', error);
    }
}

async function loadAudioDevices() {
    const select = document.getElementById('deviceSelect');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        select.innerHTML = '<option>Not supported</option>';
        showToast('Web Speech API not supported! — Please use Chrome or Edge.', 'warning');
        return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;

    try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const devices = await navigator.mediaDevices.enumerateDevices();
        const audioInputs = devices.filter(device => device.kind === 'audioinput');

        select.innerHTML = '<option>System Default</option>';
        stream.getTracks().forEach(track => track.stop());

        console.log(`Speech Recognition initialized`);
        setupRecognitionHandlers();

    } catch (error) {
        console.error('Microphone access error:', error);
        select.innerHTML = '<option>Access denied</option>';
        showToast('Microphone access denied! — Please allow microphone access.', 'danger');
    }
}

function setupRecognitionHandlers() {
    if (!recognition) return;

    recognition.onstart = () => {
        console.log('Speech recognition started');
        isRecording = true;
        updateRecordButton();
        updateInterimDisplay('Listening...', true);
        document.getElementById('autoRestartBadge').style.display = 'flex';
    };

    recognition.onend = () => {
        console.log('Speech recognition ended');

        if (isRecording && autoRestartEnabled) {
            console.log('Auto-restarting in 300ms...');
            clearTimeout(restartTimeout);
            restartTimeout = setTimeout(() => {
                if (isRecording) {
                    try {
                        recognition.start();
                        console.log('Recognition restarted');
                    } catch (e) {
                        console.error('Restart failed:', e);
                        setTimeout(() => {
                            if (isRecording) {
                                try {
                                    recognition.start();
                                } catch (err) {
                                    console.error('Second restart failed:', err);
                                    isRecording = false;
                                    updateRecordButton();
                                    updateInterimDisplay('Error: Cannot restart', false);
                                }
                            }
                        }, 1000);
                    }
                }
            }, 300);
        } else {
            isRecording = false;
            currentTempId = null;
            updateRecordButton();
            updateInterimDisplay('Stopped', false);
            document.getElementById('autoRestartBadge').style.display = 'none';
        }
    };

    recognition.onerror = (event) => {
        console.error('Recognition error:', event.error);

        switch (event.error) {
            case 'no-speech':
                console.log('No speech detected - will auto-restart');
                updateInterimDisplay('No speech detected...', true);
                break;

            case 'audio-capture':
                showToast('Cannot access microphone', 'danger');
                isRecording = false;
                updateRecordButton();
                updateInterimDisplay('Error: No microphone', false);
                document.getElementById('autoRestartBadge').style.display = 'none';
                break;

            case 'network':
                console.error('Network error - will retry');
                updateInterimDisplay('Network error, retrying...', true);
                break;

            case 'not-allowed':
                showToast('Microphone permission denied', 'danger');
                isRecording = false;
                updateRecordButton();
                updateInterimDisplay('Error: Permission denied', false);
                document.getElementById('autoRestartBadge').style.display = 'none';
                break;

            default:
                console.error('Unknown error:', event.error);
                updateInterimDisplay(`Error: ${event.error}`, true);
        }
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            const confidence = event.results[i][0].confidence;

            if (event.results[i].isFinal) {
                console.log(`SENDING FINAL: "${transcript}"`);
                // Send final with same temp_id so user-side replaces the interim card
                sendTranscription(transcript, confidence, true);
                currentTempId = null;  // Reset for next utterance
                updateInterimDisplay('Sent: ' + transcript.substring(0, 50) + '...', true);
                setTimeout(() => {
                    if (isRecording) {
                        updateInterimDisplay('Listening...', true);
                    }
                }, 500);
            } else {
                interimTranscript += transcript;
            }
        }

        if (interimTranscript.trim()) {
            // Generate temp_id for this utterance if not yet created
            if (!currentTempId) {
                currentTempId = 'rec_' + Date.now() + '_' + Math.random().toString(36).substr(2, 6);
            }
            // Throttle interim sends to max ~3/sec to avoid flooding
            if (!interimThrottleTimer) {
                sendTranscription(interimTranscript, 0.85, false);
                interimThrottleTimer = setTimeout(() => { interimThrottleTimer = null; }, 300);
            }
            updateInterimDisplay(interimTranscript, true);
        }
    };
}

function updateInterimDisplay(text, active) {
    const display = document.getElementById('interimDisplay');
    const textEl = document.getElementById('interimText');

    textEl.textContent = text;
    display.className = active ? 'interim-display active' : 'interim-display inactive';
}

function sendTranscription(text, confidence, isFinal = true) {
    if (!text || !socket || !socket.connected) {
        console.warn('Cannot send - no text or no connection');
        return;
    }

    const validation = validateText(text);
    if (!validation.valid) {
        console.error('Invalid input:', validation.error);
        updateInterimDisplay(validation.error, false);
        return;
    }

    const sanitizedText = validation.text;
    console.log(`SENDING: "${sanitizedText}" (confidence: ${confidence}, final: ${isFinal})`);

    socket.emit('new_transcription', {
        text: sanitizedText,
        language: recognitionLanguage.split('-')[0],
        timestamp: new Date().toISOString(),
        confidence: confidence,
        is_final: isFinal,
        temp_id: currentTempId
    });

    if (isFinal) {
        updateInterimDisplay('Sent: ' + sanitizedText.substring(0, 50) + '...', true);
    }
}

function updateRecordButton() {
    const btn = document.getElementById('recordBtn');
    const langSelect = document.getElementById('sourceLangSelect');

    const shared = window.sharedI18n || {};
    const lang = window._displayLanguage || localStorage.getItem('displayLanguage') || (navigator.language || 'en').split('-')[0];

    const span = btn.querySelector('[data-i18n]') || btn;

    if (isRecording) {
        const text = (shared[lang] && shared[lang]['stopRecording']) || 'Stop Recording';
        span.textContent = text;
        btn.className = 'pf-v6-c-button pf-m-danger recording';
        btn.setAttribute('aria-pressed', 'true');
        langSelect.disabled = true;
    } else {
        const text = (shared[lang] && shared[lang]['startRecording']) || 'Start Recording';
        span.textContent = text;
        btn.className = 'pf-v6-c-button pf-m-primary';
        btn.setAttribute('aria-pressed', 'false');
        langSelect.disabled = false;
    }
}

async function toggleRecording() {
    if (!recognition) {
        showToast('Speech Recognition not initialized. Please refresh.', 'warning');
        return;
    }

    if (!isRecording) {
        isRecording = true;
        recognitionAttempts = 0;
        finalTranscript = '';
        recognition.lang = recognitionLanguage;
        updateRecordButton();

        try {
            recognition.start();
            lastSpeechTimestamp = Date.now();
            console.log('Recognition started');
        } catch (error) {
            console.error('Start failed:', error);
            isRecording = false;
            updateRecordButton();
            showToast('Failed to start recording: ' + error.message, 'danger');
        }
    } else {
        stopRecording();
    }
}

function stopRecording() {
    console.log('Stopping recording');
    isRecording = false;
    autoRestartEnabled = false;

    if (restartTimeout) {
        clearTimeout(restartTimeout);
        restartTimeout = null;
    }

    if (recognition) {
        recognition.stop();
    }

    updateRecordButton();
    document.getElementById('autoRestartBadge').style.display = 'none';

    setTimeout(() => {
        autoRestartEnabled = true;
    }, 1000);
}

function changeSourceLanguage() {
    if (isRecording) {
        showToast('Cannot change language while recording. Please stop recording first.', 'danger');
        const select = document.getElementById('sourceLangSelect');
        select.value = recognitionLanguage;
        return;
    }

    const select = document.getElementById('sourceLangSelect');
    const oldLang = recognitionLanguage;
    recognitionLanguage = select.value;
    console.log(`Language: ${oldLang}${recognitionLanguage}`);
}

let draggedElement = null;
let draggedIndex = null;
let touchStartY = 0;
let touchElement = null;

function renderTranscriptions() {
    const list = document.getElementById('transcriptionsList');
    document.getElementById('itemCount').textContent = translations.length;

    // Define shared and lang at function scope for use throughout
    const shared = window.sharedI18n || {};
    const lang = window._displayLanguage || localStorage.getItem('displayLanguage') || (navigator.language || 'en').split('-')[0];

    if (translations.length === 0) {
        const noTrans = (shared[lang] && shared[lang]['noTranscriptionsYet']) || 'No transcriptions yet';
        const startHelp = (shared[lang] && shared[lang]['startRecordingHelp']) || 'Start recording to see transcriptions';
        // PatternFly's empty state, icon and all, is in the template as
        // #emptyStateTemplate rather than as a string here.
        list.replaceChildren();
        const tpl = document.getElementById('emptyStateTemplate');
        if (tpl) {
            const empty = tpl.content.cloneNode(true);
            empty.querySelector('.pf-v6-c-empty-state__title-text').textContent = noTrans;
            empty.querySelector('.pf-v6-c-empty-state__body').textContent = startHelp;
            list.appendChild(empty);
        }
        return;
    }

    // Display in reverse order (newest first)
    const reversed = [...translations].reverse();
    // PatternFly's data list: a row with a drag handle, a check and a cell.
    // .transcription-card stays on the row because admin.js's drag handlers
    // find rows by that class.
    list.innerHTML = reversed.map((item, index) => `
        <li class="pf-v6-c-data-list__item transcription-card ${selectedItem && selectedItem.id === item.id ? 'pf-m-selected selected' : ''}"
            draggable="true"
            data-id="${item.id}"
            data-index="${index}"
            onclick="selectItem(${item.id})"
            ondragstart="handleDragStart(event, ${index})"
            ondragend="handleDragEnd(event)"
            ondragover="handleDragOver(event)"
            ondrop="handleDrop(event, ${index})"
            ontouchstart="handleTouchStart(event, ${index})"
            ontouchmove="handleTouchMove(event)"
            ontouchend="handleTouchEnd(event)">
          <div class="pf-v6-c-data-list__item-row">
            <div class="pf-v6-c-data-list__item-control">
              <div class="pf-v6-c-data-list__item-draggable-button">
                <button class="pf-v6-c-button pf-m-plain drag-handle" type="button"
                        aria-label="Reorder this transcription"
                        onmousedown="event.stopPropagation()"
                        ontouchstart="event.stopPropagation()">
                  <span class="pf-v6-c-data-list__item-draggable-icon">${svgIcon('grip-vertical')}</span>
                </button>
              </div>
              <div class="pf-v6-c-data-list__check">
                <input type="checkbox" class="pf-v6-c-check__input card-checkbox"
                       aria-label="Select transcription"
                       data-id="${item.id}"
                       ${selectedItem && selectedItem.id === item.id ? 'checked' : ''}
                       onclick="handleCheckboxClick(event, ${item.id})">
              </div>
            </div>
            <div class="pf-v6-c-data-list__item-content">
              <div class="pf-v6-c-data-list__cell">
                <div class="card-header">
                  <span class="card-time">${escapeHtml(item.timestamp)}</span>
                  ${item.is_corrected ? `<span class="pf-v6-c-label pf-m-green pf-m-compact card-badge"><span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">${(shared && shared[lang] && shared[lang]['corrected']) || 'Corrected'}</span></span></span>` : ''}
                </div>
                <div class="card-text">${escapeHtml(item.corrected)}</div>
              </div>
            </div>
          </div>
        </li>
    `).join('');
}

function handleDragStart(event, index) {
    draggedElement = event.target;
    draggedIndex = index;
    event.target.classList.add('dragging');
    event.dataTransfer.effectAllowed = 'move';
    event.dataTransfer.setData('text/html', event.target.innerHTML);
}

function handleDragEnd(event) {
    event.target.classList.remove('dragging');
    document.querySelectorAll('.transcription-card').forEach(card => {
        card.classList.remove('drag-over');
    });
}

function handleDragOver(event) {
    if (event.preventDefault) {
        event.preventDefault();
    }
    event.dataTransfer.dropEffect = 'move';

    const target = event.target.closest('.transcription-card');
    if (target && target !== draggedElement) {
        target.classList.add('drag-over');
    }

    return false;
}

function handleDrop(event, dropIndex) {
    if (event.stopPropagation) {
        event.stopPropagation();
    }

    event.target.closest('.transcription-card')?.classList.remove('drag-over');

    if (draggedIndex !== dropIndex) {
        reorderTranslations(draggedIndex, dropIndex);
    }

    return false;
}

function handleTouchStart(event, index) {
    if (!event.target.classList.contains('drag-handle')) {
        return;
    }

    event.preventDefault();
    touchElement = event.currentTarget;
    draggedIndex = index;
    touchStartY = event.touches[0].clientY;

    touchElement.classList.add('dragging');
}

function handleTouchMove(event) {
    if (!touchElement) return;

    event.preventDefault();
    const touch = event.touches[0];
    const deltaY = touch.clientY - touchStartY;

    touchElement.style.transform = `translateY(${deltaY}px)`;
    touchElement.style.zIndex = '1000';

    const cards = document.querySelectorAll('.transcription-card');
    let targetIndex = -1;

    cards.forEach((card, idx) => {
        const rect = card.getBoundingClientRect();
        const cardMiddle = rect.top + rect.height / 2;

        if (touch.clientY < cardMiddle && idx > 0) {
            card.classList.add('drag-over');
            targetIndex = idx;
        } else {
            card.classList.remove('drag-over');
        }
    });
}

function handleTouchEnd(event) {
    if (!touchElement) return;

    event.preventDefault();

    touchElement.style.transform = '';
    touchElement.style.zIndex = '';
    touchElement.classList.remove('dragging');

    const cards = document.querySelectorAll('.transcription-card');
    let dropIndex = -1;

    cards.forEach((card, idx) => {
        if (card.classList.contains('drag-over')) {
            dropIndex = idx;
            card.classList.remove('drag-over');
        }
    });

    if (dropIndex !== -1 && dropIndex !== draggedIndex) {
        reorderTranslations(draggedIndex, dropIndex);
    }

    touchElement = null;
    draggedIndex = null;
}

function reorderTranslations(fromIndex, toIndex) {
    const actualFromIndex = translations.length - 1 - fromIndex;
    const actualToIndex = translations.length - 1 - toIndex;

    const [removed] = translations.splice(actualFromIndex, 1);
    translations.splice(actualToIndex, 0, removed);

    socket.emit('update_order', {translations});

    renderTranscriptions();
}

function handleCheckboxClick(event, id) {
    event.stopPropagation();
    selectItem(id);
}

function selectItem(id) {
    const item = translations.find(t => t.id === id);
    if (!item) return;

    selectedItem = item;

    document.getElementById('originalText').value = item.original;
    document.getElementById('correctedText').value = item.corrected;

    renderTranscriptions();
}

function addNewItem() {
    showInputModal({
        title: 'Add Transcription',
        label: 'Enter transcription text:',
        onConfirm: function (text) {
            if (!text) return;
            const validation = validateText(text);
            if (!validation.valid) {
                showToast(validation.error, 'danger');
                return;
            }
            socket.emit('new_transcription', {
                text: validation.text,
                language: 'manual'
            });
        }
    });
}

function editSelected() {
    if (!selectedItem) {
        showToast('Please select an item to edit', 'warning');
        return;
    }
    document.getElementById('correctedText').focus();
}

function deleteSelected() {
    const checkboxes = document.querySelectorAll('.card-checkbox:checked');
    if (checkboxes.length === 0) {
        showToast('Please select items to delete', 'warning');
        return;
    }

    if (!confirm(`Delete ${checkboxes.length} item(s)?`)) return;

    // Get all checked item IDs
    const itemsToDelete = Array.from(checkboxes).map(checkbox => {
        return parseInt(checkbox.getAttribute('data-id'));
    });

    // Emit delete event to server
    socket.emit('delete_items', {
        ids: itemsToDelete
    });
}

function saveCorrection() {
    if (!selectedItem) {
        showToast('No item selected', 'warning');
        return;
    }

    const corrected = document.getElementById('correctedText').value.trim();

    const validation = validateText(corrected);
    if (!validation.valid) {
        showToast(validation.error, 'danger');
        return;
    }

    socket.emit('correct_translation', {
        id: selectedItem.id,
        corrected_text: validation.text
    });

    showToast('Correction saved and broadcasted to all clients!', 'success');

    setTimeout(() => {
        cancelCorrection();
    }, 500);
}

function cancelCorrection() {
    selectedItem = null;
    document.getElementById('originalText').value = '';
    document.getElementById('correctedText').value = '';
    renderTranscriptions();
}

function clearHistory() {
    if (!confirm('Clear all transcriptions?\n\nThis cannot be undone.')) return;
    socket.emit('clear_history');
}

function exportData() {
    if (translations.length === 0) {
        showToast('No data to export', 'warning');
        return;
    }
    showExportModal();
}

function handleImportFile(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    if (!file.name.endsWith('.json')) {
        showToast('Please select a JSON file', 'danger');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const content = e.target.result;
            const data = JSON.parse(content);
            
            // Validate data structure
            if (!data.translations || !Array.isArray(data.translations)) {
                showToast('Invalid JSON format. Expected {translations: []}', 'danger');
                return;
            }

            // Validate each translation object has required fields
            const requiredFields = ['id', 'original', 'corrected'];
            for (const item of data.translations) {
                for (const field of requiredFields) {
                    if (!(field in item)) {
                        showToast(`Missing required field: ${field}`, 'danger');
                        return;
                    }
                }
            }

            importTranslations(data.translations);
        } catch (error) {
            showToast(`Error parsing JSON: ${error.message}`, 'danger');
            console.error('JSON parse error:', error);
        }
    };
    reader.readAsText(file);

    // Reset file input
    event.target.value = '';
}

function importTranslations(translationsToImport) {
    if (translationsToImport.length === 0) {
        showToast('No translations to import', 'warning');
        return;
    }

    const confirmed = confirm(
        `Ready to import ${translationsToImport.length} translation(s).\n\n` +
        `This will add them to your transcriptions.\n\n` +
        `Continue?`
    );

    if (!confirmed) return;

    console.log(`Importing ${translationsToImport.length} translations...`);

    // Show progress
    let imported = 0;
    let failed = 0;

    // Send each translation via socket
    for (const item of translationsToImport) {
        const validation = validateText(item.corrected);
        if (!validation.valid) {
            console.warn(`Skipping invalid translation: ${item.corrected}`);
            failed++;
            continue;
        }

        // Emit import event to server
        socket.emit('import_transcription', {
            id: item.id,
            original: item.original,
            corrected: item.corrected,
            timestamp: item.timestamp || new Date().toISOString(),
            is_corrected: item.is_corrected || true,
            language: item.language || 'imported',
            confidence: item.confidence || 0.95
        });

        imported++;
    }

    showToast(`Import completed! — ${imported} transcription(s) imported ${failed > 0 ? `${failed} skipped (validation failed)` : 'No errors'}`, 'danger');
    
    console.log(`Import completed: ${imported}/${translationsToImport.length}`);
}

function startSystemMonitor() {
    updateSystemInfo();
    setInterval(updateSystemInfo, 2000);
    // Refresh analytics every 10 s
    refreshAnalytics();
    setInterval(refreshAnalytics, 10000);
}

async function updateSystemInfo() {
    try {
        const roomSuffix = '?room=' + encodeURIComponent(window.CURRENT_ROOM_ID || 'main');
        const response = await fetch(`${SERVER_URL}/api/health${roomSuffix}`, {
            method: 'GET',
            credentials: 'include',
            headers: {
                'Authorization': `Bearer ${authToken}`,
                'Accept': 'application/json'
            }
        });
        const data = await response.json();

        const timestamp = new Date().toLocaleString('en-US', {
            month: '2-digit',
            day: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
        });

        // Counters
        const sysClients = document.getElementById('sys-clients');
        const sysTranscriptions = document.getElementById('sys-transcriptions');
        if (sysClients) sysClients.textContent = data.clients ?? 0;
        if (sysTranscriptions) sysTranscriptions.textContent = data.translations ?? 0;

        // Recording label
        const sysRecording = document.getElementById('sys-recording');
        if (sysRecording) {
            const shared = window.sharedI18n || {};
            const lang = window._displayLanguage || localStorage.getItem('displayLanguage') || (navigator.language || 'en').split('-')[0];
            const activeText = (shared[lang] && shared[lang]['active']) || 'Active';
            const stoppedText = (shared[lang] && shared[lang]['stopped']) || 'Stopped';
            if (isRecording) {
                sysRecording.className = 'pf-v6-c-label pf-m-green';
                sysRecording.innerHTML = `<span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">${activeText}</span></span>`;
            } else {
                sysRecording.className = 'pf-v6-c-label';
                sysRecording.innerHTML = `<span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">${stoppedText}</span></span>`;
            }
        }

        // Language label
        const sysLanguage = document.getElementById('sys-language');
        if (sysLanguage) {
            sysLanguage.innerHTML = `<span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text mono">${recognitionLanguage || 'en-US'}</span></span>`;
        }
    } catch (error) {
        console.error('Failed to fetch system info:', error);
    }
}

// ── Feature 2: Send Announcement ───────────────────────────────────────
function sendAnnouncement() {
    const textEl     = document.getElementById('announcementText');
    const durationEl = document.getElementById('announcementDuration');
    const typeEl     = document.getElementById('announcementType');
    if (!textEl || !socket) return;

    const text = textEl.value.trim();
    if (!text) {
        showToast('Please enter an announcement message.', 'warning');
        return;
    }

    socket.emit('send_announcement', {
        text:     text,
        duration: parseInt(durationEl?.value ?? '10000', 10),
        type:     typeEl?.value ?? 'info',
    });

    // Use a one-shot timeout to detect failure without capturing global errors
    const tid = setTimeout(() => {
        showToast('Announcement may not have reached the server.', 'warning');
    }, 5000);

    socket.once('announcement_sent', () => {
        clearTimeout(tid);
        showToast('Announcement sent to all viewers!', 'success', 3000);
        textEl.value = '';
    });
}

// ── Feature 9: Session Analytics ───────────────────────────────────────
async function refreshAnalytics() {
    if (!authToken) return;
    try {
        const res = await fetch(`${SERVER_URL}/api/analytics`, {
            method: 'GET',
            credentials: 'include',
            headers: { 'Authorization': `Bearer ${authToken}`, 'Accept': 'application/json' }
        });
        if (!res.ok) return;
        const d = await res.json();

        const set = (id, val) => {
            const el = document.getElementById(id);
            if (el) el.textContent = val ?? '—';
        };
        set('stat-duration',     d.duration_display);
        set('stat-peak',         d.peak_clients);
        set('stat-words',        d.total_words);
        set('stat-translations', d.total_transcriptions);
        set('stat-bible-refs',   d.total_bible_refs);

        const dbEl = document.getElementById('stat-db');
        if (dbEl) {
            if (d.db && d.db.enabled) {
                dbEl.className = 'pf-v6-c-label pf-m-green';
                dbEl.innerHTML = `<span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">${d.db.count} rows</span></span>`;
            } else {
                dbEl.className = 'pf-v6-c-label';
                dbEl.innerHTML = `<span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">Disabled</span></span>`;
            }
        }
    } catch (err) {
        console.debug('Analytics fetch error:', err);
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/* ===================================
   TTS Cache Management
   =================================== */

async function refreshTTSCacheStats() {
    try {
        // Use session-based authentication (credentials: 'include' sends session cookie)
        const response = await fetch('/api/tts/cache-stats', {
            credentials: 'include',  // Send session cookie automatically
            headers: {
                'Accept': 'application/json'
            }
        });
        
        const cacheItemsEl = document.getElementById('cache-items');
        const cacheMemoryEl = document.getElementById('cache-memory');
        
        // Handle authentication errors
        if (response.status === 401) {
            console.error('Authentication failed for TTS cache stats');
            cacheItemsEl.textContent = 'Not authenticated';
            cacheMemoryEl.textContent = 'Not authenticated';
            return;
        }
        
        if (response.status === 403) {
            console.error('Access denied for TTS cache stats');
            cacheItemsEl.textContent = 'Access denied';
            cacheMemoryEl.textContent = 'Access denied';
            return;
        }
        
        if (!response.ok) {
            console.error(`Failed to fetch TTS cache stats: HTTP ${response.status}`);
            cacheItemsEl.textContent = 'Error';
            cacheMemoryEl.textContent = `HTTP ${response.status}`;
            return;
        }
        
        // Check if response is actually JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const bodyText = await response.text();
            console.error('Backend returned non-JSON response:', bodyText.substring(0, 200));
            cacheItemsEl.textContent = 'Server Error';
            cacheMemoryEl.textContent = 'Invalid response from server';
            console.warn('Tip: Check if Cloudflare Tunnel is properly configured. Ensure admin server can reach user server via localhost.');
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Update the values
            cacheItemsEl.textContent = 
                `${data.cache_items}/${data.max_cache_items}`;
            cacheMemoryEl.textContent = 
                `${data.cache_size_mb.toFixed(2)}MB/${data.max_cache_size_mb}MB`;
            console.log('TTS Cache Stats:', data);
        } else {
            const errorMsg = data.error || 'Unknown error';
            console.error('Backend error:', errorMsg);
            cacheItemsEl.textContent = 'Error';
            cacheMemoryEl.textContent = `${errorMsg}`;
            console.warn('Tip: Check admin server logs for details about the TTS cache error.');
        }
    } catch (error) {
        console.error('Network error refreshing TTS cache stats:', error);
        document.getElementById('cache-items').textContent = 'Error';
        document.getElementById('cache-memory').textContent = (error.message || 'Network error');
        console.warn('Tip: Check if the admin panel is accessible and the backend is running.');
    }
}

async function clearTTSCache() {
    if (!confirm('Are you sure you want to clear all TTS audio cache? This action cannot be undone.')) {
        return;
    }
    
    try {
        // Use session-based authentication (credentials: 'include' sends session cookie)
        const response = await fetch('/api/tts/cache-clear', {
            method: 'POST',
            credentials: 'include',  // Send session cookie automatically
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            }
        });
        
        // Handle authentication errors
        if (response.status === 401) {
            console.error('Authentication failed for TTS cache clear');
            showToast('Session expired, please login again', 'danger');
            return;
        }
        
        if (response.status === 403) {
            console.error('Access denied for TTS cache clear');
            showToast('Admin access required to clear cache', 'danger');
            return;
        }
        
        if (!response.ok) {
            console.error(`Failed to clear TTS cache: HTTP ${response.status}`);
            showToast(`Failed to clear TTS cache (HTTP ${response.status}) — Check browser console and server logs for details.`, 'danger');
            return;
        }
        
        // Check if response is actually JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const bodyText = await response.text();
            console.error('Backend returned non-JSON response:', bodyText.substring(0, 200));
            showToast('Invalid response from server. Check browser console for details.', 'danger');
            console.warn('Tip: Check if Cloudflare Tunnel is properly configured. Ensure admin server can reach user server via localhost.');
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`TTS Cache Cleared! — Cleared: ${data.cleared_items} items Freed: ${data.freed_mb.toFixed(2)}MB`, 'success');
            console.log('TTS Cache cleared:', data);
            // Refresh stats after clearing
            setTimeout(() => refreshTTSCacheStats(), 500);
        } else {
            const errorMsg = data.error || 'Failed to clear cache';
            console.error('Backend error:', errorMsg);
            showToast(`${errorMsg} — Check admin server logs for details.`, 'danger');
        }
    } catch (error) {
        console.error('Network error clearing TTS cache:', error);
        showToast(`Error: ${error.message} — Check if the admin panel is accessible and the backend is running.`, 'danger');
    }
}

console.log('EzySpeechTranslate Admin Panel Ready');
console.log('Keyboard Shortcuts:');
console.log('   Ctrl+R: Toggle recording');
console.log('   Ctrl+S: Save correction');
console.log('   Escape: Cancel selection');

// ── Bible Source Translation (admin) ─────────────────────────────────────────

/**
 * Load available translations from PrayerPulse via the user server proxy,
 * and populate the source translation selector with the current saved value.
 */
async function loadBibleSourceTranslation() {
    const sel = document.getElementById('adminBibleSourceSelect');
    const status = document.getElementById('adminBibleSaveStatus');
    if (!sel) return;

    try {
        // Fetch language list (proxied via user server)
        const langResp = await fetch(`${SERVER_URL}/api/bible/languages`);
        if (!langResp.ok) {
            sel.innerHTML = '<option value="">Bible detection not enabled</option>';
            return;
        }
        const langData = await langResp.json();

        // Fetch current saved value
        let currentSrc = 'KJV';
        try {
            const srcResp = await fetch(`${SERVER_URL}/api/bible/source-translation`);
            if (srcResp.ok) {
                const d = await srcResp.json();
                currentSrc = d.source_translation || 'KJV';
            }
        } catch (e) { /* use default */ }

        sel.innerHTML = '';
        langData.forEach(group => {
            const og = document.createElement('optgroup');
            og.label = group.language;
            (group.translations || []).forEach(t => {
                const o = document.createElement('option');
                o.value = t.short_name;
                o.textContent = `${t.short_name} — ${t.full_name}`;
                og.appendChild(o);
            });
            sel.appendChild(og);
        });

        sel.value = currentSrc;
        if (status) status.textContent = `Current: ${currentSrc}`;
    } catch (e) {
        if (sel) sel.innerHTML = '<option value="">Error loading translations</option>';
        console.warn('loadBibleSourceTranslation failed:', e);
    }
}

/**
 * Save the selected source translation to the user server (requires admin JWT).
 */
async function saveBibleSourceTranslation() {
    const sel = document.getElementById('adminBibleSourceSelect');
    const status = document.getElementById('adminBibleSaveStatus');
    if (!sel || !sel.value) return;

    const token = localStorage.getItem('adminToken') || sessionStorage.getItem('adminToken') || '';
    if (!token) {
        if (status) status.textContent = 'Not authenticated';
        return;
    }

    try {
        const resp = await fetch(`${SERVER_URL}/api/bible/source-translation`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
            },
            body: JSON.stringify({ source_translation: sel.value }),
        });
        const data = await resp.json();
        if (resp.ok && data.updated) {
            if (status) status.textContent = `Saved: ${sel.value}`;
            showToast(`Bible source set to ${sel.value}`, 'success');
        } else {
            if (status) status.textContent = `${data.error || 'Failed'}`;
        }
    } catch (e) {
        if (status) status.textContent = 'Network error';
        console.warn('saveBibleSourceTranslation failed:', e);
    }
}

// Load Bible source translation after the admin panel initialises
// (SERVER_URL is set by initAdminPanel → we wait for DOMContentLoaded +
//  a short delay to ensure the server URL is resolved)
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => loadBibleSourceTranslation(), 1500);
});

// ─── QR Code Generator ────────────────────────────────────────────────────────
let _qrInstance = null;

function generateQR() {
    const lang = document.getElementById('qrLangSelect').value;
    const roomSel = document.getElementById('qrRoomSelect');
    const roomChoice = roomSel ? roomSel.value : '';
    const effectiveRoom = roomChoice || (window.CURRENT_ROOM_ID || 'main');
    const base = (typeof SERVER_URL !== 'undefined' && SERVER_URL)
        ? SERVER_URL
        : `${window.location.protocol}//${window.location.hostname}:1915`;
    const params = new URLSearchParams();
    if (effectiveRoom && effectiveRoom !== 'main') params.set('room', effectiveRoom);
    if (lang) params.set('lang', lang);
    const qs = params.toString();
    const url = qs ? `${base}/?${qs}` : base + '/';

    const container = document.getElementById('qrCanvas');
    container.innerHTML = '';  // clear previous

    _qrInstance = new QRCode(container, {
        text: url,
        width: 220,
        height: 220,
        colorDark: '#000000',
        colorLight: '#ffffff',
        correctLevel: QRCode.CorrectLevel.M
    });

    document.getElementById('qrUrlLabel').textContent = url;
    document.getElementById('qrOutput').style.display = 'block';
}

function downloadQR() {
    const container = document.getElementById('qrCanvas');
    const img = container.querySelector('img');
    const canvas = container.querySelector('canvas');

    let dataUrl;
    if (canvas) {
        dataUrl = canvas.toDataURL('image/png');
    } else if (img) {
        // qrcodejs may render as <img> in some browsers — convert via canvas
        const c = document.createElement('canvas');
        c.width = img.naturalWidth || 220;
        c.height = img.naturalHeight || 220;
        c.getContext('2d').drawImage(img, 0, 0);
        dataUrl = c.toDataURL('image/png');
    } else {
        return;
    }

    const lang = document.getElementById('qrLangSelect').value || 'default';
    const roomSel = document.getElementById('qrRoomSelect');
    const room = (roomSel && roomSel.value) || (window.CURRENT_ROOM_ID || 'main');
    const a = document.createElement('a');
    a.href = dataUrl;
    a.download = `audience-qr-${room}-${lang}.png`;
    a.click();
}

// Populate the QR room dropdown from /api/rooms
async function refreshQrRoomDropdown() {
    const sel = document.getElementById('qrRoomSelect');
    if (!sel) return;
    try {
        const data = await _adminFetch('/api/rooms');
        const rooms = data.rooms || [];
        // Preserve selection
        const prev = sel.value;
        sel.innerHTML = '';
        const auto = document.createElement('option');
        auto.value = '';
        auto.textContent = '— Auto (current room: ' + (window.CURRENT_ROOM_ID || 'main') + ') —';
        sel.appendChild(auto);
        rooms.forEach(r => {
            const opt = document.createElement('option');
            opt.value = r.room_id;
            opt.textContent = (r.display_name || r.room_id) + ' (' + r.room_id + ')';
            sel.appendChild(opt);
        });
        sel.value = prev;
    } catch (e) {
        console.warn('refreshQrRoomDropdown failed:', e);
    }
}
window.refreshQrRoomDropdown = refreshQrRoomDropdown;
// Refresh whenever the user opens the QR section (cheap; user-initiated)
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => { if (typeof refreshQrRoomDropdown === 'function') refreshQrRoomDropdown(); }, 1600);
});


// ═════════════════════════════════════════════════════════════════
// Multi-room & Glossary management
// ═════════════════════════════════════════════════════════════════

function updateRoomIndicator(roomId) {
    const el = document.getElementById('currentRoomLabel');
    if (el) el.textContent = roomId || 'main';
}

async function _adminFetch(url, opts = {}) {
    opts.headers = Object.assign(
        { 'Content-Type': 'application/json' },
        opts.headers || {},
        authToken ? { 'Authorization': 'Bearer ' + authToken } : {}
    );
    const resp = await fetch(url, opts);
    let data = {};
    try { data = await resp.json(); } catch (_) { /* noop */ }
    if (!resp.ok || data.success === false) {
        throw new Error(data.error || ('HTTP ' + resp.status));
    }
    return data;
}

async function loadRoomList() {
    try {
        const data = await _adminFetch('/api/rooms');
        return data.rooms || [];
    } catch (e) {
        console.warn('loadRoomList failed:', e);
        return [];
    }
}

async function createRoom() {
    const rid = (prompt('Room ID (letters, digits, _ or -):') || '').trim();
    if (!rid) return;
    if (!/^[A-Za-z0-9][A-Za-z0-9_\-]{0,63}$/.test(rid)) {
        showToast('Invalid room ID', 'danger');
        return;
    }
    const name = (prompt('Display name:', rid) || rid).trim();
    try {
        await _adminFetch('/api/rooms', {
            method: 'POST',
            body: JSON.stringify({ room_id: rid, display_name: name })
        });
        showToast('Room created: ' + rid, 'success');
        await refreshRoomDropdown();
        if (typeof refreshQrRoomDropdown === 'function') await refreshQrRoomDropdown();
    } catch (e) {
        showToast('Create failed: ' + e.message, 'danger');
    }
}

async function switchRoom(targetRoom) {
    if (!targetRoom) return;
    if (!socket || !socket.connected) {
        showToast('Not connected', 'warning');
        return;
    }
    socket.emit('admin_switch_room', { room: targetRoom });
}

async function deleteRoom(roomId) {
    if (!roomId || roomId === 'main') {
        showToast('Cannot delete default room', 'warning');
        return;
    }
    if (!confirm('Delete room "' + roomId + '"? This is a soft delete; messages remain in DB.')) return;
    try {
        await _adminFetch('/api/rooms/' + encodeURIComponent(roomId), { method: 'DELETE' });
        showToast('Room deleted', 'success');
        await refreshRoomDropdown();
        if (typeof refreshQrRoomDropdown === 'function') await refreshQrRoomDropdown();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'danger');
    }
}

async function refreshRoomDropdown() {
    const sel = document.getElementById('roomSelect');
    if (!sel) return;
    const rooms = await loadRoomList();
    sel.innerHTML = '';
    rooms.forEach(r => {
        const opt = document.createElement('option');
        opt.value = r.room_id;
        opt.textContent = (r.display_name || r.room_id) + ' (' + (r.listeners || 0) + ')';
        if (r.room_id === window.CURRENT_ROOM_ID) opt.selected = true;
        sel.appendChild(opt);
    });
}

// ── Glossary CRUD ────────────────────────────────────────────────
async function loadGlossary() {
    const roomParam = window.CURRENT_ROOM_ID && window.CURRENT_ROOM_ID !== 'main'
        ? '?room=' + encodeURIComponent(window.CURRENT_ROOM_ID)
        : '';
    try {
        const data = await _adminFetch('/api/glossary' + roomParam);
        return data.entries || [];
    } catch (e) {
        console.warn('loadGlossary failed:', e);
        return [];
    }
}

async function renderGlossaryTable() {
    const tbody = document.getElementById('glossaryTableBody');
    if (!tbody) return;
    const entries = await loadGlossary();
    tbody.innerHTML = '';
    if (!entries.length) {
        tbody.innerHTML = '<tr class="pf-v6-c-table__tr"><td class="pf-v6-c-table__td" colspan="6">No glossary entries</td></tr>';
        return;
    }
    entries.forEach(e => {
        // PatternFly styles rows and cells through :where(.pf-v6-c-table__tr),
        // so a bare <tr> built here would get no styling at all.
        const tr = document.createElement('tr');
        tr.className = 'pf-v6-c-table__tr';
        const scope = e.room_id ? e.room_id : '(global)';
        const flag = (name, colour) =>
            `<span class="pf-v6-c-label pf-m-${colour} pf-m-compact"><span class="pf-v6-c-label__content"><span class="pf-v6-c-label__text">${name}</span></span></span>`;
        tr.innerHTML = `
            <td class="pf-v6-c-table__td" data-label="Scope">${escapeHTML(scope)}</td>
            <td class="pf-v6-c-table__td" data-label="Source">${escapeHTML(e.source_term)}</td>
            <td class="pf-v6-c-table__td" data-label="Lang">${escapeHTML(e.target_lang)}</td>
            <td class="pf-v6-c-table__td" data-label="Translation">${escapeHTML(e.translation)}</td>
            <td class="pf-v6-c-table__td" data-label="Flags">${e.case_sensitive ? flag('Case sensitive', 'blue') : ''} ${e.enabled ? '' : flag('Off', 'grey')}</td>
            <td class="pf-v6-c-table__td pf-v6-c-table__action">
                <button class="pf-v6-c-button pf-m-plain" type="button" aria-label="Remove entry" data-id="${Number(e.id)}" onclick="removeGlossaryEntry(${Number(e.id)})">&times;</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function escapeHTML(s) {
    return String(s == null ? '' : s)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

async function addGlossaryEntry() {
    const src = (document.getElementById('glossarySource').value || '').trim();
    const lang = (document.getElementById('glossaryLang').value || '').trim();
    const tgt = (document.getElementById('glossaryTranslation').value || '').trim();
    const caseSensitive = document.getElementById('glossaryCaseSensitive').checked;
    const scope = document.getElementById('glossaryScope').value;  // '' = global, else room id
    if (!src || !lang || !tgt) {
        showToast('All fields required', 'warning');
        return;
    }
    try {
        await _adminFetch('/api/glossary', {
            method: 'POST',
            body: JSON.stringify({
                source_term: src, target_lang: lang, translation: tgt,
                case_sensitive: caseSensitive,
                room: scope || null,
            })
        });
        document.getElementById('glossarySource').value = '';
        document.getElementById('glossaryTranslation').value = '';
        showToast('Glossary entry added', 'success');
        await renderGlossaryTable();
    } catch (e) {
        showToast('Add failed: ' + e.message, 'danger');
    }
}

async function removeGlossaryEntry(id) {
    if (!confirm('Delete glossary entry?')) return;
    try {
        await _adminFetch('/api/glossary/' + id, { method: 'DELETE' });
        showToast('Deleted', 'success');
        await renderGlossaryTable();
    } catch (e) {
        showToast('Delete failed: ' + e.message, 'danger');
    }
}

// Expose handlers for inline onclick attributes
window.createRoom = createRoom;
window.deleteRoom = deleteRoom;
window.switchRoom = switchRoom;
window.refreshRoomDropdown = refreshRoomDropdown;
window.renderGlossaryTable = renderGlossaryTable;
window.addGlossaryEntry = addGlossaryEntry;
window.removeGlossaryEntry = removeGlossaryEntry;

// ──────────────────────────────────────────
// Recording lock (per-room) + Config editor
// ──────────────────────────────────────────

// Browser-side SHA-256 with SubtleCrypto + pure-JS fallback
async function _adminSha256Hex(str) {
    try {
        if (window.crypto && window.crypto.subtle) {
            const buf = new TextEncoder().encode(str);
            const hashBuf = await window.crypto.subtle.digest('SHA-256', buf);
            return Array.from(new Uint8Array(hashBuf))
                .map(b => b.toString(16).padStart(2, '0')).join('');
        }
    } catch (_) { /* fall through */ }
    // Pure-JS fallback
    function rr(n, x) { return (x >>> n) | (x << (32 - n)); }
    const K = [0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
        0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
        0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
        0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
        0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
        0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
        0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
        0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
    let H = [0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19];
    const bytes = new TextEncoder().encode(str);
    const len = bytes.length;
    const blocks = Math.ceil((len + 9) / 64);
    const padded = new Uint8Array(blocks * 64);
    padded.set(bytes);
    padded[len] = 0x80;
    const dv = new DataView(padded.buffer);
    dv.setUint32(padded.length - 4, (len * 8) & 0xffffffff, false);
    for (let i = 0; i < blocks; i++) {
        const W = new Array(64);
        for (let j = 0; j < 16; j++) W[j] = dv.getUint32(i * 64 + j * 4, false);
        for (let j = 16; j < 64; j++) {
            const s0 = rr(7,W[j-15]) ^ rr(18,W[j-15]) ^ (W[j-15]>>>3);
            const s1 = rr(17,W[j-2])  ^ rr(19,W[j-2])  ^ (W[j-2]>>>10);
            W[j] = (W[j-16] + s0 + W[j-7] + s1) >>> 0;
        }
        let [a,b,c,d,e,f,g,h] = H;
        for (let j = 0; j < 64; j++) {
            const S1 = rr(6,e)^rr(11,e)^rr(25,e);
            const ch = (e&f)^(~e&g);
            const t1 = (h+S1+ch+K[j]+W[j]) >>> 0;
            const S0 = rr(2,a)^rr(13,a)^rr(22,a);
            const maj = (a&b)^(a&c)^(b&c);
            const t2 = (S0+maj) >>> 0;
            h=g; g=f; f=e; e=(d+t1)>>>0; d=c; c=b; b=a; a=(t1+t2)>>>0;
        }
        H = H.map((v,idx)=>([a,b,c,d,e,f,g,h][idx]+v)>>>0);
    }
    return H.map(v => v.toString(16).padStart(8,'0')).join('');
}

// Returns the current room id (matches multi-room module helper).
function _currentRoomId() {
    return (typeof window !== 'undefined' && window.CURRENT_ROOM_ID) || 'main';
}

// Raw fetch variant — returns {ok, status, data} instead of throwing on 4xx.
async function _adminFetchRaw(url, opts = {}) {
    opts.headers = Object.assign(
        { 'Content-Type': 'application/json' },
        opts.headers || {},
        (typeof authToken !== 'undefined' && authToken) ? { 'Authorization': 'Bearer ' + authToken } : {}
    );
    const resp = await fetch(url, opts);
    let data = {};
    try { data = await resp.json(); } catch (_) { /* noop */ }
    return { ok: resp.ok, status: resp.status, data };
}

// Try to acquire the recording lock. If locked by another admin, open the
// takeover modal so the user can enter a password.
async function _tryAcquireRecording(force, passwordHash) {
    const body = { room: _currentRoomId() };
    if (force) body.force = true;
    if (passwordHash) body.password_hash = passwordHash;
    if (typeof socket !== 'undefined' && socket && socket.id) body.sid = socket.id;
    return await _adminFetchRaw('/api/recording/acquire', {
        method: 'POST',
        body: JSON.stringify(body),
    });
}

function _openRecordingLockModal(ownerName) {
    const modal = document.getElementById('recordingLockModal');
    if (!modal) return;
    const lbl = document.getElementById('recordingLockOwner');
    if (lbl) lbl.textContent = ownerName || 'Another admin';
    const pw = document.getElementById('recordingLockPassword');
    if (pw) { pw.value = ''; setTimeout(() => pw.focus(), 50); }
    modal.classList.add('modal-overlay--open');
}

async function confirmForceRecording() {
    const pw = document.getElementById('recordingLockPassword');
    const pwd = pw ? pw.value : '';
    if (!pwd) {
        if (typeof showToast === 'function') showToast('Enter admin password', 'warning');
        return;
    }
    let hash;
    try { hash = await _adminSha256Hex(pwd); }
    catch (e) {
        if (typeof showToast === 'function') showToast('Hash failed: ' + e.message, 'danger');
        return;
    }
    const res = await _tryAcquireRecording(true, hash);
    if (res.ok && res.data.success) {
        window.closeRecordingLock && window.closeRecordingLock();
        if (typeof showToast === 'function') showToast('Took over recording. Starting…', 'success');
        // Resume normal recording start
        await _startRecognitionAfterLock();
    } else if (res.status === 401) {
        if (typeof showToast === 'function') showToast('Wrong password', 'danger');
    } else {
        if (typeof showToast === 'function')
            showToast('Force-stop failed: ' + (res.data.error || res.status), 'danger');
    }
}
window.confirmForceRecording = confirmForceRecording;

// Actually start the SpeechRecognition session (after lock acquired).
async function _startRecognitionAfterLock() {
    if (typeof recognition === 'undefined' || !recognition) return;
    try {
        isRecording = true;
        if (typeof recognitionAttempts !== 'undefined') recognitionAttempts = 0;
        finalTranscript = '';
        recognition.lang = recognitionLanguage;
        updateRecordButton();
        recognition.start();
        if (typeof lastSpeechTimestamp !== 'undefined') lastSpeechTimestamp = Date.now();
        console.log('Recognition started (lock acquired)');
    } catch (error) {
        console.error('Start failed:', error);
        isRecording = false;
        updateRecordButton();
        if (typeof showToast === 'function')
            showToast('Failed to start recording: ' + error.message, 'danger');
        // Release the server-side lock we just acquired
        _releaseRecording();
    }
}

async function _releaseRecording() {
    try {
        await _adminFetchRaw('/api/recording/release', {
            method: 'POST',
            body: JSON.stringify({ room: _currentRoomId() }),
        });
    } catch (_) { /* best-effort */ }
}

// Override toggleRecording with a lock-aware wrapper.
const _origToggleRecording = (typeof toggleRecording !== 'undefined') ? toggleRecording : null;
const _origStopRecording = (typeof stopRecording !== 'undefined') ? stopRecording : null;

window.toggleRecording = async function () {
    if (typeof recognition === 'undefined' || !recognition) {
        if (typeof showToast === 'function')
            showToast('Speech Recognition not initialized. Please refresh.', 'warning');
        return;
    }
    if (isRecording) {
        // Stop path — release lock first
        if (_origStopRecording) _origStopRecording();
        await _releaseRecording();
        return;
    }
    // Start path — try to acquire lock
    const res = await _tryAcquireRecording(false);
    if (res.ok && res.data.success) {
        await _startRecognitionAfterLock();
        return;
    }
    if (res.status === 423) {
        const ownerName = (res.data.owner && res.data.owner.username) || 'Another admin';
        _openRecordingLockModal(ownerName);
        return;
    }
    if (typeof showToast === 'function')
        showToast('Could not start recording: ' + (res.data.error || res.status), 'danger');
};

// Also wrap stopRecording so manual stop calls release the lock.
window.stopRecording = function () {
    if (_origStopRecording) _origStopRecording();
    _releaseRecording();
};

// Handle force-stopped notification (admin was kicked by another admin).
if (typeof socket !== 'undefined' && socket && socket.on) {
    socket.on('recording_force_stopped', function (data) {
        if (!data || data.room_id !== _currentRoomId()) return;
        if (isRecording && _origStopRecording) _origStopRecording();
        if (typeof showToast === 'function')
            showToast('Your recording was stopped by ' + (data.by || 'another admin'), 'warning');
    });
}

// ── Config editor ────────────────────────────────────────────────────
function _jwtUsername() {
    try {
        const payload = JSON.parse(atob(
            authToken.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
        ));
        return payload.username || 'admin';
    } catch (_) { return 'admin'; }
}

async function confirmConfigPassword() {
    const inp = document.getElementById('configPasswordInput');
    const pwd = inp ? inp.value : '';
    if (!pwd) {
        if (typeof showToast === 'function') showToast('Enter password', 'warning');
        return;
    }
    let hash;
    try { hash = await _adminSha256Hex(pwd); }
    catch (e) {
        if (typeof showToast === 'function') showToast('Hash failed: ' + e.message, 'danger');
        return;
    }
    try {
        const resp = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: _jwtUsername(), password_hash: hash }),
        });
        if (resp.ok) {
            window.closeConfigPasswordGate && window.closeConfigPasswordGate();
            window.location.href = '/config';
        } else {
            if (typeof showToast === 'function') showToast('Wrong password', 'danger');
            if (inp) { inp.value = ''; inp.focus(); }
        }
    } catch (e) {
        if (typeof showToast === 'function') showToast('Request failed: ' + e.message, 'danger');
    }
}
window.confirmConfigPassword = confirmConfigPassword;