"""
EzySpeechTranslate Admin GUI
Desktop application for real-time transcription and correction
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import queue
import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import yaml
import requests
import socketio as sio
import json
from datetime import datetime
import logging
from system_monitor import SystemMonitor
import socket

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_server_health():
    """Check if backend server is reachable"""
    config = Config()
    server_host = config.get('server', 'host', default='localhost')
    server_port = config.get('server', 'port', default=5000)
    url = f"http://{server_host}:{server_port}/api/health"

    try:
        resp = requests.get(url, timeout=3)
        if resp.status_code != 200:
            messagebox.showerror(
                "Server Error",
                f"Server health check failed with status code {resp.status_code}. Cannot start app."
            )
            return False
    except Exception as e:
        messagebox.showerror(
            "Server Error",
            f"Cannot reach server at {server_host}:{server_port}\nError: {e}\nCannot start app."
        )
        return False
    return True

class Config:
    """Configuration manager"""

    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r') as f:
            self.data = yaml.safe_load(f)

    def get(self, *keys, default=None):
        val = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
            else:
                return default
            if val is None:
                return default
        return val


class AudioProcessor:
    """Audio capture and processing"""

    def __init__(self, config, callback):
        self.config = config
        self.callback = callback
        self.sample_rate = config.get('audio', 'sample_rate', default=16000)
        self.block_duration = config.get('audio', 'block_duration', default=5)
        self.buffer = np.zeros(0, dtype=np.float32)
        self.stream = None
        self.running = False

        # Initialize Whisper model
        model_size = config.get('whisper', 'model_size', default='base')
        device = config.get('whisper', 'device', default='cpu')
        compute_type = config.get('whisper', 'compute_type', default='int8')

        logger.info(f"Loading Whisper model: {model_size}")
        self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
        logger.info("Whisper model loaded successfully")

    def audio_callback(self, indata, frames, time, status):
        """Audio stream callback"""
        if status:
            logger.warning(f"Audio status: {status}")

        self.buffer = np.append(self.buffer, indata[:, 0])

        # Process when buffer is full
        if len(self.buffer) >= self.sample_rate * self.block_duration:
            segment = self.buffer[:self.sample_rate * self.block_duration]
            self.buffer = self.buffer[self.sample_rate * self.block_duration:]

            # Process in separate thread to avoid blocking
            threading.Thread(target=self._transcribe, args=(segment,), daemon=True).start()

    def _transcribe(self, audio_data):
        """Transcribe audio segment"""
        try:
            segments, info = self.model.transcribe(
                audio_data,
                language=self.config.get('whisper', 'language'),
                beam_size=self.config.get('whisper', 'beam_size', default=5),
                vad_filter=self.config.get('whisper', 'vad_filter', default=True)
            )

            text = "".join([s.text for s in segments]).strip()

            if text:
                self.callback(text, info.language if hasattr(info, 'language') else 'en')
        except Exception as e:
            logger.error(f"Transcription error: {e}")

    def start(self, device_index=None):
        """Start audio capture"""
        if self.running:
            return

        self.running = True
        self.buffer = np.zeros(0, dtype=np.float32)

        try:
            self.stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype='float32',
                callback=self.audio_callback,
                device=device_index
            )
            self.stream.start()
            logger.info("Audio capture started")
        except Exception as e:
            logger.error(f"Failed to start audio: {e}")
            self.running = False
            raise

    def stop(self):
        """Stop audio capture"""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
        self.running = False
        logger.info("Audio capture stopped")

    def is_running(self):
        return self.running


class AdminGUI:
    """Main admin GUI application"""

    def __init__(self, root):
        self.root = root
        self.config = Config()
        self.token = None
        self.socket = None
        self.audio_processor = None
        self.translations = []
        self.message_queue = queue.Queue()

        # Setup window
        self.root.title(self.config.get('gui', 'window_title', default='EzySpeechTranslate Admin'))
        window_size = self.config.get('gui', 'window_size', default='1200x800')
        self.root.geometry(window_size)

        # Authentication state
        self.authenticated = False

        # Create UI
        self.create_login_ui()

        # Start message queue processor
        self.process_queue()

    def create_login_ui(self):
        """Create login interface"""
        self.login_frame = ttk.Frame(self.root, padding="20")
        self.login_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Center the login frame
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        ttk.Label(self.login_frame, text="EzySpeechTranslate Admin",
                  font=('Arial', 24, 'bold')).grid(row=0, column=0, columnspan=2, pady=20)

        ttk.Label(self.login_frame, text="Username:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.username_entry = ttk.Entry(self.login_frame, width=30)
        self.username_entry.grid(row=1, column=1, pady=5)

        ttk.Label(self.login_frame, text="Password:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.password_entry = ttk.Entry(self.login_frame, width=30, show="*")
        self.password_entry.grid(row=2, column=1, pady=5)

        ttk.Button(self.login_frame, text="Login", command=self.login).grid(
            row=3, column=0, columnspan=2, pady=20)

        self.status_label = ttk.Label(self.login_frame, text="", foreground="red")
        self.status_label.grid(row=4, column=0, columnspan=2)

        # Bind Enter key
        self.password_entry.bind('<Return>', lambda e: self.login())

    def login(self):
        """Authenticate with backend"""
        username = self.username_entry.get()
        password = self.password_entry.get()

        if not username or not password:
            self.status_label.config(text="Please enter username and password")
            return

        try:
            server_host = self.config.get('server', 'host', default='localhost')
            server_port = self.config.get('server', 'port', default=5000)
            url = f"http://{server_host}:{server_port}/api/login"

            response = requests.post(url, json={
                'username': username,
                'password': password
            }, timeout=5)

            if response.status_code == 200:
                data = response.json()
                self.token = data['token']
                self.authenticated = True
                logger.info("Authentication successful")

                # Destroy login frame and create main UI
                self.login_frame.destroy()
                self.create_main_ui()
                self.connect_websocket()
            else:
                self.status_label.config(text="Invalid credentials")
        except requests.exceptions.RequestException as e:
            self.status_label.config(text=f"Connection error: {str(e)}")
            logger.error(f"Login error: {e}")

    def create_main_ui(self):
        """Create main application interface"""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        main_frame.grid_rowconfigure(1, weight=1)
        main_frame.grid_columnconfigure(0, weight=1)

        # Top control panel
        control_frame = ttk.LabelFrame(main_frame, text="Controls", padding="10")
        control_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))

        # Audio device selection
        ttk.Label(control_frame, text="Audio Device:").grid(row=0, column=0, padx=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(control_frame, textvariable=self.device_var,
                                         width=40, state='readonly')
        self.device_combo.grid(row=0, column=1, padx=5)
        self.refresh_devices()

        ttk.Button(control_frame, text="Refresh",
                   command=self.refresh_devices).grid(row=0, column=2, padx=5)

        # Start/Stop button
        self.record_button = ttk.Button(control_frame, text="🎙️ Start Recording",
                                        command=self.toggle_recording, width=20)
        self.record_button.grid(row=0, column=3, padx=5)

        # Status indicator
        self.status_indicator = ttk.Label(control_frame, text="● Stopped",
                                          foreground="red", font=('Arial', 15, 'bold'))
        self.status_indicator.grid(row=0, column=4, padx=5)

        # Clear and Export buttons
        ttk.Button(control_frame, text="Clear History",
                   command=self.clear_history).grid(row=0, column=5, padx=5)
        ttk.Button(control_frame, text="Export",
                   command=self.export_translations).grid(row=0, column=6, padx=5)

        # Main content area with notebook
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Transcription tab
        transcription_frame = ttk.Frame(notebook, padding="10")
        notebook.add(transcription_frame, text="Transcriptions")

        # Transcription list
        list_frame = ttk.Frame(transcription_frame)
        list_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transcription_frame.grid_rowconfigure(0, weight=1)
        transcription_frame.grid_columnconfigure(0, weight=1)

        # Scrollbar and listbox
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        self.transcription_listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                                font=('Arial', 15), height=15)
        self.transcription_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        scrollbar.config(command=self.transcription_listbox.yview)

        list_frame.grid_rowconfigure(0, weight=1)
        list_frame.grid_columnconfigure(0, weight=1)

        self.transcription_listbox.bind('<<ListboxSelect>>', self.on_transcription_select)

        # Correction & System area
        content_frame = ttk.Frame(transcription_frame)
        content_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        transcription_frame.grid_rowconfigure(1, weight=1)
        transcription_frame.grid_columnconfigure(0, weight=1)

        # Correction For 70%
        correction_frame = ttk.LabelFrame(content_frame, text="Correction", padding=10)
        correction_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=7)
        content_frame.grid_rowconfigure(0, weight=1)

        ttk.Label(correction_frame, text="Original:").grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self.original_text = scrolledtext.ScrolledText(correction_frame, height=8, width=60, state='disabled',
                                                       font=('Arial', 18))
        self.original_text.grid(row=1, column=0, sticky="nsew", pady=(0, 5))

        ttk.Label(correction_frame, text="Corrected:").grid(row=2, column=0, sticky=tk.W, pady=(5, 2))
        self.corrected_text = scrolledtext.ScrolledText(correction_frame, height=8, width=60, font=('Arial', 18))
        self.corrected_text.grid(row=3, column=0, sticky="nsew", pady=(0, 5))

        button_frame = ttk.Frame(correction_frame)
        button_frame.grid(row=4, column=0, sticky="e", pady=(5, 0))
        ttk.Button(button_frame, text="Save Correction", command=self.save_correction).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_correction).pack(side=tk.LEFT, padx=5)

        correction_frame.grid_rowconfigure(1, weight=1)
        correction_frame.grid_rowconfigure(3, weight=1)
        correction_frame.grid_columnconfigure(0, weight=1)

        # System & Config For 30%
        sys_frame = ttk.LabelFrame(content_frame, text="System & Config", padding=10)
        sys_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        content_frame.grid_columnconfigure(1, weight=3)

        self.sys_text = scrolledtext.ScrolledText(sys_frame, height=20, width=40, state='disabled',
                                                  font=('Consolas', 12))
        self.sys_text.grid(row=0, column=0, sticky="nsew")
        sys_frame.grid_rowconfigure(0, weight=1)
        sys_frame.grid_columnconfigure(0, weight=1)

        # 初始化系统监控
        self.sys_monitor = SystemMonitor(update_callback=self.update_system_stats, interval=1.0)
        self.sys_monitor.start()
        # Log tab
        log_frame = ttk.Frame(notebook, padding="10")
        notebook.add(log_frame, text="Log")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=100)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log("Admin GUI initialized")

    def refresh_devices(self):
        """Refresh audio device list"""
        try:
            devices = sd.query_devices()
            input_devices = []

            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    input_devices.append(f"{i}: {device['name']}")

            self.device_combo['values'] = input_devices
            if input_devices:
                self.device_combo.current(0)

            self.log(f"Found {len(input_devices)} input devices")
        except Exception as e:
            self.log(f"Error refreshing devices: {e}")
            messagebox.showerror("Error", f"Failed to refresh devices: {e}")

    def toggle_recording(self):
        """Start or stop audio recording"""
        if self.audio_processor is None or not self.audio_processor.is_running():
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording"""
        try:
            # Get selected device index
            device_str = self.device_var.get()
            device_index = int(device_str.split(':')[0]) if device_str else None

            # Initialize audio processor if needed
            if self.audio_processor is None:
                self.audio_processor = AudioProcessor(self.config, self.on_transcription)

            self.audio_processor.start(device_index)

            # Update UI
            self.record_button.config(text="⏹️ Stop Recording")
            self.status_indicator.config(text="● Recording", foreground="green")
            self.log("Recording started")

        except Exception as e:
            self.log(f"Failed to start recording: {e}")
            messagebox.showerror("Error", f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stop audio recording"""
        if self.audio_processor:
            self.audio_processor.stop()

        # Update UI
        self.record_button.config(text="🎙️ Start Recording")
        self.status_indicator.config(text="● Stopped", foreground="red")
        self.log("Recording stopped")

    def on_transcription(self, text, language):
        """Callback for new transcription"""
        self.message_queue.put(('transcription', text, language))

    def on_transcription_select(self, event):
        """Handle transcription selection"""
        selection = self.transcription_listbox.curselection()
        if selection:
            index = selection[0]
            if 0 <= index < len(self.translations):
                item = self.translations[index]

                # Update correction fields
                self.original_text.config(state='normal')
                self.original_text.delete(1.0, tk.END)
                self.original_text.insert(1.0, item.get('original', ''))
                self.original_text.config(state='disabled')

                self.corrected_text.delete(1.0, tk.END)
                self.corrected_text.insert(1.0, item.get('corrected', ''))

    def save_correction(self):
        """Save corrected transcription"""
        selection = self.transcription_listbox.curselection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a transcription to correct")
            return

        index = selection[0]
        corrected_text = self.corrected_text.get(1.0, tk.END).strip()

        if not corrected_text:
            messagebox.showwarning("Warning", "Corrected text cannot be empty")
            return

        # Update local data
        self.translations[index]['corrected'] = corrected_text
        self.translations[index]['is_corrected'] = True

        # Send to server
        if self.socket:
            self.socket.emit('correct_translation', {
                'id': self.translations[index]['id'],
                'corrected_text': corrected_text
            })

        # Update listbox
        self.update_listbox_item(index)
        self.log(f"Correction saved for item {index}")
        messagebox.showinfo("Success", "Correction saved and broadcasted")

    def cancel_correction(self):
        """Cancel correction"""
        self.corrected_text.delete(1.0, tk.END)
        self.original_text.config(state='normal')
        self.original_text.delete(1.0, tk.END)
        self.original_text.config(state='disabled')

    def update_listbox_item(self, index):
        """Update single listbox item"""
        if 0 <= index < len(self.translations):
            item = self.translations[index]
            display_text = f"[{item['timestamp']}] {item['corrected']}"
            if item.get('is_corrected'):
                display_text += " ✓"

            # Keep Current status
            selected_indices = self.transcription_listbox.curselection()

            self.transcription_listbox.delete(index)
            self.transcription_listbox.insert(index, display_text)

            if index in selected_indices or not selected_indices:
                self.transcription_listbox.selection_set(index)

    def update_system_stats(self, stats):
        """Update system and config info in the right-bottom text box (pretty formatted)"""
        cpu = stats.get('cpu', {})
        mem = stats.get('memory', {})
        gpus = stats.get('gpu', [])

        def get_local_ip():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
                s.close()
                return ip
            except:
                return "127.0.0.1"

        # --- Config values ---
        sample_rate = self.config.get('audio', 'sample_rate')
        block_duration = self.config.get('audio', 'block_duration')
        model_size = self.config.get('whisper', 'model_size')
        beam_size = self.config.get('whisper', 'beam_size')
        device = self.config.get('whisper', 'device')
        host = get_local_ip()
        port = self.config.get('server', 'port')

        # --- GPU Info Formatting ---
        if gpus:
            gpu_lines = []
            for gpu in gpus:
                gpu_lines.append(
                    f"  • GPU{gpu.get('id', 0)} {gpu.get('name', 'Unknown')}: "
                    f"{gpu.get('load', 0):.1f}% | "
                    f"{gpu.get('memory_used', 0)}/{gpu.get('memory_total', 0)} MB | "
                    f"{gpu.get('temperature', 0)}°C"
                )
            gpu_info = "\n".join(gpu_lines)
        else:
            gpu_info = "  • None detected"

        # --- Construct Info Text ---
        info_text = (
            f"🕓 {stats.get('timestamp', '')}\n"
            f"───────────────────────────────\n"
            f"CPU     : {cpu.get('percent', 0):>5.1f}%   ({cpu.get('freq_current', 0):.1f}/{cpu.get('freq_max', 0):.1f} MHz)\n"
            f"Memory  : {mem.get('used', 0):>5.2f}/{mem.get('total', 0):.2f} GB  ({mem.get('percent', 0):.1f}%)\n"
            f"GPU(s)  :\n{gpu_info}\n"
            f"───────────────────────────────\n"
            f"Audio   : Sample Rate = {sample_rate}, Block = {block_duration}s\n"
            f"Whisper : Model = {model_size}, Beam = {beam_size}, Device = {device}\n"
            f"Server  : {host}:{port}\n"
        )

        # --- Update Text Widget ---
        self.sys_text.config(state='normal')
        self.sys_text.delete(1.0, tk.END)
        self.sys_text.insert(tk.END, info_text)
        self.sys_text.config(state='disabled')


    def clear_history(self):
        """Clear translation history"""
        if messagebox.askyesno("Confirm", "Clear all transcriptions?"):
            self.translations.clear()
            self.transcription_listbox.delete(0, tk.END)
            self.cancel_correction()

            if self.socket:
                self.socket.emit('clear_history')

            self.log("History cleared")

    def export_translations(self):
        """Export translations to file"""
        if not self.translations:
            messagebox.showinfo("Info", "No translations to export")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("SRT Subtitles", "*.srt"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            if file_path.endswith('.json'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.translations, f, indent=2, ensure_ascii=False)

            elif file_path.endswith('.srt'):
                with open(file_path, 'w', encoding='utf-8') as f:
                    for i, item in enumerate(self.translations, 1):
                        start_seconds = (i - 1) * 5
                        end_seconds = i * 5
                        start_time = f"00:{start_seconds // 60:02d}:{start_seconds % 60:02d},000"
                        end_time = f"00:{end_seconds // 60:02d}:{end_seconds % 60:02d},000"

                        f.write(f"{i}\n")
                        f.write(f"{start_time} --> {end_time}\n")
                        f.write(f"{item['corrected']}\n\n")

            else:  # Default to .txt
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write("EzySpeechTranslate Export\n")
                    f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write("=" * 60 + "\n\n")

                    for item in self.translations:
                        f.write(f"[{item['id']}] {item['timestamp']}\n")
                        f.write(f"Original: {item['original']}\n")
                        f.write(f"Corrected: {item['corrected']}\n")
                        if item.get('is_corrected'):
                            f.write("(Manually corrected)\n")
                        f.write("-" * 60 + "\n\n")

            self.log(f"Exported to {file_path}")
            messagebox.showinfo("Success", f"Exported to {file_path}")

        except Exception as e:
            self.log(f"Export failed: {e}")
            messagebox.showerror("Error", f"Export failed: {e}")

    def connect_websocket(self):
        """Connect to backend WebSocket"""
        try:
            server_host = self.config.get('server', 'host', default='localhost')
            server_port = self.config.get('server', 'port', default=5000)
            url = f"http://{server_host}:{server_port}"

            self.socket = sio.Client()

            @self.socket.on('connect')
            def on_connect():
                self.log("Connected to server")
                self.socket.emit('admin_connect', {'token': self.token})

            @self.socket.on('disconnect')
            def on_disconnect():
                self.log("Disconnected from server")

            @self.socket.on('admin_connected')
            def on_admin_connected(data):
                if data.get('success'):
                    self.log("Admin session authenticated")
                else:
                    self.log(f"Admin authentication failed: {data.get('error')}")

            @self.socket.on('correction_success')
            def on_correction_success(data):
                self.log(f"Correction confirmed by server: ID {data['id']}")

            @self.socket.on('error')
            def on_error(data):
                self.log(f"Server error: {data.get('message')}")

            self.socket.connect(url)

        except Exception as e:
            self.log(f"WebSocket connection failed: {e}")
            messagebox.showerror("Error", f"Failed to connect to server: {e}")

    def process_queue(self):
        """Process message queue from background threads"""
        try:
            while True:
                msg = self.message_queue.get_nowait()

                if msg[0] == 'transcription':
                    text = msg[1]
                    language = msg[2]

                    # Add to translations
                    translation = {
                        'id': len(self.translations),
                        'timestamp': datetime.now().strftime('%H:%M:%S'),
                        'original': text,
                        'corrected': text,
                        'translated': None,
                        'is_corrected': False,
                        'source_language': language
                    }

                    self.translations.append(translation)

                    # Update UI
                    display_text = f"[{translation['timestamp']}] {text}"
                    self.transcription_listbox.insert(tk.END, display_text)
                    self.transcription_listbox.see(tk.END)

                    # Send to server
                    if self.socket:
                        self.socket.emit('new_transcription', {
                            'text': text,
                            'language': language
                        })

                    self.log(f"New transcription: {text[:50]}...")

        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.process_queue)

    def log(self, message):
        """Add message to log"""
        timestamp = datetime.now().strftime('%H:%M:%S')
        log_message = f"[{timestamp}] {message}\n"

        if hasattr(self, 'log_text'):
            self.log_text.insert(tk.END, log_message)
            self.log_text.see(tk.END)

        logger.info(message)

    def on_closing(self):
        """Handle window closing"""
        if self.audio_processor and self.audio_processor.is_running():
            self.audio_processor.stop()

        if self.socket:
            self.socket.disconnect()

        self.root.destroy()


def main():
    """Main entry point"""
    if not check_server_health():
        exit(1)
    else:
        root = tk.Tk()
        app = AdminGUI(root)
        root.protocol("WM_DELETE_WINDOW", app.on_closing)
        root.mainloop()


if __name__ == '__main__':
    main()