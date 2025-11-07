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
const MAX_SILENT_TIME = 30000; // 30 seconds
let lastSpeechTimestamp = Date.now();
let warmupTimeout = null;

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

function toggleLoginTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const newTheme = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);

    document.getElementById('loginThemeIcon').textContent = newTheme === 'dark' ? '☀️' : '🌙';
    document.getElementById('loginThemeText').textContent = newTheme === 'dark' ? 'Light Mode' : 'Dark Mode';
}

const storedTheme = localStorage.getItem('theme') || 'light';
document.documentElement.setAttribute('data-theme', storedTheme);

window.addEventListener('DOMContentLoaded', () => {
    updateThemeUI(storedTheme);

    if (storedTheme === 'dark') {
        const loginThemeIcon = document.getElementById('loginThemeIcon');
        const loginThemeText = document.getElementById('loginThemeText');
        if (loginThemeIcon) loginThemeIcon.textContent = '☀️';
        if (loginThemeText) loginThemeText.textContent = 'Light Mode';
    }
});

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        hideAbout();
        closeMobileMenu();
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

    if (e.key === 'Escape') {
        if (selectedItem) {
            cancelCorrection();
        }
    }
});

async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    const errorEl = document.getElementById('loginError');

    if (!username || !password) {
        errorEl.textContent = 'Please fill in all fields';
        errorEl.style.display = 'block';
        return;
    }

    try {
        const response = await fetch(`${SERVER_URL}/api/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username, password})
        });

        const data = await response.json();

        if (data.success && data.token) {
            authToken = data.token;
            localStorage.setItem('authToken', authToken);
            showMainApp();
            connectWebSocket();
        } else {
            errorEl.textContent = 'Invalid credentials';
            errorEl.style.display = 'block';
        }
    } catch (error) {
        errorEl.textContent = 'Connection failed. Is the server running?';
        errorEl.style.display = 'block';
        console.error('Login error:', error);
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
        location.reload();
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    document.getElementById('password').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') login();
    });

    try {
        const response = await fetch('/api/config');
        const config = await response.json();
        SERVER_URL = `${window.location.protocol}//${window.location.hostname}:${config.mainServerPort}`;
        console.log('Main server URL:', SERVER_URL);
    } catch (error) {
        console.error('Failed to load config:', error);
        SERVER_URL = `${window.location.protocol}//${window.location.hostname}:1915`;
    }

    const savedToken = localStorage.getItem('authToken');
    if (savedToken) {
        authToken = savedToken;
        showMainApp();
        connectWebSocket();
    }
});

function showMainApp() {
    document.getElementById('loginScreen').style.display = 'none';
    document.getElementById('mainApp').style.display = 'block';
    loadAudioDevices();
    startSystemMonitor();
}

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
        } else {
            console.warn('⚠️ No authToken available!');
        }
    });

    socket.on('admin_connected', (response) => {
        console.log('✅ Admin connected response:', response);
        if (!response.success) {
            console.error('❌ Admin connection rejected:', response.error);
            alert('Session expired. Please login again.');
            localStorage.removeItem('authToken');
            location.reload();
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
            location.reload();
        } else {
            alert('Socket error: ' + (error.message || JSON.stringify(error)));
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
}

function updateStatus(connected) {
    const badge = document.getElementById('statusBadge');
    if (connected) {
        badge.className = 'connection-badge online';
        badge.querySelector('span:last-child').textContent = 'User Server is Oline';
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

        select.innerHTML = audioInputs.length === 0
            ? '<option>🎤 System Default</option>'
            : '<option>🎤 System Default (Best Available)</option>';

        stream.getTracks().forEach(track => track.stop());

        console.log(`✅ Speech Recognition initialized`);
        setupRecognitionHandlers();

    } catch (error) {
        console.error('Microphone access error:', error);
        select.innerHTML = '<option>❌ Access denied</option>';
        alert('⚠️ Microphone access denied!\n\nPlease allow microphone access.');
    }
}

function warmupRecognition() {
    console.log('🎤 Warming up speech recognition...');
    updateInterimDisplay('🎤 Warming up... Please wait....', true);
    // Create a short-lived recognition instance for warmup
    const warmupRecognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    warmupRecognition.lang = recognitionLanguage;
    warmupRecognition.continuous = false;
    warmupRecognition.interimResults = false;
    
    warmupRecognition.onend = () => {
        console.log('✅ Warmup complete');
        startMainRecognition();
    };
    
    warmupRecognition.onerror = (event) => {
        console.warn('⚠️ Warmup error:', event.error);
        startMainRecognition();
    };
    
    try {
        warmupRecognition.start();
    } catch (error) {
        console.error('❌ Warmup failed:', error);
        startMainRecognition();
    }
}

function startMainRecognition() {
    if (!recognition) return;
    
    recognition.onresult = handleRecognitionResult;
    recognition.onerror = handleRecognitionError;
    recognition.onend = handleRecognitionEnd;
    
    try {
        recognition.start();
        lastSpeechTimestamp = Date.now();
        console.log('🎤 Main recognition started');
    } catch (error) {
        console.error('❌ Start failed:', error);
        handleRecognitionError({ error: 'start_failed' });
    }
}

function handleRecognitionResult(event) {
    let interimTranscript = '';
    
    for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        lastSpeechTimestamp = Date.now(); // Update timestamp on speech

        if (event.results[i].isFinal) {
            finalTranscript += transcript + ' ';
            console.log('✅ Final:', transcript);
            
            sendTranscription(finalTranscript.trim());
            finalTranscript = '';
            recognitionAttempts = 0; // Reset attempts on successful speech
            
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
}

function handleRecognitionError(event) {
    console.error('❌ Recognition error:', event.error);
    
    switch (event.error) {
        case 'no-speech':
            const silentTime = Date.now() - lastSpeechTimestamp;
            if (silentTime > MAX_SILENT_TIME) {
                console.log('⚠️ Long silence detected, restarting...');
                restartRecognition();
            } else {
                updateInterimDisplay('Waiting for speech...', true);
            }
            break;
            
        case 'network':
            updateInterimDisplay('⚠️ Network error, retrying...', true);
            setTimeout(restartRecognition, 1000);
            break;
            
        default:
            recognitionAttempts++;
            if (recognitionAttempts < 3) {
                console.log(`🔄 Retry attempt ${recognitionAttempts}...`);
                setTimeout(restartRecognition, 1000);
            } else {
                handleRecognitionFailure(event.error);
            }
    }
}

function handleRecognitionEnd() {
    console.log('🛑 Recognition ended');
    
    if (finalTranscript.trim()) {
        sendTranscription(finalTranscript.trim());
        finalTranscript = '';
    }
    
    if (isRecording && autoRestartEnabled) {
        console.log('🔄 Auto-restarting...');
        restartRecognition();
    }
}

function restartRecognition() {
    if (!isRecording) return;
    
    clearTimeout(warmupTimeout);
    warmupTimeout = setTimeout(() => {
        console.log('🔄 Restarting recognition...');
        try {
            recognition.abort();
            recognition.start();
            lastSpeechTimestamp = Date.now();
        } catch (error) {
            console.error('❌ Restart failed:', error);
            handleRecognitionFailure('restart_failed');
        }
    }, 300);
}

function handleRecognitionFailure(error) {
    console.error('❌ Recognition failed:', error);
    isRecording = false;
    updateRecordButton();
    updateInterimDisplay(`Error: ${error}`, false);
    document.getElementById('autoRestartBadge').style.display = 'none';
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

        if (finalTranscript.trim()) {
            sendTranscription(finalTranscript.trim());
            finalTranscript = '';
        }

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

            if (event.results[i].isFinal) {
                finalTranscript += transcript + ' ';
                console.log('✅ Final:', transcript);

                sendTranscription(finalTranscript.trim());
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

function sendTranscription(text) {
    if (!text || !socket || !socket.connected) {
        console.warn('⚠️ Cannot send - no text or no connection');
        return;
    }

    console.log(`📤 SENDING TO SERVER: "${text}"`);

    socket.emit('new_transcription', {
        text: text,
        language: recognitionLanguage.split('-')[0],
        timestamp: new Date().toISOString()
    });

    updateInterimDisplay('✓ Sent: ' + text.substring(0, 50) + '...', true);
}

function updateRecordButton() {
    const btn = document.getElementById('recordBtn');
    if (isRecording) {
        btn.textContent = '⏹️ Stop Recording';
        btn.className = 'pf-c-button pf-c-button--danger recording';
    } else {
        btn.textContent = '🎙️ Start Recording';
        btn.className = 'pf-c-button pf-c-button--success';
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
        warmupRecognition();
    } else {
        stopRecording();
    }
}

function startRecording() {
    try {
        finalTranscript = '';
        recognition.lang = recognitionLanguage;
        recognition.start();
        console.log(`🚀 Starting (language: ${recognitionLanguage})`);
    } catch (error) {
        console.error('Failed to start:', error);

        if (error.message && error.message.includes('already started')) {
            isRecording = true;
            updateRecordButton();
            updateInterimDisplay('🎤 Listening...', true);
            document.getElementById('autoRestartBadge').style.display = 'flex';
        } else {
            alert(`Failed to start recording: ${error.message}`);
        }
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
    const select = document.getElementById('sourceLangSelect');
    const oldLang = recognitionLanguage;
    recognitionLanguage = select.value;
    console.log(`🌍 Language: ${oldLang} → ${recognitionLanguage}`);

    if (isRecording) {
        console.log('🔄 Restarting with new language...');
        stopRecording();
        setTimeout(() => {
            autoRestartEnabled = true;
            startRecording();
        }, 1000);
    }
}

let draggedElement = null;
let draggedIndex = null;
let touchStartY = 0;
let touchElement = null;

function renderTranscriptions() {
    const list = document.getElementById('transcriptionsList');
    document.getElementById('itemCount').textContent = translations.length;

    if (translations.length === 0) {
        list.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">💬</div>
                        <div>No transcriptions yet</div>
                        <small style="display: block; margin-top: 0.5rem; opacity: 0.7;">
                            Start recording to see transcriptions
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
                        <div class="card-header">
                            <span class="card-time">${item.timestamp}</span>
                            ${item.is_corrected ? '<span class="card-badge">✓ Corrected</span>' : ''}
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

    socket.emit('new_transcription', {
        text: text,
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

    alert('Delete functionality requires server-side implementation');
}

function saveCorrection() {
    if (!selectedItem) {
        alert('No item selected');
        return;
    }

    const corrected = document.getElementById('correctedText').value.trim();
    if (!corrected) {
        alert('Corrected text cannot be empty');
        return;
    }

    socket.emit('correct_translation', {
        id: selectedItem.id,
        corrected_text: corrected
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
            headers: {'Authorization': `Bearer ${authToken}`}
        });
        const data = await response.json();

        const timestamp = data.timestamp ?
            new Date(data.timestamp).toLocaleString('en-US', {
                month: '2-digit',
                day: '2-digit',
                year: 'numeric',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit',
                hour12: false
            }) :
            new Date().toLocaleTimeString();

        document.getElementById('systemInfo').textContent =
            `⏰ ${timestamp}\n` +
            `${'─'.repeat(30)}\n` +
            `Status: ${data.status}\n` +
            `Clients: ${data.clients}\n` +
            `Translations: ${data.translations}\n` +
            `Recording: ${isRecording ? '🔴 Active' : '⚪ Stopped'}\n` +
            `Language: ${recognitionLanguage}`;
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