"""
EzySpeechTranslate Admin GUI - Modern Design with CustomTkinter
Beautiful, modern interface with proper spacing and visual hierarchy
"""

import customtkinter as ctk
from tkinter import messagebox, filedialog
import threading
import queue
from dataclasses import dataclass, asdict
from typing import Optional, Callable, List, Dict, Any
from datetime import datetime
from pathlib import Path
import logging

import sounddevice as sd
import numpy as np
from faster_whisper import WhisperModel
import yaml
import requests
import socketio as sio
import json

from system_monitor import SystemMonitor
import socket
import platform
import subprocess
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Set appearance mode and color theme
ctk.set_appearance_mode("system")  # "system", "dark", "light"
ctk.set_default_color_theme("blue")  # "blue", "green", "dark-blue"


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class TranscriptionItem:
    """Data model for a transcription entry."""
    id: int
    timestamp: str
    original: str
    corrected: str
    source_language: str
    translated: Optional[str] = None
    is_corrected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def get_display_text(self) -> str:
        """Generate display text for list view."""
        marker = " ✓" if self.is_corrected else ""
        return f"[{self.timestamp}] {self.corrected}{marker}"


@dataclass
class AudioConfig:
    """Audio processing configuration."""
    sample_rate: int = 16000
    block_duration: float = 5.0
    device_index: Optional[int] = None


@dataclass
class WhisperConfig:
    """Whisper model configuration."""
    model_size: str = 'base'
    device: str = 'cpu'
    compute_type: str = 'int8'
    language: Optional[str] = None
    beam_size: int = 5
    vad_filter: bool = True


# ============================================================================
# Configuration Management
# ============================================================================

class ConfigManager:
    """Manages application configuration."""

    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = Path(config_path)
        self._data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {self.config_path}")
            return {}
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}

    def get(self, *keys, default=None):
        """Get nested configuration value."""
        value = self._data
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value if value is not None else default

    def get_audio_config(self) -> AudioConfig:
        """Get audio configuration."""
        return AudioConfig(
            sample_rate=self.get('audio', 'sample_rate', default=16000),
            block_duration=self.get('audio', 'block_duration', default=5.0)
        )

    def get_whisper_config(self) -> WhisperConfig:
        """Get Whisper configuration."""
        return WhisperConfig(
            model_size=self.get('whisper', 'model_size', default='base'),
            device=self.get('whisper', 'device', default='cpu'),
            compute_type=self.get('whisper', 'compute_type', default='int8'),
            language=self.get('whisper', 'language'),
            beam_size=self.get('whisper', 'beam_size', default=5),
            vad_filter=self.get('whisper', 'vad_filter', default=True)
        )

    def get_server_url(self) -> str:
        """Get server URL."""
        host = self.get('server', 'host', default='localhost')
        port = self.get('server', 'port', default=5000)
        return f"http://{host}:{port}"


# ============================================================================
# Network Services
# ============================================================================

class ServerHealthChecker:
    """Checks server health status."""

    def __init__(self, config: ConfigManager):
        self.config = config

    def check(self, timeout: float = 3.0) -> bool:
        """Check if server is healthy."""
        try:
            url = f"{self.config.get_server_url()}/api/health"
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.debug(f"Health check failed: {e}")
            return False


class AuthenticationService:
    """Handles user authentication."""

    def __init__(self, config: ConfigManager):
        self.config = config

    def login(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and return token."""
        try:
            url = f"{self.config.get_server_url()}/api/login"
            response = requests.post(
                url,
                json={'username': username, 'password': password},
                timeout=6
            )

            if response.status_code == 200:
                return response.json().get('token')
            else:
                logger.warning(f"Login failed with status: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"Login error: {e}")
            return None


class WebSocketManager:
    """Manages WebSocket connections."""

    def __init__(self, config: ConfigManager, token: str):
        self.config = config
        self.token = token
        self.socket: Optional[sio.Client] = None
        self._callbacks = {
            'connect': [],
            'disconnect': [],
            'new_transcription': []
        }

    def connect(self):
        """Establish WebSocket connection."""
        try:
            self.socket = sio.Client()

            @self.socket.event
            def connect():
                logger.info("WebSocket connected")
                self._trigger_callbacks('connect')
                try:
                    self.socket.emit('admin_connect', {'token': self.token})
                except Exception as e:
                    logger.error(f"Failed to emit admin_connect: {e}")

            @self.socket.event
            def disconnect():
                logger.info("WebSocket disconnected")
                self._trigger_callbacks('disconnect')

            @self.socket.on('new_transcription')
            def on_new_transcription(data):
                self._trigger_callbacks('new_transcription', data)

            url = self.config.get_server_url()
            self.socket.connect(url)

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            raise

    def disconnect(self):
        """Close WebSocket connection."""
        if self.socket:
            try:
                self.socket.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")

    def emit(self, event: str, data: Any):
        """Emit event to server."""
        if self.socket and getattr(self.socket, 'connected', False):
            try:
                self.socket.emit(event, data)
            except Exception as e:
                logger.error(f"Failed to emit {event}: {e}")

    def on(self, event: str, callback: Callable):
        """Register event callback."""
        if event in self._callbacks:
            self._callbacks[event].append(callback)

    def _trigger_callbacks(self, event: str, *args):
        """Trigger all callbacks for an event."""
        for callback in self._callbacks.get(event, []):
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Callback error for {event}: {e}")


# ============================================================================
# Audio Processing
# ============================================================================

class AudioProcessor:
    """Handles audio capture and transcription."""

    def __init__(
        self,
        audio_config: AudioConfig,
        whisper_config: WhisperConfig,
        callback: Callable[[str, str], None]
    ):
        self.audio_config = audio_config
        self.whisper_config = whisper_config
        self.callback = callback

        self.buffer = np.zeros(0, dtype=np.float32)
        self.running = False
        self.stream: Optional[sd.InputStream] = None

        self._load_model()

    def _load_model(self):
        """Load Whisper model."""
        logger.info("Loading Whisper model...")
        self.model = WhisperModel(
            self.whisper_config.model_size,
            device=self.whisper_config.device,
            compute_type=self.whisper_config.compute_type
        )
        logger.info("Whisper model loaded successfully")

    def _audio_callback(self, indata, frames, time, status):
        """Handle incoming audio data."""
        if status:
            logger.warning(f"Audio status: {status}")

        self.buffer = np.append(self.buffer, indata[:, 0])

        required_samples = int(
            self.audio_config.sample_rate * self.audio_config.block_duration
        )

        if len(self.buffer) >= required_samples:
            segment = self.buffer[:required_samples].copy()
            self.buffer = self.buffer[required_samples:]

            threading.Thread(
                target=self._transcribe_segment,
                args=(segment,),
                daemon=True
            ).start()

    def _transcribe_segment(self, audio_segment: np.ndarray):
        """Transcribe audio segment."""
        try:
            segments, info = self.model.transcribe(
                audio_segment,
                language=self.whisper_config.language,
                beam_size=self.whisper_config.beam_size,
                vad_filter=self.whisper_config.vad_filter
            )

            text = "".join(s.text for s in segments).strip()
            language = getattr(info, 'language', 'en') if info else 'en'

            if text:
                self.callback(text, language)

        except Exception as e:
            logger.error(f"Transcription failed: {e}", exc_info=True)

    def start(self, device_index: Optional[int] = None):
        """Start audio capture."""
        if self.running:
            logger.warning("Audio processor already running")
            return

        try:
            self.stream = sd.InputStream(
                samplerate=self.audio_config.sample_rate,
                channels=1,
                dtype='float32',
                callback=self._audio_callback,
                device=device_index
            )
            self.stream.start()
            self.running = True
            logger.info("Audio stream started")

        except Exception as e:
            logger.error(f"Failed to start audio stream: {e}")
            raise

    def stop(self):
        """Stop audio capture."""
        if self.stream:
            try:
                self.stream.stop()
                self.stream.close()
                self.stream = None
            except Exception as e:
                logger.error(f"Error stopping audio stream: {e}")

        self.running = False
        logger.info("Audio stream stopped")

    def is_running(self) -> bool:
        """Check if processor is running."""
        return self.running


# ============================================================================
# Export Functionality
# ============================================================================

class TranscriptionExporter:
    """Export transcriptions to various formats."""

    @staticmethod
    def export_to_text(translations: List[TranscriptionItem], path: str):
        """Export to plain text format."""
        with open(path, 'w', encoding='utf-8') as f:
            f.write("EzySpeechTranslate Export\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

            for item in translations:
                f.write(f"[{item.id}] {item.timestamp}\n")
                f.write(f"Original: {item.original}\n")
                f.write(f"Corrected: {item.corrected}\n")
                if item.is_corrected:
                    f.write("(Manually corrected)\n")
                f.write("-" * 60 + "\n")

    @staticmethod
    def export_to_json(translations: List[TranscriptionItem], path: str):
        """Export to JSON format."""
        data = [item.to_dict() for item in translations]
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def export_to_srt(translations: List[TranscriptionItem], path: str):
        """Export to SRT subtitle format."""
        with open(path, 'w', encoding='utf-8') as f:
            for i, item in enumerate(translations, start=1):
                start_seconds = (i - 1) * 5
                end_seconds = i * 5

                start_time = TranscriptionExporter._format_srt_time(start_seconds)
                end_time = TranscriptionExporter._format_srt_time(end_seconds)

                f.write(f"{i}\n")
                f.write(f"{start_time} --> {end_time}\n")
                f.write(f"{item.corrected}\n\n")

    @staticmethod
    def _format_srt_time(seconds: int) -> str:
        """Format seconds to SRT time format."""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d},000"


# ============================================================================
# System Utilities
# ============================================================================

class SystemInfoProvider:
    """Provides system information display."""

    @staticmethod
    def format_system_info(
        stats: Dict[str, Any],
        config: ConfigManager,
        translation_count: int
    ) -> str:
        """Format system stats for display."""
        cpu = stats.get('cpu', {})
        mem = stats.get('memory', {})
        gpus = stats.get('gpu', [])

        gpu_info = "None"
        if gpus:
            lines = [
                f"GPU{g.get('id', 0)}: {g.get('load', 0):.1f}% | "
                f"{g.get('temperature', 0)}°C"
                for g in gpus
            ]
            gpu_info = "\n".join(lines)

        local_ip = SystemInfoProvider._get_local_ip()

        return (
            f"⏰ {stats.get('timestamp', '')}\n"
            f"{'─' * 40}\n"
            f"CPU: {cpu.get('percent', 0):.1f}%\n"
            f"Memory: {mem.get('percent', 0):.1f}% "
            f"({mem.get('used', 0):.1f}/{mem.get('total', 0):.1f} GB)\n"
            f"GPU(s): {gpu_info}\n"
            f"{'─' * 40}\n"
            f"Model: {config.get('whisper', 'model_size', default='base')}\n"
            f"Device: {config.get('whisper', 'device', default='cpu')}\n"
            f"Server: {local_ip}:{config.get('server', 'port', default=5000)}\n"
            f"Items: {translation_count}\n"
        )

    @staticmethod
    def _get_local_ip() -> str:
        """Get local IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"


# ============================================================================
# Custom UI Components
# ============================================================================

class ConnectionStatusBadge(ctk.CTkFrame):
    """Modern connection status badge."""

    def __init__(self, parent, show_server=False, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.show_server = show_server

        # Status dot
        self.canvas = ctk.CTkCanvas(
            self,
            width=12,
            height=12,
            bg=self._apply_appearance_mode(ctk.ThemeManager.theme["CTkFrame"]["fg_color"]),
            highlightthickness=0
        )
        self.canvas.pack(side="left", padx=(0, 8))

        # Status label
        self.label = ctk.CTkLabel(
            self,
            text="Disconnected",
            font=ctk.CTkFont(size=13)
        )
        self.label.pack(side="left")

        self.set_status('offline')

    def set_status(self, status: str):
        """Update connection status."""
        colors = {
            'online': '#10b981',
            'offline': '#ef4444',
            'connecting': '#f59e0b'
        }

        if self.show_server:
            texts = {
                'online': 'Connected to Server',
                'offline': 'Disconnected from Server',
                'connecting': 'Connecting to Server...'
            }
        else:
            texts = {
                'online': 'Connected',
                'offline': 'Disconnected',
                'connecting': 'Connecting...'
            }

        color = colors.get(status, '#ef4444')
        text = texts.get(status, 'Unknown')

        self.canvas.delete("all")
        self.canvas.create_oval(2, 2, 10, 10, fill=color, outline=color)
        self.label.configure(text=text)


class TranscriptionCard(ctk.CTkFrame):
    """Card for displaying a single transcription."""

    def __init__(
        self,
        parent,
        item: TranscriptionItem,
        on_select: Callable,
        on_drag_start: Callable,
        on_drag_move: Callable,
        on_drag_end: Callable,
        **kwargs
    ):
        super().__init__(parent, corner_radius=8, **kwargs)

        self.item = item
        self.on_select = on_select
        self.on_drag_start = on_drag_start
        self.on_drag_move = on_drag_move
        self.on_drag_end = on_drag_end
        self.selected = False
        self.dragging = False

        # Main container
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True)

        # Drag handle (left side, larger and more visible)
        self.drag_handle = ctk.CTkButton(
            main_container,
            text="⋮\n⋮",
            width=40,
            height=60,
            font=ctk.CTkFont(size=20, weight="bold"),
            fg_color=("gray80", "gray25"),
            hover_color=("gray70", "gray30"),
            cursor="hand2"
        )
        self.drag_handle.pack(side="left", padx=(8, 0), pady=8)

        # Bind drag events to handle
        self.drag_handle.bind("<Button-1>", self._start_drag)
        self.drag_handle.bind("<B1-Motion>", self._do_drag)
        self.drag_handle.bind("<ButtonRelease-1>", self._end_drag)

        # Checkbox
        self.checkbox_var = ctk.BooleanVar(value=False)
        self.checkbox = ctk.CTkCheckBox(
            main_container,
            text="",
            variable=self.checkbox_var,
            width=30,
            command=self.toggle_selection
        )
        self.checkbox.pack(side="left", padx=(12, 8), pady=12)

        # Content frame (clickable)
        self.content_frame = ctk.CTkFrame(main_container, fg_color="transparent", cursor="hand2")
        self.content_frame.pack(side="left", fill="both", expand=True, padx=8, pady=12)

        # Bind click to select
        self.content_frame.bind("<Button-1>", lambda e: self.toggle_selection())

        # Timestamp
        self.timestamp_label = ctk.CTkLabel(
            self.content_frame,
            text=item.timestamp,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=("gray50", "gray60"),
            cursor="hand2"
        )
        self.timestamp_label.pack(anchor="w")
        self.timestamp_label.bind("<Button-1>", lambda e: self.toggle_selection())

        # Text
        self.text_label = ctk.CTkLabel(
            self.content_frame,
            text=item.corrected,
            font=ctk.CTkFont(size=13),
            anchor="w",
            justify="left",
            wraplength=500,
            cursor="hand2"
        )
        self.text_label.pack(anchor="w", pady=(4, 0))
        self.text_label.bind("<Button-1>", lambda e: self.toggle_selection())

        # Corrected indicator
        if item.is_corrected:
            self.corrected_badge = ctk.CTkLabel(
                self.content_frame,
                text="✓ Corrected",
                font=ctk.CTkFont(size=11),
                text_color=("#10b981", "#10b981"),
                cursor="hand2"
            )
            self.corrected_badge.pack(anchor="w", pady=(4, 0))
            self.corrected_badge.bind("<Button-1>", lambda e: self.toggle_selection())

    def _start_drag(self, event):
        """Start dragging."""
        self.dragging = True
        self.drag_start_y = event.y_root
        self.on_drag_start(self, event)
        # Visual feedback
        self.configure(fg_color=("gray90", "gray20"))

    def _do_drag(self, event):
        """Handle drag motion."""
        if self.dragging:
            self.on_drag_move(self, event)

    def _end_drag(self, event):
        """End dragging."""
        if self.dragging:
            self.dragging = False
            self.on_drag_end(self, event)
            # Reset visual
            self.configure(fg_color=("gray95", "gray17"))

    def toggle_selection(self):
        """Toggle card selection."""
        self.selected = self.checkbox_var.get()
        self.on_select()

    def set_selected(self, selected: bool):
        """Set selection state."""
        self.selected = selected
        self.checkbox_var.set(selected)


# ============================================================================
# Application Windows
# ============================================================================

class LoginWindow(ctk.CTk):
    """Modern login window."""

    def __init__(
        self,
        config: ConfigManager,
        on_success: Callable[[str], None]
    ):
        super().__init__()

        self.config = config
        self.on_success = on_success
        self.auth_service = AuthenticationService(config)
        self.health_checker = ServerHealthChecker(config)

        self._setup_window()
        self._create_ui()
        self._start_health_check()

    def _setup_window(self):
        """Setup window properties."""
        title = self.config.get('gui', 'window_title', default='EzySpeechTranslate')
        self.title(f"Login - {title}")

        width, height = 600, 800
        self.geometry(f"{width}x{height}")
        self.resizable(False, False)

        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2
        self.geometry(f"{width}x{height}+{x}+{y}")

    def _create_ui(self):
        """Create UI elements."""
        # Main container with padding
        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=40, pady=40)

        # Logo section
        logo_frame = ctk.CTkFrame(container, corner_radius=16)
        logo_frame.pack(fill="x", pady=(0, 24))

        # App icon/emoji
        icon_label = ctk.CTkLabel(
            logo_frame,
            text="🎤",
            font=ctk.CTkFont(size=64)
        )
        icon_label.pack(pady=(32, 16))

        # App name
        app_name = self.config.get('gui', 'window_title', default='EzySpeechTranslate')
        title_label = ctk.CTkLabel(
            logo_frame,
            text=app_name,
            font=ctk.CTkFont(size=28, weight="bold")
        )
        title_label.pack()

        subtitle_label = ctk.CTkLabel(
            logo_frame,
            text="Admin Panel",
            font=ctk.CTkFont(size=14),
            text_color=("gray50", "gray60")
        )
        subtitle_label.pack(pady=(4, 24))

        # Connection status
        self.status_badge = ConnectionStatusBadge(logo_frame, show_server=False)
        self.status_badge.pack(pady=(0, 24))

        # Login form
        form_frame = ctk.CTkFrame(container, corner_radius=16)
        form_frame.pack(fill="both", expand=True)

        form_inner = ctk.CTkFrame(form_frame, fg_color="transparent")
        form_inner.pack(fill="both", expand=True, padx=32, pady=32)

        # Username
        username_label = ctk.CTkLabel(
            form_inner,
            text="Username",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        username_label.pack(fill="x", pady=(0, 8))

        self.username_entry = ctk.CTkEntry(
            form_inner,
            placeholder_text="Enter your username",
            height=44,
            font=ctk.CTkFont(size=14)
        )
        self.username_entry.pack(fill="x", pady=(0, 20))

        # Password
        password_label = ctk.CTkLabel(
            form_inner,
            text="Password",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        password_label.pack(fill="x", pady=(0, 8))

        self.password_entry = ctk.CTkEntry(
            form_inner,
            placeholder_text="Enter your password",
            show="●",
            height=44,
            font=ctk.CTkFont(size=14)
        )
        self.password_entry.pack(fill="x", pady=(0, 12))

        # Status label
        self.status_label = ctk.CTkLabel(
            form_inner,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("#ef4444", "#ef4444")
        )
        self.status_label.pack(pady=(0, 20))

        # Sign in button
        self.signin_button = ctk.CTkButton(
            form_inner,
            text="Sign In",
            command=self._handle_login,
            height=48,
            font=ctk.CTkFont(size=15, weight="bold"),
            corner_radius=8
        )
        self.signin_button.pack(fill="x")

        # Keyboard bindings
        self.username_entry.bind("<Return>", lambda e: self.password_entry.focus())
        self.password_entry.bind("<Return>", lambda e: self._handle_login())

        # Focus on username
        self.after(100, lambda: self.username_entry.focus())

    def _start_health_check(self):
        """Start background health check."""
        def check_loop():
            is_healthy = self.health_checker.check()
            status = 'online' if is_healthy else 'offline'
            self.after(0, lambda s=status: self.status_badge.set_status(s))

            # If offline, show error message
            if not is_healthy:
                self.after(0, lambda: self.status_label.configure(
                    text="⚠️ Cannot connect to server. Please check if the server is running.",
                    text_color=("#f59e0b", "#f59e0b")
                ))

        threading.Thread(target=check_loop, daemon=True).start()

    def _handle_login(self):
        """Handle login attempt."""
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self.status_label.configure(text="Please fill in all fields")
            return

        self.status_label.configure(
            text="Authenticating...",
            text_color=("#3b82f6", "#3b82f6")
        )
        self.signin_button.configure(state="disabled")

        def authenticate():
            token = self.auth_service.login(username, password)

            if token:
                self.after(0, lambda: self._handle_success(token))
            else:
                self.after(0, lambda: (
                    self.status_label.configure(
                        text="Invalid credentials",
                        text_color=("#ef4444", "#ef4444")
                    ),
                    self.signin_button.configure(state="normal")
                ))

        threading.Thread(target=authenticate, daemon=True).start()

    def _handle_success(self, token: str):
        """Handle successful login."""
        self.destroy()
        if callable(self.on_success):
            self.on_success(token)


class AdminGUI(ctk.CTk):
    """Main admin GUI with modern design."""

    def __init__(self, token: str):
        super().__init__()

        self.token = token
        self.config = ConfigManager()
        self.message_queue = queue.Queue()
        self.translations: List[TranscriptionItem] = []
        self.audio_processor: Optional[AudioProcessor] = None
        self.websocket: Optional[WebSocketManager] = None
        self.sys_monitor: Optional[SystemMonitor] = None

        # Configuration
        self.max_history = self.config.get('gui', 'max_history', default=1000)
        self.auto_scroll = self.config.get('gui', 'auto_scroll', default=True)
        self.reverse_order = True

        self._setup_window()
        self._create_ui()
        self._initialize_services()

    def _setup_window(self):
        """Setup window properties."""
        title = self.config.get('gui', 'window_title', default='EzySpeechTranslate Admin')
        self.title(title)
        geometry = self.config.get('gui', 'window_size', default='1800x1200')
        self.geometry(geometry)

        # Maximize window
        try:
            self.state('zoomed')
        except Exception:
            try:
                self.attributes('-zoomed', True)
            except Exception:
                pass

    def _create_ui(self):
        """Create all UI elements."""
        # Top bar
        self._create_top_bar()

        # Main content
        self._create_main_content()

        logger.info("Admin GUI initialized")

    def _create_top_bar(self):
        """Create top navigation bar."""
        topbar = ctk.CTkFrame(self, height=60, corner_radius=0)
        topbar.pack(fill="x", padx=0, pady=0)
        topbar.pack_propagate(False)

        # Left side - connection status
        left_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        left_frame.pack(side="left", padx=20)

        self.connection_status = ConnectionStatusBadge(left_frame, show_server=True)
        self.connection_status.pack(side="left", pady=16)

        # Right side - theme toggle
        right_frame = ctk.CTkFrame(topbar, fg_color="transparent")
        right_frame.pack(side="right", padx=20)

        self.theme_switch = ctk.CTkSwitch(
            right_frame,
            text="Dark Mode",
            command=self.toggle_theme,
            font=ctk.CTkFont(size=13)
        )
        self.theme_switch.pack(side="right", pady=16)

        # Set initial theme
        current_mode = ctk.get_appearance_mode()
        self.theme_switch.select() if current_mode == "Dark" else self.theme_switch.deselect()

    def _create_main_content(self):
        """Create main content area."""
        # Main container with padding
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="both", expand=True, padx=20, pady=20)

        # Control panel
        self._create_control_panel(main_container)

        # Content grid (2 columns)
        content_frame = ctk.CTkFrame(main_container, fg_color="transparent")
        content_frame.pack(fill="both", expand=True, pady=(16, 0))

        # Configure grid
        content_frame.grid_columnconfigure(0, weight=3)
        content_frame.grid_columnconfigure(1, weight=2)
        content_frame.grid_rowconfigure(0, weight=1)

        # Left column - transcriptions
        self._create_transcription_panel(content_frame)

        # Right column - editor and system info
        right_column = ctk.CTkFrame(content_frame, fg_color="transparent")
        right_column.grid(row=0, column=1, sticky="nsew", padx=(16, 0))

        self._create_editor_panel(right_column)
        self._create_system_panel(right_column)

    def _create_control_panel(self, parent):
        """Create audio control panel."""
        control_frame = ctk.CTkFrame(parent, corner_radius=12)
        control_frame.pack(fill="x", pady=0, ipady=4)

        inner = ctk.CTkFrame(control_frame, fg_color="transparent")
        inner.pack(fill="x", padx=24, pady=0, ipady=4)

        # Header
        header = ctk.CTkFrame(inner, fg_color="transparent", height=1)
        header.pack(fill="x", pady=(0, 4))

        title = ctk.CTkLabel(
            header,
            text="Audio Controls",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        # Audio device row
        device_frame = ctk.CTkFrame(inner, fg_color="transparent", height=48)
        device_frame.pack(fill="x", pady=(0, 4))
        device_frame.pack_propagate(False)

        device_label = ctk.CTkLabel(
            device_frame,
            text="Audio Device:",
            font=ctk.CTkFont(size=13)
        )
        device_label.pack(side="left", padx=(0, 12))

        self.device_menu = ctk.CTkOptionMenu(
            device_frame,
            values=["No devices"],
            width=300,
            height=36,
            font=ctk.CTkFont(size=13)
        )
        self.device_menu.pack(side="left", padx=(0, 12))

        refresh_btn = ctk.CTkButton(
            device_frame,
            text="⟳",
            width=40,
            height=36,
            command=self.refresh_devices,
            font=ctk.CTkFont(size=16)
        )
        refresh_btn.pack(side="left")

        # Status and record button (fixed width container)
        recording_container = ctk.CTkFrame(device_frame, fg_color="transparent", width=400)
        recording_container.pack(side="right")
        recording_container.pack_propagate(False)

        self.status_label = ctk.CTkLabel(
            recording_container,
            text="● Stopped",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=("#ef4444", "#ef4444"),
            width=120
        )
        self.status_label.pack(side="left", padx=(0, 16))

        self.record_button = ctk.CTkButton(
            recording_container,
            text="🎙 Start Recording",
            command=self.toggle_recording,
            width=220,
            height=48,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#10b981", "#10b981"),
            hover_color=("#059669", "#059669")
        )
        self.record_button.pack(side="left")

        # Action buttons
        action_frame = ctk.CTkFrame(inner, fg_color="transparent")
        action_frame.pack(fill="x")

        # Left actions
        left_actions = ctk.CTkFrame(action_frame, fg_color="transparent")
        left_actions.pack(side="left")

        add_btn = ctk.CTkButton(
            left_actions,
            text="➕ Add",
            width=100,
            height=36,
            command=self.add_new_item,
            font=ctk.CTkFont(size=13)
        )
        add_btn.pack(side="left", padx=(0, 8))

        edit_btn = ctk.CTkButton(
            left_actions,
            text="✏️ Edit",
            width=100,
            height=36,
            command=self.edit_selected,
            font=ctk.CTkFont(size=13)
        )
        edit_btn.pack(side="left", padx=(0, 8))

        delete_btn = ctk.CTkButton(
            left_actions,
            text="🗑 Delete",
            width=100,
            height=36,
            command=self.delete_selected,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            font=ctk.CTkFont(size=13)
        )
        delete_btn.pack(side="left")

        # Right actions
        right_actions = ctk.CTkFrame(action_frame, fg_color="transparent")
        right_actions.pack(side="right")

        self.sort_button = ctk.CTkButton(
            right_actions,
            text="🔽 Newest First",
            width=140,
            height=36,
            command=self.toggle_sort_order,
            font=ctk.CTkFont(size=13)
        )
        self.sort_button.pack(side="left", padx=(0, 8))

        clear_btn = ctk.CTkButton(
            right_actions,
            text="🗑 Clear All",
            width=110,
            height=36,
            command=self.clear_history,
            fg_color=("#ef4444", "#dc2626"),
            hover_color=("#dc2626", "#b91c1c"),
            font=ctk.CTkFont(size=13)
        )
        clear_btn.pack(side="left", padx=(0, 8))

        export_btn = ctk.CTkButton(
            right_actions,
            text="📤 Export",
            width=100,
            height=36,
            command=self.export_translations,
            font=ctk.CTkFont(size=13)
        )
        export_btn.pack(side="left")

        # Initialize devices
        self.refresh_devices()

    def _create_transcription_panel(self, parent):
        """Create transcription list panel."""
        trans_frame = ctk.CTkFrame(parent, corner_radius=12)
        trans_frame.grid(row=0, column=0, sticky="nsew")

        # Header
        header = ctk.CTkFrame(trans_frame, fg_color="transparent")
        header.pack(fill="x", padx=24, pady=(20, 12))

        title = ctk.CTkLabel(
            header,
            text="Transcriptions",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        self.item_count_label = ctk.CTkLabel(
            header,
            text="0 items",
            font=ctk.CTkFont(size=13),
            text_color=("gray50", "gray60")
        )
        self.item_count_label.pack(side="right")

        # Scrollable frame for transcriptions
        self.transcription_scroll = ctk.CTkScrollableFrame(
            trans_frame,
            corner_radius=0
        )
        self.transcription_scroll.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self.transcription_cards: List[TranscriptionCard] = []

    def _create_editor_panel(self, parent):
        """Create correction editor panel."""
        editor_frame = ctk.CTkFrame(parent, corner_radius=12)
        editor_frame.pack(fill="both", expand=True, pady=(0, 16))

        # Header
        header = ctk.CTkFrame(editor_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))

        title = ctk.CTkLabel(
            header,
            text="Edit & Correct",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        # Original text
        original_label = ctk.CTkLabel(
            editor_frame,
            text="Original:",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        original_label.pack(fill="x", padx=20, pady=(8, 4))

        self.original_text = ctk.CTkTextbox(
            editor_frame,
            height=120,
            font=ctk.CTkFont(size=13),
            wrap="word",
            state="disabled"
        )
        self.original_text.pack(fill="x", padx=20, pady=(0, 16))

        # Corrected text
        corrected_label = ctk.CTkLabel(
            editor_frame,
            text="Corrected:",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        )
        corrected_label.pack(fill="x", padx=20, pady=(0, 4))

        self.corrected_text = ctk.CTkTextbox(
            editor_frame,
            height=120,
            font=ctk.CTkFont(size=13),
            wrap="word"
        )
        self.corrected_text.pack(fill="x", padx=20, pady=(0, 16))

        # Buttons
        button_frame = ctk.CTkFrame(editor_frame, fg_color="transparent")
        button_frame.pack(fill="x", padx=20, pady=(0, 20))

        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 Save",
            command=self.save_correction,
            width=120,
            height=40,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#10b981", "#10b981"),
            hover_color=("#059669", "#059669")
        )
        save_btn.pack(side="left", padx=(0, 12))

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="✖ Cancel",
            command=self.cancel_correction,
            width=120,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color=("gray70", "gray30")
        )
        cancel_btn.pack(side="left")

    def _create_system_panel(self, parent):
        """Create system info panel."""
        sys_frame = ctk.CTkFrame(parent, corner_radius=12)
        sys_frame.pack(fill="both")

        # Header
        header = ctk.CTkFrame(sys_frame, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(16, 12))

        title = ctk.CTkLabel(
            header,
            text="System Info",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title.pack(side="left")

        # System info text
        self.sys_text = ctk.CTkTextbox(
            sys_frame,
            height=200,
            font=ctk.CTkFont(family="Courier", size=12),
            wrap="none",
            state="disabled"
        )
        self.sys_text.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _initialize_services(self):
        """Initialize background services."""
        # System monitor
        self.sys_monitor = SystemMonitor(
            update_callback=self.update_system_stats,
            interval=1.0
        )
        self.sys_monitor.start()

        # WebSocket connection
        self._connect_websocket()

        # Queue processor
        self.process_queue()

    def _connect_websocket(self):
        """Connect to WebSocket server."""
        try:
            self.websocket = WebSocketManager(self.config, self.token)

            # Register callbacks
            self.websocket.on('connect', self._on_ws_connect)
            self.websocket.on('disconnect', self._on_ws_disconnect)
            self.websocket.on('new_transcription', self._on_ws_new_transcription)

            self.connection_status.set_status('connecting')
            self.websocket.connect()

        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.connection_status.set_status('offline')

    def _on_ws_connect(self):
        """Handle WebSocket connection."""
        self.after(0, lambda: self.connection_status.set_status('online'))

    def _on_ws_disconnect(self):
        """Handle WebSocket disconnection."""
        self.after(0, lambda: self.connection_status.set_status('offline'))

    def _on_ws_new_transcription(self, data: Dict[str, Any]):
        """Handle new transcription from server."""
        text = data.get('text')
        language = data.get('language', 'en')
        if text:
            self.message_queue.put(('transcription', text, language))

    # ========================================================================
    # Event Handlers
    # ========================================================================

    def toggle_theme(self):
        """Toggle between light and dark theme."""
        current = ctk.get_appearance_mode()
        new_mode = "Light" if current == "Dark" else "Dark"
        ctk.set_appearance_mode(new_mode)
        logger.info(f"Theme changed to {new_mode}")

    def toggle_sort_order(self):
        """Toggle sort order."""
        self.reverse_order = not self.reverse_order
        sort_text = "🔽 Newest First" if self.reverse_order else "🔼 Oldest First"
        self.sort_button.configure(text=sort_text)
        self.refresh_transcription_list()
        self.sync_order_to_server()

    def refresh_devices(self):
        """Refresh audio device list."""
        try:
            devices = sd.query_devices()
            inputs = [
                f"{i}: {d['name']}"
                for i, d in enumerate(devices)
                if d['max_input_channels'] > 0
            ]

            if inputs:
                self.device_menu.configure(values=inputs)
                self.device_menu.set(inputs[0])
            else:
                self.device_menu.configure(values=["No devices found"])
                self.device_menu.set("No devices found")

        except Exception as e:
            logger.error(f"Failed to query audio devices: {e}")

    def toggle_recording(self):
        """Toggle audio recording."""
        if self.audio_processor is None or not self.audio_processor.is_running():
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        """Start audio recording."""
        try:
            device_str = self.device_menu.get()

            if device_str == "No devices found":
                messagebox.showerror("Error", "No audio devices available")
                return

            device_index = int(device_str.split(':')[0]) if device_str else None

            if self.audio_processor is None:
                audio_config = self.config.get_audio_config()
                whisper_config = self.config.get_whisper_config()

                self.audio_processor = AudioProcessor(
                    audio_config,
                    whisper_config,
                    self.on_transcription
                )

            self.audio_processor.start(device_index)

            self.record_button.configure(
                text="⏹ Stop Recording",
                fg_color=("#ef4444", "#dc2626"),
                hover_color=("#dc2626", "#b91c1c")
            )
            self.status_label.configure(
                text="● Recording",
                text_color=("#10b981", "#10b981")
            )

        except Exception as e:
            logger.error(f"Start recording failed: {e}")
            messagebox.showerror("Error", f"Failed to start recording: {e}")

    def stop_recording(self):
        """Stop audio recording."""
        if self.audio_processor:
            self.audio_processor.stop()

        self.record_button.configure(
            text="🎙 Start Recording",
            fg_color=("#10b981", "#10b981"),
            hover_color=("#059669", "#059669")
        )
        self.status_label.configure(
            text="● Stopped",
            text_color=("#ef4444", "#ef4444")
        )

    def on_transcription(self, text: str, language: str):
        """Handle new transcription."""
        self.message_queue.put(('transcription', text, language))

    def refresh_transcription_list(self):
        """Refresh the transcription list display."""
        # Clear existing cards
        for card in self.transcription_cards:
            card.destroy()
        self.transcription_cards.clear()

        # Get items to display
        items = list(self.translations[-self.max_history:])
        if self.reverse_order:
            items.reverse()

        # Create cards
        for item in items:
            card = TranscriptionCard(
                self.transcription_scroll,
                item,
                on_select=lambda: None,
                on_drag_start=self._on_card_drag_start,
                on_drag_move=self._on_card_drag_move,
                on_drag_end=self._on_card_drag_end
            )
            card.pack(fill="x", padx=8, pady=4)
            self.transcription_cards.append(card)

        # Update count
        self.item_count_label.configure(text=f"{len(items)} items")

        # Auto scroll
        if self.auto_scroll and items:
            self.after(100, lambda: self.transcription_scroll._parent_canvas.yview_moveto(1.0))

    def _on_card_drag_start(self, card, event):
        """Handle drag start."""
        self._dragging_card = card
        self._drag_start_index = self.transcription_cards.index(card)

    def _on_card_drag_move(self, card, event):
        """Handle drag move."""
        if not hasattr(self, '_dragging_card'):
            return

        # Find target position
        for i, target_card in enumerate(self.transcription_cards):
            if target_card == card:
                continue

            # Get card position
            card_y = target_card.winfo_rooty()
            card_height = target_card.winfo_height()

            # Check if mouse is over this card
            if card_y <= event.y_root <= card_y + card_height:
                # Swap positions
                current_index = self.transcription_cards.index(card)
                if i != current_index:
                    # Reorder in list
                    self.transcription_cards.pop(current_index)
                    self.transcription_cards.insert(i, card)

                    # Repack all cards
                    for c in self.transcription_cards:
                        c.pack_forget()
                    for c in self.transcription_cards:
                        c.pack(fill="x", padx=8, pady=4)
                break

    def _on_card_drag_end(self, card, event):
        """Handle drag end."""
        if hasattr(self, '_dragging_card'):
            # Update translations order
            self.translations = [c.item for c in self.transcription_cards]
            if self.reverse_order:
                self.translations.reverse()

            # Sync to server
            self.sync_order_to_server()

            del self._dragging_card
            del self._drag_start_index

    def add_new_item(self):
        """Show dialog to add new transcription."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add New Transcription")
        dialog.geometry("600x400")
        dialog.transient(self)
        dialog.grab_set()

        # Center dialog
        self.update_idletasks()
        x = self.winfo_x() + (self.winfo_width() // 2) - 300
        y = self.winfo_y() + (self.winfo_height() // 2) - 200
        dialog.geometry(f"600x400+{x}+{y}")

        # Content
        container = ctk.CTkFrame(dialog, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=30, pady=30)

        label = ctk.CTkLabel(
            container,
            text="Enter transcription text:",
            font=ctk.CTkFont(size=16, weight="bold")
        )
        label.pack(anchor="w", pady=(0, 12))

        text_widget = ctk.CTkTextbox(
            container,
            height=200,
            font=ctk.CTkFont(size=14),
            wrap="word"
        )
        text_widget.pack(fill="both", expand=True, pady=(0, 20))
        text_widget.focus()

        def save():
            text = text_widget.get("1.0", "end-1c").strip()
            if not text:
                messagebox.showwarning("Warning", "Text cannot be empty")
                return

            item = TranscriptionItem(
                id=len(self.translations),
                timestamp=datetime.now().strftime('%H:%M:%S'),
                original=text,
                corrected=text,
                source_language='manual'
            )

            self.translations.append(item)
            self.refresh_transcription_list()
            self.sync_order_to_server()
            dialog.destroy()

        # Buttons
        button_frame = ctk.CTkFrame(container, fg_color="transparent")
        button_frame.pack(fill="x")

        save_btn = ctk.CTkButton(
            button_frame,
            text="💾 Save",
            command=save,
            width=140,
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=("#10b981", "#10b981"),
            hover_color=("#059669", "#059669")
        )
        save_btn.pack(side="left", padx=(0, 12))

        cancel_btn = ctk.CTkButton(
            button_frame,
            text="✖ Cancel",
            command=dialog.destroy,
            width=140,
            height=44,
            font=ctk.CTkFont(size=14),
            fg_color=("gray70", "gray30")
        )
        cancel_btn.pack(side="left")

    def delete_selected(self):
        """Delete selected transcriptions."""
        selected_cards = [card for card in self.transcription_cards if card.selected]

        if not selected_cards:
            messagebox.showwarning("Warning", "Please select items to delete")
            return

        if not messagebox.askyesno("Confirm", f"Delete {len(selected_cards)} item(s)?"):
            return

        ids_to_delete = {card.item.id for card in selected_cards}
        self.translations = [
            t for t in self.translations if t.id not in ids_to_delete
        ]

        self.refresh_transcription_list()
        self.cancel_correction()
        self.sync_order_to_server()

    def edit_selected(self):
        """Edit selected transcription."""
        selected_cards = [card for card in self.transcription_cards if card.selected]

        if not selected_cards:
            messagebox.showwarning("Warning", "Please select an item to edit")
            return

        if len(selected_cards) > 1:
            messagebox.showinfo("Info", "Only the first selected item will be edited")

        item = selected_cards[0].item

        self.original_text.configure(state="normal")
        self.original_text.delete("1.0", "end")
        self.original_text.insert("1.0", item.original)
        self.original_text.configure(state="disabled")

        self.corrected_text.delete("1.0", "end")
        self.corrected_text.insert("1.0", item.corrected)
        self.corrected_text.focus()

    def save_correction(self):
        """Save correction to transcription."""
        corrected = self.corrected_text.get("1.0", "end-1c").strip()
        original = self.original_text.get("1.0", "end-1c").strip()

        if not corrected:
            messagebox.showwarning("Warning", "Corrected text cannot be empty")
            return

        if not original:
            messagebox.showwarning("Warning", "No item selected")
            return

        # Find matching item
        target = None
        for translation in self.translations:
            if translation.original == original:
                target = translation
                break

        if target is None:
            messagebox.showwarning("Warning", "Matching item not found")
            return

        target.corrected = corrected
        target.is_corrected = True

        # Broadcast to server
        if self.websocket:
            self.websocket.emit('correct_translation', {
                'id': target.id,
                'corrected_text': corrected
            })

        self.refresh_transcription_list()
        messagebox.showinfo("Success", "Correction saved and broadcasted")

    def cancel_correction(self):
        """Cancel current correction."""
        self.corrected_text.delete("1.0", "end")
        self.original_text.configure(state="normal")
        self.original_text.delete("1.0", "end")
        self.original_text.configure(state="disabled")

    def clear_history(self):
        """Clear all transcriptions."""
        if not messagebox.askyesno("Confirm", "Clear all transcriptions?"):
            return

        self.translations.clear()
        self.refresh_transcription_list()
        self.cancel_correction()

        if self.websocket:
            self.websocket.emit('clear_history')

    def export_translations(self):
        """Export translations to file."""
        if not self.translations:
            messagebox.showinfo("Info", "No translations to export")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("JSON files", "*.json"),
                ("SRT files", "*.srt")
            ]
        )

        if not path:
            return

        try:
            if path.endswith('.json'):
                TranscriptionExporter.export_to_json(self.translations, path)
            elif path.endswith('.srt'):
                TranscriptionExporter.export_to_srt(self.translations, path)
            else:
                TranscriptionExporter.export_to_text(self.translations, path)

            messagebox.showinfo("Success", f"Exported to {path}")

        except Exception as e:
            logger.error(f"Export failed: {e}", exc_info=True)
            messagebox.showerror("Error", "Export failed")

    def sync_order_to_server(self):
        """Sync translation order to server."""
        if self.websocket:
            self.websocket.emit('update_order', {
                'translations': [t.to_dict() for t in self.translations]
            })

    def update_system_stats(self, stats: Dict[str, Any]):
        """Update system stats display."""
        info = SystemInfoProvider.format_system_info(
            stats,
            self.config,
            len(self.translations)
        )

        self.sys_text.configure(state="normal")
        self.sys_text.delete("1.0", "end")
        self.sys_text.insert("1.0", info)
        self.sys_text.configure(state="disabled")

    def process_queue(self):
        """Process message queue."""
        try:
            while True:
                item = self.message_queue.get_nowait()

                if item[0] == 'transcription':
                    self._handle_new_transcription(item[1], item[2])

        except queue.Empty:
            pass

        self.after(100, self.process_queue)

    def _handle_new_transcription(self, text: str, language: str):
        """Handle new transcription from queue."""
        entry = TranscriptionItem(
            id=len(self.translations),
            timestamp=datetime.now().strftime('%H:%M:%S'),
            original=text,
            corrected=text,
            source_language=language
        )

        self.translations.append(entry)
        self.refresh_transcription_list()

        # Trim excess history
        if len(self.translations) > self.max_history:
            excess = len(self.translations) - self.max_history
            self.translations = self.translations[excess:]
            logger.info(f"Trimmed {excess} excess items")

        # Broadcast to server
        if self.websocket:
            self.websocket.emit('new_transcription', {
                'text': text,
                'language': language
            })
            self.sync_order_to_server()

    def on_closing(self):
        """Handle window close event."""
        # Stop audio
        if self.audio_processor and self.audio_processor.is_running():
            self.audio_processor.stop()

        # Stop system monitor
        if self.sys_monitor:
            try:
                self.sys_monitor.stop()
            except Exception as e:
                logger.error(f"Error stopping system monitor: {e}")

        # Disconnect WebSocket
        if self.websocket:
            try:
                self.websocket.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting WebSocket: {e}")

        self.destroy()


# ============================================================================
# Application Entry Point
# ============================================================================

def main():
    """Main application entry point."""
    try:
        config = ConfigManager()

        def on_login_success(token: str):
            """Handle successful login."""
            app = AdminGUI(token)
            app.protocol("WM_DELETE_WINDOW", app.on_closing)
            app.mainloop()

        login_window = LoginWindow(config, on_login_success)
        login_window.mainloop()

    except Exception as e:
        logger.critical(f"Application failed to start: {e}", exc_info=True)
        messagebox.showerror("Fatal Error", f"Application failed to start: {e}")


if __name__ == '__main__':
    main()