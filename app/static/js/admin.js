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
function showToast(message, type, duration) {
    type = type || 'info';
    duration = duration || 3000;
    const container = document.getElementById('toastContainer');
    if (!container) { console.log('[toast]', type, message); return; }
    while (container.children.length >= ADMIN_MAX_TOASTS) container.firstChild.remove();
    const toast = document.createElement('div');
    toast.className = 'toast ' + type;
    toast.setAttribute('role', type === 'danger' ? 'alert' : 'status');
    toast.textContent = message;
    container.appendChild(toast);
    // eslint-disable-next-line no-unused-expressions
    toast.offsetHeight;
    toast.classList.add('show');
    setTimeout(function () {
        toast.classList.remove('show');
        setTimeout(function () { toast.remove(); }, 300);
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
    localStorage.setItem('theme', newTheme);

    updateThemeUI(newTheme);
}

function updateThemeUI(theme) {
    const icon = document.getElementById('themeIcon');
    const text = document.getElementById('themeText');

    if (theme === 'dark') {
        if (icon) icon.textContent = '☀️';
        if (text) text.textContent = t('lightMode', 'Light Mode');
    } else {
        if (icon) icon.textContent = '🌙';
        if (text) text.textContent = t('darkMode', 'Dark Mode');
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
    console.log('🔌 Connecting to WebSocket:', SERVER_URL);
    console.log('🔑 Using token:', authToken ? 'Yes' : 'No');
    
    // Admin should use separate persistent client ID (distinct from user client)
    const adminClientIdKey = '_admin_client_id';
    let clientId = localStorage.getItem(adminClientIdKey);
    if (!clientId) {
        clientId = 'admin_' + Math.random().toString(36).substring(2, 15) + '_' + Date.now();
        localStorage.setItem(adminClientIdKey, clientId);
    }

    socket = io(SERVER_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000,
        query: {
            client_id: clientId,  // Send persistent client ID to server
            type: 'admin'  // Identify as admin client
        }
    });

    socket.on('connect', () => {
        console.log('✅ WebSocket connected - SID:', socket.id);
        updateStatus(true);

        if (authToken) {
            console.log('📤 Sending admin_connect...');
            socket.emit('admin_connect', {token: authToken});
        }
    });

    socket.on('admin_connected', (response) => {
        console.log('✅ Admin connected response:', response);
        if (!response.success) {
            console.error('❌ Admin connection rejected:', response.error);
            showToast('Session expired. Please login again.', 'danger');
            localStorage.removeItem('authToken');
            window.location.href = '/login';
        } else {
            // Fetch history via HTTP API to ensure we get the latest data
            fetchTranslationHistory();
        }
    });

    socket.on('disconnect', () => {
        console.log('⚠️ Disconnected');
        updateStatus(false);
    });

    socket.on('connect_error', (error) => {
        console.error('❌ Connection error:', error);
        updateStatus(false);
    });

    socket.on('error', (error) => {
        console.error('❌ Socket error:', error);

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
        console.log('📥 Received translation:', data);
        const exists = translations.some(t => t.id === data.id);
        if (!exists) {
            translations.push(data);
            renderTranscriptions();
        }
    });

    // Confirmation that our transcription was stored with its server-assigned ID
    socket.on('transcription_confirmed', (data) => {
        console.log('✅ Transcription confirmed, id:', data.id);
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
        badge.className = 'connection-badge online';
        badge.querySelector('span:last-child').textContent = 'User Server is Online';
    } else {
        badge.className = 'connection-badge offline';
        badge.querySelector('span:last-child').textContent = 'User Server is Offline';
    }
}

async function fetchTranslationHistory() {
    try {
        console.log('📥 Fetching translation history via HTTP...');
        const response = await fetch(`${SERVER_URL}/api/history`, {
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
            console.log(`✅ Loaded ${data.count} transcriptions from server`);
            renderTranscriptions();
        }
    } catch (error) {
        console.error('Failed to fetch translation history:', error);
    }
}

async function loadAudioDevices() {
    const select = document.getElementById('deviceSelect');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        select.innerHTML = '<option>❌ Not supported</option>';
        showToast('⚠️ Web Speech API not supported! — Please use Chrome or Edge.', 'warning');
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

        console.log(`✅ Speech Recognition initialized`);
        setupRecognitionHandlers();

    } catch (error) {
        console.error('Microphone access error:', error);
        select.innerHTML = '<option>❌ Access denied</option>';
        showToast('⚠️ Microphone access denied! — Please allow microphone access.', 'danger');
    }
}

function setupRecognitionHandlers() {
    if (!recognition) return;

    recognition.onstart = () => {
        console.log('🎤 Speech recognition started');
        isRecording = true;
        updateRecordButton();
        updateInterimDisplay('🎤 Listening...', true);
        document.getElementById('autoRestartBadge').style.display = 'flex';
    };

    recognition.onend = () => {
        console.log('🛑 Speech recognition ended');

        if (isRecording && autoRestartEnabled) {
            console.log('🔄 Auto-restarting in 300ms...');
            clearTimeout(restartTimeout);
            restartTimeout = setTimeout(() => {
                if (isRecording) {
                    try {
                        recognition.start();
                        console.log('✅ Recognition restarted');
                    } catch (e) {
                        console.error('❌ Restart failed:', e);
                        setTimeout(() => {
                            if (isRecording) {
                                try {
                                    recognition.start();
                                } catch (err) {
                                    console.error('❌ Second restart failed:', err);
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
        console.error('❌ Recognition error:', event.error);

        switch (event.error) {
            case 'no-speech':
                console.log('⚠️ No speech detected - will auto-restart');
                updateInterimDisplay('⚠️ No speech detected...', true);
                break;

            case 'audio-capture':
                showToast('❌ Cannot access microphone', 'danger');
                isRecording = false;
                updateRecordButton();
                updateInterimDisplay('Error: No microphone', false);
                document.getElementById('autoRestartBadge').style.display = 'none';
                break;

            case 'network':
                console.error('❌ Network error - will retry');
                updateInterimDisplay('⚠️ Network error, retrying...', true);
                break;

            case 'not-allowed':
                showToast('❌ Microphone permission denied', 'danger');
                isRecording = false;
                updateRecordButton();
                updateInterimDisplay('Error: Permission denied', false);
                document.getElementById('autoRestartBadge').style.display = 'none';
                break;

            default:
                console.error('Unknown error:', event.error);
                updateInterimDisplay(`⚠️ Error: ${event.error}`, true);
        }
    };

    recognition.onresult = (event) => {
        let interimTranscript = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
            const transcript = event.results[i][0].transcript;
            const confidence = event.results[i][0].confidence;

            if (event.results[i].isFinal) {
                console.log(`📤 SENDING FINAL: "${transcript}"`);
                // Send final with same temp_id so user-side replaces the interim card
                sendTranscription(transcript, confidence, true);
                currentTempId = null;  // Reset for next utterance
                updateInterimDisplay('✓ Sent: ' + transcript.substring(0, 50) + '...', true);
                setTimeout(() => {
                    if (isRecording) {
                        updateInterimDisplay('🎤 Listening...', true);
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
        console.warn('⚠️ Cannot send - no text or no connection');
        return;
    }

    const validation = validateText(text);
    if (!validation.valid) {
        console.error('❌ Invalid input:', validation.error);
        updateInterimDisplay('⚠️ ' + validation.error, false);
        return;
    }

    const sanitizedText = validation.text;
    console.log(`📤 SENDING: "${sanitizedText}" (confidence: ${confidence}, final: ${isFinal})`);

    socket.emit('new_transcription', {
        text: sanitizedText,
        language: recognitionLanguage.split('-')[0],
        timestamp: new Date().toISOString(),
        confidence: confidence,
        is_final: isFinal,
        temp_id: currentTempId
    });

    if (isFinal) {
        updateInterimDisplay('✓ Sent: ' + sanitizedText.substring(0, 50) + '...', true);
    }
}

function updateRecordButton() {
    const btn = document.getElementById('recordBtn');
    const langSelect = document.getElementById('sourceLangSelect');

    const shared = window.sharedI18n || {};
    const lang = window._displayLanguage || localStorage.getItem('displayLanguage') || (navigator.language || 'en').split('-')[0];

    const span = btn.querySelector('[data-i18n]') || btn;

    if (isRecording) {
        const text = (shared[lang] && shared[lang]['stopRecording']) || '⏹️ Stop Recording';
        span.textContent = text;
        btn.className = 'pf-c-button pf-c-button--danger recording';
        langSelect.disabled = true;
    } else {
        const text = (shared[lang] && shared[lang]['startRecording']) || '🎙️ Start Recording';
        span.textContent = text;
        btn.className = 'pf-c-button pf-c-button--success';
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
            console.log('🎤 Recognition started');
        } catch (error) {
            console.error('❌ Start failed:', error);
            isRecording = false;
            updateRecordButton();
            showToast('Failed to start recording: ' + error.message, 'danger');
        }
    } else {
        stopRecording();
    }
}

function stopRecording() {
    console.log('⏹️ Stopping recording');
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
        showToast('⚠️ Cannot change language while recording. Please stop recording first.', 'danger');
        const select = document.getElementById('sourceLangSelect');
        select.value = recognitionLanguage;
        return;
    }

    const select = document.getElementById('sourceLangSelect');
    const oldLang = recognitionLanguage;
    recognitionLanguage = select.value;
    console.log(`🌍 Language: ${oldLang} → ${recognitionLanguage}`);
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
        list.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">💬</div>
                <div>${noTrans}</div>
                <small style="display: block; margin-top: 0.5rem; opacity: 0.7;">
                    ${startHelp}
                </small>
            </div>
        `;
        return;
    }

    // Display in reverse order (newest first)
    const reversed = [...translations].reverse();
    list.innerHTML = reversed.map((item, index) => `
        <div class="transcription-card ${selectedItem && selectedItem.id === item.id ? 'selected' : ''}"
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
            <div class="drag-handle"
                 onmousedown="event.stopPropagation()"
                 ontouchstart="event.stopPropagation()">⋮⋮</div>
            <input type="checkbox"
                   class="card-checkbox"
                   data-id="${item.id}"
                   ${selectedItem && selectedItem.id === item.id ? 'checked' : ''}
                   onclick="handleCheckboxClick(event, ${item.id})">
            <div class="card-content">
                <div class="card-header">
                    <span class="card-time">${item.timestamp}</span>
                    ${item.is_corrected ? `<span class="card-badge">${(shared && shared[lang] && shared[lang]['corrected']) || '✓ Corrected'}</span>` : ''}
                </div>
                <div class="card-text">${escapeHtml(item.corrected)}</div>
            </div>
        </div>
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
        title: '✏️ Add Transcription',
        label: 'Enter transcription text:',
        onConfirm: function (text) {
            if (!text) return;
            const validation = validateText(text);
            if (!validation.valid) {
                showToast('❌ ' + validation.error, 'danger');
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
        showToast('❌ ' + validation.error, 'danger');
        return;
    }

    socket.emit('correct_translation', {
        id: selectedItem.id,
        corrected_text: validation.text
    });

    showToast('✅ Correction saved and broadcasted to all clients!', 'success');

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
    if (!confirm('⚠️ Clear all transcriptions?\n\nThis cannot be undone.')) return;
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
        showToast('❌ Please select a JSON file', 'danger');
        return;
    }

    const reader = new FileReader();
    reader.onload = (e) => {
        try {
            const content = e.target.result;
            const data = JSON.parse(content);
            
            // Validate data structure
            if (!data.translations || !Array.isArray(data.translations)) {
                showToast('❌ Invalid JSON format. Expected {translations: []}', 'danger');
                return;
            }

            // Validate each translation object has required fields
            const requiredFields = ['id', 'original', 'corrected'];
            for (const item of data.translations) {
                for (const field of requiredFields) {
                    if (!(field in item)) {
                        showToast(`❌ Missing required field: ${field}`, 'danger');
                        return;
                    }
                }
            }

            importTranslations(data.translations);
        } catch (error) {
            showToast(`❌ Error parsing JSON: ${error.message}`, 'danger');
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
        `📥 Ready to import ${translationsToImport.length} translation(s).\n\n` +
        `This will add them to your transcriptions.\n\n` +
        `Continue?`
    );

    if (!confirmed) return;

    console.log(`📥 Importing ${translationsToImport.length} translations...`);

    // Show progress
    let imported = 0;
    let failed = 0;

    // Send each translation via socket
    for (const item of translationsToImport) {
        const validation = validateText(item.corrected);
        if (!validation.valid) {
            console.warn(`⚠️ Skipping invalid translation: ${item.corrected}`);
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

    showToast(`✅ Import completed! — ${imported} transcription(s) imported ${failed > 0 ? `${failed} skipped (validation failed)` : 'No errors'}`, 'danger');
    
    console.log(`✅ Import completed: ${imported}/${translationsToImport.length}`);
}

function startSystemMonitor() {
    updateSystemInfo();
    setInterval(updateSystemInfo, 2000);
}

async function updateSystemInfo() {
    try {
        const response = await fetch(`${SERVER_URL}/api/health`, {
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
                sysRecording.className = 'pf-v5-c-label pf-m-green';
                sysRecording.innerHTML = `<span class="pf-v5-c-label__content"><span class="pf-v5-c-label__icon">●</span><span class="pf-v5-c-label__text">${activeText}</span></span>`;
            } else {
                sysRecording.className = 'pf-v5-c-label pf-m-grey';
                sysRecording.innerHTML = `<span class="pf-v5-c-label__content"><span class="pf-v5-c-label__icon">○</span><span class="pf-v5-c-label__text">${stoppedText}</span></span>`;
            }
        }

        // Language label
        const sysLanguage = document.getElementById('sys-language');
        if (sysLanguage) {
            sysLanguage.innerHTML = `<span class="pf-v5-c-label__content"><span class="pf-v5-c-label__text pf-mono">${recognitionLanguage || 'en-US'}</span></span>`;
        }
    } catch (error) {
        console.error('Failed to fetch system info:', error);
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
            console.error('❌ Authentication failed for TTS cache stats');
            cacheItemsEl.textContent = '⚠️ Not authenticated';
            cacheMemoryEl.textContent = '⚠️ Not authenticated';
            return;
        }
        
        if (response.status === 403) {
            console.error('❌ Access denied for TTS cache stats');
            cacheItemsEl.textContent = '⚠️ Access denied';
            cacheMemoryEl.textContent = '⚠️ Access denied';
            return;
        }
        
        if (!response.ok) {
            console.error(`❌ Failed to fetch TTS cache stats: HTTP ${response.status}`);
            cacheItemsEl.textContent = '❌ Error';
            cacheMemoryEl.textContent = `❌ HTTP ${response.status}`;
            return;
        }
        
        // Check if response is actually JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const bodyText = await response.text();
            console.error('❌ Backend returned non-JSON response:', bodyText.substring(0, 200));
            cacheItemsEl.textContent = '❌ Server Error';
            cacheMemoryEl.textContent = '❌ Invalid response from server';
            console.warn('💡 Tip: Check if Cloudflare Tunnel is properly configured. Ensure admin server can reach user server via localhost.');
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            // Update the values
            cacheItemsEl.textContent = 
                `${data.cache_items}/${data.max_cache_items}`;
            cacheMemoryEl.textContent = 
                `${data.cache_size_mb.toFixed(2)}MB/${data.max_cache_size_mb}MB`;
            console.log('✅ TTS Cache Stats:', data);
        } else {
            const errorMsg = data.error || 'Unknown error';
            console.error('❌ Backend error:', errorMsg);
            cacheItemsEl.textContent = '❌ Error';
            cacheMemoryEl.textContent = `❌ ${errorMsg}`;
            console.warn('💡 Tip: Check admin server logs for details about the TTS cache error.');
        }
    } catch (error) {
        console.error('❌ Network error refreshing TTS cache stats:', error);
        document.getElementById('cache-items').textContent = '❌ Error';
        document.getElementById('cache-memory').textContent = '❌ ' + (error.message || 'Network error');
        console.warn('💡 Tip: Check if the admin panel is accessible and the backend is running.');
    }
}

async function clearTTSCache() {
    if (!confirm('⚠️ Are you sure you want to clear all TTS audio cache? This action cannot be undone.')) {
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
            console.error('❌ Authentication failed for TTS cache clear');
            showToast('❌ Session expired, please login again', 'danger');
            return;
        }
        
        if (response.status === 403) {
            console.error('❌ Access denied for TTS cache clear');
            showToast('❌ Admin access required to clear cache', 'danger');
            return;
        }
        
        if (!response.ok) {
            console.error(`❌ Failed to clear TTS cache: HTTP ${response.status}`);
            showToast(`❌ Failed to clear TTS cache (HTTP ${response.status}) — Check browser console and server logs for details.`, 'danger');
            return;
        }
        
        // Check if response is actually JSON (not HTML error page)
        const contentType = response.headers.get('content-type');
        if (!contentType || !contentType.includes('application/json')) {
            const bodyText = await response.text();
            console.error('❌ Backend returned non-JSON response:', bodyText.substring(0, 200));
            showToast('❌ Invalid response from server. Check browser console for details.', 'danger');
            console.warn('💡 Tip: Check if Cloudflare Tunnel is properly configured. Ensure admin server can reach user server via localhost.');
            return;
        }
        
        const data = await response.json();
        
        if (data.success) {
            showToast(`✅ TTS Cache Cleared! — Cleared: ${data.cleared_items} items Freed: ${data.freed_mb.toFixed(2)}MB`, 'success');
            console.log('✅ TTS Cache cleared:', data);
            // Refresh stats after clearing
            setTimeout(() => refreshTTSCacheStats(), 500);
        } else {
            const errorMsg = data.error || 'Failed to clear cache';
            console.error('❌ Backend error:', errorMsg);
            showToast(`❌ ${errorMsg} — Check admin server logs for details.`, 'danger');
        }
    } catch (error) {
        console.error('❌ Network error clearing TTS cache:', error);
        showToast(`❌ Error: ${error.message} — Check if the admin panel is accessible and the backend is running.`, 'danger');
    }
}

console.log('✅ EzySpeechTranslate Admin Panel Ready');
console.log('📝 Keyboard Shortcuts:');
console.log('   Ctrl+R: Toggle recording');
console.log('   Ctrl+S: Save correction');
console.log('   Escape: Cancel selection');