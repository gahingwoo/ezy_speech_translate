"""
EzySpeechTranslate Admin GUI - Enhanced Version
Desktop application for real-time transcription and correction
New features: Checkbox selection, Add/Delete, Reverse order, Drag & Drop, Dark/Light Theme
Order synchronization with frontend
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

# Theme configurations
THEMES = {
    'light': {
        'bg': '#ffffff',
        'fg': '#000000',
        'listbox_bg': '#f8f9fa',
        'listbox_fg': '#212529',
        'item_bg': '#ffffff',
        'item_hover': '#e9ecef',
        'item_drag': '#cfe2ff',
        'border': '#dee2e6',
        'button_bg': '#e9ecef',
        'button_fg': '#212529',
        'text_bg': '#ffffff',
        'text_fg': '#000000',
        'accent': '#0d6efd',
        'success': '#198754',
        'danger': '#dc3545',
        'label_fg': '#495057'
    },
    'dark': {
        'bg': '#212529',
        'fg': '#f8f9fa',
        'listbox_bg': '#343a40',
        'listbox_fg': '#f8f9fa',
        'item_bg': '#2b3035',
        'item_hover': '#3d4449',
        'item_drag': '#1e3a5f',
        'border': '#495057',
        'button_bg': '#495057',
        'button_fg': '#f8f9fa',
        'text_bg': '#2b3035',
        'text_fg': '#f8f9fa',
        'accent': '#0d6efd',
        'success': '#198754',
        'danger': '#dc3545',
        'label_fg': '#adb5bd'
    }
}


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


class DraggableListbox(tk.Frame):
    """Enhanced Listbox with checkboxes and drag & drop functionality"""

    def __init__(self, parent, theme='light', on_order_changed=None, **kwargs):
        super().__init__(parent)
        self.theme_name = theme
        self.theme = THEMES[theme]
        self.on_order_changed = on_order_changed  # Callback when order changes

        self.configure(bg=self.theme['bg'])

        # Create canvas for custom drawing
        self.canvas = tk.Canvas(self, bg=self.theme['listbox_bg'],
                               highlightthickness=1,
                               highlightbackground=self.theme['border'])
        self.scrollbar = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Frame inside canvas
        self.frame = tk.Frame(self.canvas, bg=self.theme['listbox_bg'])
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.frame, anchor='nw')

        # Data storage
        self.items = []  # List of {id, text, checked, widgets}
        self.drag_data = {"index": None, "widget": None}

        # Bind events
        self.frame.bind('<Configure>', self._on_frame_configure)
        self.canvas.bind('<Configure>', self._on_canvas_configure)

    def apply_theme(self, theme_name):
        """Apply theme to listbox"""
        self.theme_name = theme_name
        self.theme = THEMES[theme_name]

        self.configure(bg=self.theme['bg'])
        self.canvas.configure(bg=self.theme['listbox_bg'],
                            highlightbackground=self.theme['border'])
        self.frame.configure(bg=self.theme['listbox_bg'])

        # Update all items
        for item in self.items:
            item['frame'].configure(bg=self.theme['item_bg'])
            item['label'].configure(bg=self.theme['item_bg'], fg=self.theme['listbox_fg'])
            item['checkbox'].configure(bg=self.theme['item_bg'],
                                      fg=self.theme['listbox_fg'],
                                      selectcolor=self.theme['item_bg'])

    def _on_frame_configure(self, event=None):
        """Update scroll region"""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))

    def _on_canvas_configure(self, event):
        """Resize frame to canvas width"""
        self.canvas.itemconfig(self.canvas_frame, width=event.width)

    def insert(self, index, item_data):
        """Insert new item with checkbox"""
        item_frame = tk.Frame(self.frame, bg=self.theme['item_bg'],
                             relief=tk.RAISED, borderwidth=1)

        # Checkbox
        var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(item_frame, variable=var, bg=self.theme['item_bg'],
                           fg=self.theme['listbox_fg'],
                           selectcolor=self.theme['item_bg'],
                           activebackground=self.theme['item_hover'],
                           command=lambda: self._on_check_changed(item_data['id']))
        cb.pack(side=tk.LEFT, padx=5)

        # Text label
        label = tk.Label(item_frame, text=item_data['text'],
                        bg=self.theme['item_bg'],
                        fg=self.theme['listbox_fg'],
                        font=('Arial', 12), anchor='w', justify=tk.LEFT)
        label.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Bind drag events
        item_frame.bind('<Button-1>', lambda e: self._on_drag_start(e, item_data['id']))
        item_frame.bind('<B1-Motion>', self._on_drag_motion)
        item_frame.bind('<ButtonRelease-1>', self._on_drag_release)
        label.bind('<Button-1>', lambda e: self._on_drag_start(e, item_data['id']))
        label.bind('<B1-Motion>', self._on_drag_motion)
        label.bind('<ButtonRelease-1>', self._on_drag_release)

        # Hover effect
        def on_enter(e):
            if self.drag_data["index"] is None:
                item_frame.configure(bg=self.theme['item_hover'])
                label.configure(bg=self.theme['item_hover'])
                cb.configure(bg=self.theme['item_hover'])

        def on_leave(e):
            if self.drag_data["index"] is None:
                item_frame.configure(bg=self.theme['item_bg'])
                label.configure(bg=self.theme['item_bg'])
                cb.configure(bg=self.theme['item_bg'])

        item_frame.bind('<Enter>', on_enter)
        item_frame.bind('<Leave>', on_leave)
        label.bind('<Enter>', on_enter)
        label.bind('<Leave>', on_leave)

        # Store item
        item_entry = {
            'id': item_data['id'],
            'text': item_data['text'],
            'data': item_data.get('data'),
            'checked': False,
            'var': var,
            'frame': item_frame,
            'label': label,
            'checkbox': cb
        }

        if index == 'end' or index >= len(self.items):
            self.items.append(item_entry)
            item_frame.pack(fill=tk.X, padx=2, pady=1)
        else:
            self.items.insert(index, item_entry)
            self._rebuild_display()

        self._on_frame_configure()

    def delete(self, index):
        """Delete item at index"""
        if 0 <= index < len(self.items):
            item = self.items.pop(index)
            item['frame'].destroy()
            self._on_frame_configure()

    def get_checked_indices(self):
        """Get indices of checked items"""
        return [i for i, item in enumerate(self.items) if item['var'].get()]

    def get_checked_items(self):
        """Get checked item data"""
        return [item for item in self.items if item['var'].get()]

    def clear(self):
        """Clear all items"""
        for item in self.items:
            item['frame'].destroy()
        self.items.clear()
        self._on_frame_configure()

    def size(self):
        """Get number of items"""
        return len(self.items)

    def get_item(self, index):
        """Get item data at index"""
        if 0 <= index < len(self.items):
            return self.items[index]
        return None

    def get_all_items(self):
        """Get all items in current order"""
        return self.items

    def update_item(self, index, text):
        """Update item text"""
        if 0 <= index < len(self.items):
            self.items[index]['text'] = text
            self.items[index]['label'].config(text=text)

    def _on_check_changed(self, item_id):
        """Callback when checkbox state changes"""
        pass

    def _on_drag_start(self, event, item_id):
        """Start dragging"""
        for i, item in enumerate(self.items):
            if item['id'] == item_id:
                self.drag_data["index"] = i
                self.drag_data["widget"] = item['frame']
                item['frame'].config(relief=tk.SUNKEN, bg=self.theme['item_drag'])
                item['label'].config(bg=self.theme['item_drag'])
                item['checkbox'].config(bg=self.theme['item_drag'])
                break

    def _on_drag_motion(self, event):
        """Handle drag motion"""
        if self.drag_data["index"] is None:
            return

        # Get Y position relative to canvas
        canvas_y = self.canvas.canvasy(event.y_root - self.canvas.winfo_rooty())

        # Find target position
        for i, item in enumerate(self.items):
            widget_y = item['frame'].winfo_y()
            widget_height = item['frame'].winfo_height()

            if widget_y <= canvas_y <= widget_y + widget_height:
                if i != self.drag_data["index"]:
                    # Move item
                    moved_item = self.items.pop(self.drag_data["index"])
                    self.items.insert(i, moved_item)
                    self.drag_data["index"] = i
                    self._rebuild_display()
                break

    def _on_drag_release(self, event):
        """End dragging"""
        if self.drag_data["index"] is not None:
            item = self.items[self.drag_data["index"]]
            item['frame'].config(relief=tk.RAISED, bg=self.theme['item_bg'])
            item['label'].config(bg=self.theme['item_bg'])
            item['checkbox'].config(bg=self.theme['item_bg'])

            # Notify order changed
            if self.on_order_changed:
                self.on_order_changed()

        self.drag_data = {"index": None, "widget": None}

    def _rebuild_display(self):
        """Rebuild display order"""
        for item in self.items:
            item['frame'].pack_forget()
        for item in self.items:
            item['frame'].pack(fill=tk.X, padx=2, pady=1)
        self._on_frame_configure()


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
        self.reverse_order = True  # Default to newest first
        self.current_theme = 'light'  # Default theme

        # Setup window
        self.root.title(self.config.get('gui', 'window_title', default='EzySpeechTranslate Admin'))
        window_size = self.config.get('gui', 'window_size', default='1200x1000')
        self.root.geometry(window_size)

        # Authentication state
        self.authenticated = False

        # Create UI
        self.create_login_ui()

        # Start message queue processor
        self.process_queue()

    def create_login_ui(self):
        """Create login interface"""
        theme = THEMES[self.current_theme]

        self.root.configure(bg=theme['bg'])

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

    def toggle_theme(self):
        """Toggle between light and dark theme"""
        self.current_theme = 'dark' if self.current_theme == 'light' else 'light'
        self.apply_theme()
        self.log(f"Theme changed to: {self.current_theme}")

    def apply_theme(self):
        """Apply current theme to all widgets"""
        theme = THEMES[self.current_theme]

        # Update root window
        self.root.configure(bg=theme['bg'])

        # Update theme button
        theme_icon = '🌙' if self.current_theme == 'light' else '☀️'
        self.theme_button.config(text=theme_icon)

        # Update transcription listbox
        if hasattr(self, 'transcription_listbox'):
            self.transcription_listbox.apply_theme(self.current_theme)

        # Update text widgets
        if hasattr(self, 'original_text'):
            self.original_text.config(bg=theme['text_bg'], fg=theme['text_fg'])
        if hasattr(self, 'corrected_text'):
            self.corrected_text.config(bg=theme['text_bg'], fg=theme['text_fg'])
        if hasattr(self, 'sys_text'):
            self.sys_text.config(bg=theme['text_bg'], fg=theme['text_fg'])
        if hasattr(self, 'log_text'):
            self.log_text.config(bg=theme['text_bg'], fg=theme['text_fg'])

    def on_order_changed(self):
        """Callback when listbox order changes (after drag & drop)"""
        # Get current order from listbox
        current_items = self.transcription_listbox.get_all_items()

        # Update translations list to match new order
        new_translations = []
        for item in current_items:
            new_translations.append(item['data'])

        self.translations = new_translations

        # Sync order to backend/frontend
        self.sync_order_to_server()
        self.log("Order changed and synced to server")

    def sync_order_to_server(self):
        """Synchronize current order to server"""
        if self.socket and self.socket.connected:
            try:
                # Send complete ordered list to server
                self.socket.emit('update_order', {
                    'translations': self.translations
                })
                logger.info(f"Order synced to server: {len(self.translations)} items")
            except Exception as e:
                logger.error(f"Failed to sync order: {e}")
                self.log(f"Failed to sync order: {e}")
        else:
            logger.warning("Socket not connected, cannot sync order")
            self.log("Socket not connected, cannot sync order")

    def create_main_ui(self):
        """Create main application interface"""
        theme = THEMES[self.current_theme]

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

        # Row 1: Audio controls
        ttk.Label(control_frame, text="Audio Device:").grid(row=0, column=0, padx=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(control_frame, textvariable=self.device_var,
                                         width=30, state='readonly')
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

        # Theme toggle button
        theme_icon = '🌙' if self.current_theme == 'light' else '☀️'
        self.theme_button = ttk.Button(control_frame, text=theme_icon,
                                       command=self.toggle_theme, width=3)
        self.theme_button.grid(row=0, column=5, padx=5)

        # Row 2: List controls
        ttk.Button(control_frame, text="➕ Add New",
                  command=self.add_new_item).grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Button(control_frame, text="🗑️ Delete Selected",
                  command=self.delete_selected).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        ttk.Button(control_frame, text="✏️ Edit Selected",
                  command=self.edit_selected).grid(row=1, column=2, padx=5, pady=5, sticky=tk.W)

        # Sort order button
        self.sort_button = ttk.Button(control_frame, text="🔽 Newest First",
                                      command=self.toggle_sort_order)
        self.sort_button.grid(row=1, column=3, padx=5, pady=5)

        # Clear and Export buttons
        ttk.Button(control_frame, text="Clear History",
                   command=self.clear_history).grid(row=1, column=4, padx=5, pady=5)
        ttk.Button(control_frame, text="Export",
                   command=self.export_translations).grid(row=1, column=5, padx=5, pady=5)

        # Main content area with notebook
        notebook = ttk.Notebook(main_frame)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Transcription tab
        transcription_frame = ttk.Frame(notebook, padding="10")
        notebook.add(transcription_frame, text="Transcriptions")

        # Transcription list
        list_container = ttk.Frame(transcription_frame)
        list_container.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        transcription_frame.grid_rowconfigure(0, weight=1)
        transcription_frame.grid_columnconfigure(0, weight=1)

        # Draggable listbox with order change callback
        self.transcription_listbox = DraggableListbox(
            list_container,
            theme=self.current_theme,
            on_order_changed=self.on_order_changed
        )
        self.transcription_listbox.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        list_container.grid_rowconfigure(0, weight=1)
        list_container.grid_columnconfigure(0, weight=1)

        # Correction & System area
        content_frame = ttk.Frame(transcription_frame)
        content_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(10, 0))
        transcription_frame.grid_rowconfigure(1, weight=1)
        transcription_frame.grid_columnconfigure(0, weight=1)

        # Correction panel (70%)
        correction_frame = ttk.LabelFrame(content_frame, text="Correction", padding=10)
        correction_frame.grid(row=0, column=0, sticky="nsew")
        content_frame.grid_columnconfigure(0, weight=7)
        content_frame.grid_rowconfigure(0, weight=1)

        ttk.Label(correction_frame, text="Original:").grid(row=0, column=0, sticky=tk.W, pady=(0, 2))
        self.original_text = scrolledtext.ScrolledText(correction_frame, height=8, width=60,
                                                       state='disabled', font=('Arial', 14),
                                                       bg=theme['text_bg'], fg=theme['text_fg'])
        self.original_text.grid(row=1, column=0, sticky="nsew", pady=(0, 5))

        ttk.Label(correction_frame, text="Corrected:").grid(row=2, column=0, sticky=tk.W, pady=(5, 2))
        self.corrected_text = scrolledtext.ScrolledText(correction_frame, height=8, width=60,
                                                        font=('Arial', 14),
                                                        bg=theme['text_bg'], fg=theme['text_fg'])
        self.corrected_text.grid(row=3, column=0, sticky="nsew", pady=(0, 5))

        button_frame = ttk.Frame(correction_frame)
        button_frame.grid(row=4, column=0, sticky="e", pady=(5, 0))
        ttk.Button(button_frame, text="Save Correction", command=self.save_correction).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=self.cancel_correction).pack(side=tk.LEFT, padx=5)

        correction_frame.grid_rowconfigure(1, weight=1)
        correction_frame.grid_rowconfigure(3, weight=1)
        correction_frame.grid_columnconfigure(0, weight=1)

        # System & Config panel (30%)
        sys_frame = ttk.LabelFrame(content_frame, text="System & Config", padding=10)
        sys_frame.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        content_frame.grid_columnconfigure(1, weight=3)

        self.sys_text = scrolledtext.ScrolledText(sys_frame, height=20, width=40, state='disabled',
                                                  font=('Consolas', 10),
                                                  bg=theme['text_bg'], fg=theme['text_fg'])
        self.sys_text.grid(row=0, column=0, sticky="nsew")
        sys_frame.grid_rowconfigure(0, weight=1)
        sys_frame.grid_columnconfigure(0, weight=1)

        # Init System Monitoring
        self.sys_monitor = SystemMonitor(update_callback=self.update_system_stats, interval=1.0)
        self.sys_monitor.start()

        # Log tab
        log_frame = ttk.Frame(notebook, padding="10")
        notebook.add(log_frame, text="Log")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=20, width=100,
                                                  bg=theme['text_bg'], fg=theme['text_fg'])
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.grid_rowconfigure(0, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        self.log("Admin GUI initialized")

    def toggle_sort_order(self):
        """Toggle between newest first and oldest first"""
        self.reverse_order = not self.reverse_order

        if self.reverse_order:
            self.sort_button.config(text="🔽 Newest First")
        else:
            self.sort_button.config(text="🔼 Oldest First")

        self.refresh_listbox()
        self.sync_order_to_server()
        self.log(f"Sort order changed to: {'Newest First' if self.reverse_order else 'Oldest First'}")

    def refresh_listbox(self):
        """Rebuild listbox with current sort order"""
        self.transcription_listbox.clear()

        items_to_display = list(self.translations)
        if self.reverse_order:
            items_to_display.reverse()

        for item in items_to_display:
            display_text = f"[{item['timestamp']}] {item['corrected']}"
            if item.get('is_corrected'):
                display_text += " ✓"

            self.transcription_listbox.insert('end', {
                'id': item['id'],
                'text': display_text,
                'data': item
            })

    def add_new_item(self):
        """Add new transcription item manually"""
        theme = THEMES[self.current_theme]

        dialog = tk.Toplevel(self.root)
        dialog.title("Add New Transcription")
        dialog.geometry("600x250")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=theme['bg'])

        ttk.Label(dialog, text="Enter transcription text:", font=('Arial', 12)).pack(pady=10)

        text_widget = scrolledtext.ScrolledText(dialog, height=6, width=60, font=('Arial', 12),
                                               bg=theme['text_bg'], fg=theme['text_fg'])
        text_widget.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)
        text_widget.focus()

        def save_new():
            text = text_widget.get(1.0, tk.END).strip()
            if text:
                translation = {
                    'id': len(self.translations),
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'original': text,
                    'corrected': text,
                    'translated': None,
                    'is_corrected': False,
                    'source_language': 'manual'
                }
                self.translations.append(translation)
                self.refresh_listbox()
                self.sync_order_to_server()
                self.log(f"Manually added: {text[:50]}...")
                dialog.destroy()
            else:
                messagebox.showwarning("Warning", "Text cannot be empty")

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)
        ttk.Button(button_frame, text="Save", command=save_new).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=dialog.destroy).pack(side=tk.LEFT, padx=5)

    def delete_selected(self):
        """Delete selected items"""
        checked_items = self.transcription_listbox.get_checked_items()

        if not checked_items:
            messagebox.showwarning("Warning", "Please select items to delete")
            return

        if not messagebox.askyesno("Confirm", f"Delete {len(checked_items)} selected item(s)?"):
            return

        # Get IDs to delete
        ids_to_delete = [item['data']['id'] for item in checked_items]

        # Remove from translations
        self.translations = [t for t in self.translations if t['id'] not in ids_to_delete]

        # Refresh display
        self.refresh_listbox()
        self.cancel_correction()
        self.sync_order_to_server()

        self.log(f"Deleted {len(ids_to_delete)} items")

    def edit_selected(self):
        """Edit the first selected item"""
        checked_items = self.transcription_listbox.get_checked_items()

        if not checked_items:
            messagebox.showwarning("Warning", "Please select an item to edit")
            return

        if len(checked_items) > 1:
            messagebox.showinfo("Info", "Only the first selected item will be edited")

        item_data = checked_items[0]['data']

        # Populate correction fields
        self.original_text.config(state='normal')
        self.original_text.delete(1.0, tk.END)
        self.original_text.insert(1.0, item_data.get('original', ''))
        self.original_text.config(state='disabled')

        self.corrected_text.delete(1.0, tk.END)
        self.corrected_text.insert(1.0, item_data.get('corrected', ''))
        self.corrected_text.focus()

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

    def save_correction(self):
        """Save corrected transcription"""
        corrected_text = self.corrected_text.get(1.0, tk.END).strip()
        original_text = self.original_text.get(1.0, tk.END).strip()

        if not corrected_text:
            messagebox.showwarning("Warning", "Corrected text cannot be empty")
            return

        if not original_text:
            messagebox.showwarning("Warning", "No item selected")
            return

        # Find matching translation
        target_item = None
        for item in self.translations:
            if item['original'] == original_text:
                target_item = item
                break

        if not target_item:
            messagebox.showwarning("Warning", "Could not find matching transcription")
            return

        # Update translation
        target_item['corrected'] = corrected_text
        target_item['is_corrected'] = True

        # Send to server
        if self.socket:
            self.socket.emit('correct_translation', {
                'id': target_item['id'],
                'corrected_text': corrected_text
            })

        # Refresh display
        self.refresh_listbox()
        self.log(f"Correction saved for item {target_item['id']}")
        messagebox.showinfo("Success", "Correction saved and broadcasted")

    def cancel_correction(self):
        """Cancel correction"""
        self.corrected_text.delete(1.0, tk.END)
        self.original_text.config(state='normal')
        self.original_text.delete(1.0, tk.END)
        self.original_text.config(state='disabled')

    def update_system_stats(self, stats):
        """Update system and config info"""
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

        # Config values
        sample_rate = self.config.get('audio', 'sample_rate')
        block_duration = self.config.get('audio', 'block_duration')
        model_size = self.config.get('whisper', 'model_size')
        beam_size = self.config.get('whisper', 'beam_size')
        device = self.config.get('whisper', 'device')
        host = get_local_ip()
        port = self.config.get('server', 'port')

        # GPU Info
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

        # Construct info text
        info_text = (
            f"🕓 {stats.get('timestamp', '')}\n"
            f"───────────────────────────────\n"
            f"CPU     : {cpu.get('percent', 0):>5.1f}%   ({cpu.get('freq_current', 0):.1f}/{cpu.get('freq_max', 0):.1f} MHz)\n"
            f"Memory  : {mem.get('used', 0):>5.2f}/{mem.get('total', 0):.2f} GB  ({mem.get('percent', 0):.1f}%)\n"
            f"GPU(s)  :\n{gpu_info}\n"
            f"───────────────────────────────\n"
            f"Audio   : {sample_rate} Hz, {block_duration}s\n"
            f"Whisper : {model_size}, Beam={beam_size}\n"
            f"         Device={device}\n"
            f"Server  : {host}:{port}\n"
            f"Items   : {len(self.translations)}\n"
            f"Theme   : {self.current_theme.title()}\n"
        )

        # Update text widget
        self.sys_text.config(state='normal')
        self.sys_text.delete(1.0, tk.END)
        self.sys_text.insert(tk.END, info_text)
        self.sys_text.config(state='disabled')

    def clear_history(self):
        """Clear translation history"""
        if messagebox.askyesno("Confirm", "Clear all transcriptions?"):
            self.translations.clear()
            self.transcription_listbox.clear()
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

                    # Refresh display
                    self.refresh_listbox()

                    # Send to server (will also sync order)
                    if self.socket:
                        self.socket.emit('new_transcription', {
                            'text': text,
                            'language': language
                        })
                        # Sync complete order
                        self.sync_order_to_server()

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

        if hasattr(self, 'sys_monitor'):
            self.sys_monitor.stop()

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