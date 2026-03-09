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
});

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
        if (selectedItem) {
            cancelCorrection();
        }
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

    socket = io(SERVER_URL, {
        transports: ['websocket', 'polling'],
        reconnection: true,
        reconnectionAttempts: 5,
        reconnectionDelay: 1000
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
            alert('Session expired. Please login again.');
            localStorage.removeItem('authToken');
            window.location.href = '/login';
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
            alert('Session expired. Please login again.');
            localStorage.removeItem('authToken');
            window.location.href = '/login';
        }
    });

    socket.on('history', (history) => {
        translations = history;
        renderTranscriptions();
    });

    socket.on('new_translation', (data) => {
        console.log('📥 Received translation:', data);
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

async function loadAudioDevices() {
    const select = document.getElementById('deviceSelect');

    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        select.innerHTML = '<option>❌ Not supported</option>';
        alert('⚠️ Web Speech API not supported!\n\nPlease use Chrome or Edge.');
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
        alert('⚠️ Microphone access denied!\n\nPlease allow microphone access.');
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

        // Do not auto-send here — final results are sent from onresult.
        // Keep finalTranscript for any pending processing by onresult.

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
                alert('❌ Cannot access microphone');
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
                alert('❌ Microphone permission denied');
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
                finalTranscript += transcript + ' ';
                console.log('✅ Final:', transcript, 'Confidence:', confidence);

                sendTranscription(finalTranscript.trim(), confidence);
                finalTranscript = '';

                updateInterimDisplay('✓ Sent', true);
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
            updateInterimDisplay(interimTranscript, true);
            console.log('💭 Interim:', interimTranscript.substring(0, 50) + '...');
        }
    };
}

function updateInterimDisplay(text, active) {
    const display = document.getElementById('interimDisplay');
    const textEl = document.getElementById('interimText');

    textEl.textContent = text;
    display.className = active ? 'interim-display active' : 'interim-display inactive';
}

function sendTranscription(text, confidence) {
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
    console.log(`📤 SENDING TO SERVER: "${sanitizedText}" (confidence: ${confidence})`);

    socket.emit('new_transcription', {
        text: sanitizedText,
        language: recognitionLanguage.split('-')[0],
        timestamp: new Date().toISOString(),
        confidence: confidence
    });

    updateInterimDisplay('✓ Sent: ' + sanitizedText.substring(0, 50) + '...', true);
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
        alert('Speech Recognition not initialized. Please refresh.');
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
            alert('Failed to start recording: ' + error.message);
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
        alert('⚠️ Cannot change language while recording. Please stop recording first.');
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
                ${item.confidence ? `<span class="card-confidence">confidence: ${Math.round(item.confidence * 100)}%</span>` : ''}
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
    const text = prompt('Enter transcription text:');
    if (!text) return;

    const validation = validateText(text);
    if (!validation.valid) {
        alert('❌ ' + validation.error);
        return;
    }

    socket.emit('new_transcription', {
        text: validation.text,
        language: 'manual'
    });
}

function editSelected() {
    if (!selectedItem) {
        alert('Please select an item to edit');
        return;
    }
    document.getElementById('correctedText').focus();
}

function deleteSelected() {
    const checkboxes = document.querySelectorAll('.card-checkbox:checked');
    if (checkboxes.length === 0) {
        alert('Please select items to delete');
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
        alert('No item selected');
        return;
    }

    const corrected = document.getElementById('correctedText').value.trim();

    const validation = validateText(corrected);
    if (!validation.valid) {
        alert('❌ ' + validation.error);
        return;
    }

    socket.emit('correct_translation', {
        id: selectedItem.id,
        corrected_text: validation.text
    });

    alert('✅ Correction saved and broadcasted to all clients!');

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
        alert('No data to export');
        return;
    }

    const format = prompt('Export format:\n\n• txt - Plain text\n• json - JSON data\n• srt - Subtitle format\n\nEnter format:', 'txt');
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

console.log('✅ EzySpeechTranslate Admin Panel Ready');
console.log('📝 Keyboard Shortcuts:');
console.log('   Ctrl+R: Toggle recording');
console.log('   Ctrl+S: Save correction');
console.log('   Escape: Cancel selection');