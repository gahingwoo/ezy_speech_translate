#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EzySpeechTranslate - Bilingual Admin Interface (EN/CN)
管理员控制面板 - 双语界面（英文/中文）
"""

import sys
import requests
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QComboBox, QTextEdit,
                             QLabel, QTableWidget, QTableWidgetItem, QSplitter,
                             QMessageBox)
from PyQt6.QtCore import QTimer, Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor
import socketio

# Language strings
LANG = {
    'en': {
        'title': 'EzySpeechTranslate - Admin Control Panel',
        'audio_input': 'Audio Input:',
        'refresh_devices': '🔄 Refresh Devices',
        'start_recording': '▶ Start Recording',
        'stop_recording': '⏹ Stop Recording',
        'clear_history': '🗑 Clear History',
        'connected': '● Connected',
        'disconnected': '● Disconnected',
        'ready': 'Ready',
        'recording': 'Recording...',
        'preview_title': 'Real-time Translation Stream:',
        'history_title': 'Translation History & Correction:',
        'time': 'Time',
        'english_source': 'English Source',
        'translation': 'Translation',
        'actions': 'Actions',
        'save': 'Save',
        'default_device': 'Default Device',
        'devices_updated': 'Device list updated',
        'devices_count': 'devices',
        'connection_error': 'Connection Error',
        'connection_error_msg': 'Cannot connect to server!\n\nPlease ensure backend is running:\npython app_multilang.py',
        'timeout': 'Timeout',
        'timeout_msg': 'Server response timeout, please retry',
        'data_error': 'Data Error',
        'data_error_msg': 'Server returned invalid data format.\n\nPossible reasons:\n1. Backend not started correctly\n2. Server returned error page\n3. PyAudio not installed correctly',
        'error': 'Error',
        'load_devices_error': 'Failed to load devices',
        'start_error': 'Failed to start recording',
        'stop_error': 'Failed to stop recording',
        'already_recording': 'Already recording',
        'warning': 'Warning',
        'start_failed': 'Start failed',
        'stopped_recording': 'Recording stopped',
        'confirm': 'Confirm',
        'clear_confirm': 'Are you sure to clear all history?',
        'history_cleared': 'History cleared',
        'clear_error': 'Failed to clear history',
        'save_success': 'Correction saved',
        'save_failed': 'Save failed',
        'translation_updated': 'Translation updated: ID',
    },
    'cn': {
        'title': 'EzySpeechTranslate - 管理员控制面板',
        'audio_input': '音频输入:',
        'refresh_devices': '🔄 刷新设备',
        'start_recording': '▶ 开始录制',
        'stop_recording': '⏹ 停止录制',
        'clear_history': '🗑 清空历史',
        'connected': '● 已连接',
        'disconnected': '● 未连接',
        'ready': '就绪',
        'recording': '正在录制...',
        'preview_title': '实时翻译流:',
        'history_title': '翻译历史与校对:',
        'time': '时间',
        'english_source': '英文原文',
        'translation': '翻译',
        'actions': '操作',
        'save': '保存',
        'default_device': '默认设备',
        'devices_updated': '设备列表已更新',
        'devices_count': '个设备',
        'connection_error': '连接错误',
        'connection_error_msg': '无法连接到服务器！\n\n请确保后端服务正在运行:\npython app_multilang.py',
        'timeout': '超时',
        'timeout_msg': '服务器响应超时，请重试',
        'data_error': '数据错误',
        'data_error_msg': '服务器返回了无效的数据格式。\n\n可能的原因:\n1. 后端未正确启动\n2. 服务器返回了错误页面\n3. PyAudio 未正确安装',
        'error': '错误',
        'load_devices_error': '无法加载设备',
        'start_error': '无法启动录制',
        'stop_error': '无法停止录制',
        'already_recording': '已在录制中',
        'warning': '警告',
        'start_failed': '启动失败',
        'stopped_recording': '已停止录制',
        'confirm': '确认',
        'clear_confirm': '确定要清空所有历史记录吗？',
        'history_cleared': '历史已清空',
        'clear_error': '无法清空历史',
        'save_success': '已保存校对',
        'save_failed': '保存失败',
        'translation_updated': '翻译已更新: ID',
    }
}


class SocketIOThread(QThread):
    """WebSocket connection thread"""
    new_translation = pyqtSignal(dict)
    translation_corrected = pyqtSignal(dict)
    history_received = pyqtSignal(list)
    connection_status = pyqtSignal(bool)

    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url
        self.sio = socketio.Client()
        self.running = True

        @self.sio.on('connect')
        def on_connect():
            print('Connected to server / 已连接到服务器')
            self.connection_status.emit(True)

        @self.sio.on('disconnect')
        def on_disconnect():
            print('Disconnected from server / 与服务器断开连接')
            self.connection_status.emit(False)

        @self.sio.on('new_translation')
        def on_new_translation(data):
            self.new_translation.emit(data)

        @self.sio.on('translation_corrected')
        def on_translation_corrected(data):
            self.translation_corrected.emit(data)

        @self.sio.on('history')
        def on_history(data):
            self.history_received.emit(data)

    def run(self):
        try:
            self.sio.connect(self.server_url)
            while self.running:
                self.sio.sleep(0.1)
        except Exception as e:
            print(f'Connection error / 连接错误: {e}')
            self.connection_status.emit(False)

    def stop(self):
        self.running = False
        if self.sio.connected:
            self.sio.disconnect()


class AdminWindow(QMainWindow):
    def __init__(self, lang='en'):
        super().__init__()
        self.lang = lang
        self.t = LANG[lang]  # Translation strings
        self.server_url = 'http://localhost:5000'
        self.is_recording = False
        self.socket_thread = None

        self.init_ui()
        self.load_devices()
        self.connect_to_server()

    def init_ui(self):
        self.setWindowTitle(self.t['title'])
        self.setGeometry(100, 100, 1400, 800)

        # Main widget
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Control panel
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: Real-time preview
        preview_widget = self.create_preview_widget()
        splitter.addWidget(preview_widget)

        # Right: Correction editor
        edit_widget = self.create_edit_widget()
        splitter.addWidget(edit_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # Status bar
        self.statusBar().showMessage(self.t['ready'])

    def create_control_panel(self):
        """Create control panel"""
        panel = QWidget()
        layout = QHBoxLayout(panel)

        # Language switcher
        self.lang_combo = QComboBox()
        self.lang_combo.addItem('English', 'en')
        self.lang_combo.addItem('中文', 'cn')
        self.lang_combo.setCurrentIndex(0 if self.lang == 'en' else 1)
        self.lang_combo.currentIndexChanged.connect(self.switch_language)
        layout.addWidget(self.lang_combo)

        layout.addSpacing(20)

        # Audio device selection
        layout.addWidget(QLabel(self.t['audio_input']))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        layout.addWidget(self.device_combo)

        # Refresh devices button
        refresh_btn = QPushButton(self.t['refresh_devices'])
        refresh_btn.clicked.connect(self.load_devices)
        layout.addWidget(refresh_btn)

        layout.addSpacing(20)

        # Start/Stop button
        self.start_btn = QPushButton(self.t['start_recording'])
        self.start_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 8px;')
        self.start_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.start_btn)

        # Clear history button
        clear_btn = QPushButton(self.t['clear_history'])
        clear_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_btn)

        layout.addSpacing(20)

        # Connection status
        self.status_label = QLabel(self.t['disconnected'])
        self.status_label.setStyleSheet('color: red; font-weight: bold;')
        layout.addWidget(self.status_label)

        layout.addStretch()

        return panel

    def create_preview_widget(self):
        """Create real-time preview area"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(self.t['preview_title']))

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet('font-size: 14px; background-color: #f5f5f5;')
        layout.addWidget(self.preview_text)

        return widget

    def create_edit_widget(self):
        """Create correction editor area"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel(self.t['history_title']))

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels([
            self.t['time'],
            self.t['english_source'],
            self.t['translation'],
            self.t['actions']
        ])
        self.history_table.setColumnWidth(0, 150)
        self.history_table.setColumnWidth(1, 300)
        self.history_table.setColumnWidth(2, 300)
        self.history_table.setColumnWidth(3, 120)
        layout.addWidget(self.history_table)

        return widget

    def switch_language(self, index):
        """Switch UI language"""
        new_lang = self.lang_combo.itemData(index)
        if new_lang != self.lang:
            reply = QMessageBox.question(
                self,
                'Switch Language / 切换语言',
                'Restart required to switch language.\nRestart now?\n\n需要重启以切换语言。\n现在重启？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Save preference and restart
                self.lang = new_lang
                QApplication.quit()
                import subprocess
                subprocess.Popen([sys.executable, __file__, '--lang', new_lang])

    def load_devices(self):
        """Load audio device list"""
        try:
            response = requests.get(f'{self.server_url}/api/devices', timeout=5)
            response.raise_for_status()
            devices = response.json()

            self.device_combo.clear()
            self.device_combo.addItem(self.t['default_device'], None)

            for device in devices:
                self.device_combo.addItem(
                    f"{device['name']} ({device['channels']}ch)",
                    device['index']
                )

            self.statusBar().showMessage(
                f'{self.t["devices_updated"]} ({len(devices)} {self.t["devices_count"]})'
            )
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, self.t['connection_error'],
                                 self.t['connection_error_msg'])
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, self.t['timeout'], self.t['timeout_msg'])
        except requests.exceptions.JSONDecodeError:
            QMessageBox.critical(self, self.t['data_error'], self.t['data_error_msg'])
        except Exception as e:
            QMessageBox.critical(self, self.t['error'],
                                 f'{self.t["load_devices_error"]}: {str(e)}')

    def connect_to_server(self):
        """Connect to WebSocket server"""
        self.socket_thread = SocketIOThread(self.server_url)
        self.socket_thread.new_translation.connect(self.on_new_translation)
        self.socket_thread.translation_corrected.connect(self.on_translation_corrected)
        self.socket_thread.history_received.connect(self.on_history_received)
        self.socket_thread.connection_status.connect(self.on_connection_status)
        self.socket_thread.start()

    def toggle_recording(self):
        """Toggle recording status"""
        if not self.is_recording:
            device_index = self.device_combo.currentData()
            try:
                response = requests.post(
                    f'{self.server_url}/api/start',
                    json={'device_index': device_index},
                    timeout=5
                )

                if response.status_code == 200:
                    self.is_recording = True
                    self.start_btn.setText(self.t['stop_recording'])
                    self.start_btn.setStyleSheet('background-color: #f44336; color: white; padding: 8px;')
                    self.statusBar().showMessage(self.t['recording'])
                else:
                    error_msg = response.json().get('error', self.t['start_failed'])
                    QMessageBox.warning(self, self.t['warning'], error_msg)
            except Exception as e:
                QMessageBox.critical(self, self.t['error'],
                                     f'{self.t["start_error"]}: {str(e)}')
        else:
            try:
                requests.post(f'{self.server_url}/api/stop', timeout=5)
                self.is_recording = False
                self.start_btn.setText(self.t['start_recording'])
                self.start_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 8px;')
                self.statusBar().showMessage(self.t['stopped_recording'])
            except Exception as e:
                QMessageBox.critical(self, self.t['error'],
                                     f'{self.t["stop_error"]}: {str(e)}')

    def clear_history(self):
        """Clear history records"""
        reply = QMessageBox.question(
            self, self.t['confirm'], self.t['clear_confirm'],
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                requests.post(f'{self.server_url}/api/clear', timeout=5)
                self.history_table.setRowCount(0)
                self.preview_text.clear()
                self.statusBar().showMessage(self.t['history_cleared'])
            except Exception as e:
                QMessageBox.critical(self, self.t['error'],
                                     f'{self.t["clear_error"]}: {str(e)}')

    def on_new_translation(self, data):
        """Handle new translation"""
        preview_html = f"""
        <div style='margin: 10px; padding: 10px; background: white; border-left: 4px solid #2196F3;'>
            <p style='color: #666; font-size: 12px;'>{data['timestamp']}</p>
            <p style='margin: 5px 0;'><strong>EN:</strong> {data['source']}</p>
        </div>
        """
        self.preview_text.append(preview_html)

        scrollbar = self.preview_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        self.add_row_to_table(data)

    def add_row_to_table(self, data):
        """Add row to table"""
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        self.history_table.setItem(row, 0, QTableWidgetItem(data['timestamp']))
        self.history_table.setItem(row, 1, QTableWidgetItem(data['source']))

        translation_item = QTableWidgetItem(data['corrected'])
        translation_item.setData(Qt.ItemDataRole.UserRole, data['id'])
        self.history_table.setItem(row, 2, translation_item)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(5, 2, 5, 2)

        save_btn = QPushButton(self.t['save'])
        save_btn.setStyleSheet('background-color: #2196F3; color: white;')
        save_btn.clicked.connect(lambda: self.save_correction(row))
        btn_layout.addWidget(save_btn)

        self.history_table.setCellWidget(row, 3, btn_widget)

    def save_correction(self, row):
        """Save correction"""
        translation_item = self.history_table.item(row, 2)
        entry_id = translation_item.data(Qt.ItemDataRole.UserRole)
        corrected_text = translation_item.text()

        try:
            response = requests.post(
                f'{self.server_url}/api/correct',
                json={'id': entry_id, 'corrected': corrected_text},
                timeout=5
            )

            if response.status_code == 200:
                translation_item.setBackground(QColor('#C8E6C9'))
                self.statusBar().showMessage(f'{self.t["save_success"]} #{row + 1}')
            else:
                QMessageBox.warning(self, self.t['warning'], self.t['save_failed'])
        except Exception as e:
            QMessageBox.critical(self, self.t['error'], f'{self.t["save_failed"]}: {str(e)}')

    def on_translation_corrected(self, data):
        """Handle translation correction update"""
        self.statusBar().showMessage(f'{self.t["translation_updated"]} {data["id"]}')

    def on_history_received(self, history):
        """Receive history records"""
        self.history_table.setRowCount(0)
        for entry in history:
            self.add_row_to_table(entry)

    def on_connection_status(self, connected):
        """Update connection status"""
        if connected:
            self.status_label.setText(self.t['connected'])
            self.status_label.setStyleSheet('color: green; font-weight: bold;')
        else:
            self.status_label.setText(self.t['disconnected'])
            self.status_label.setStyleSheet('color: red; font-weight: bold;')

    def closeEvent(self, event):
        """Cleanup on window close"""
        if self.socket_thread:
            self.socket_thread.stop()
            self.socket_thread.wait()
        event.accept()


def main():
    # Check for language argument
    lang = 'en'
    if '--lang' in sys.argv:
        idx = sys.argv.index('--lang')
        if idx + 1 < len(sys.argv):
            lang = sys.argv[idx + 1]

    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = AdminWindow(lang=lang)
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()