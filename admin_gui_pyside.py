"""
使用 PySide6 的管理界面（PyQt6 替代方案）
如果 PyQt6 有 DLL 问题，可以使用此版本
安装: pip install PySide6
"""

import sys
import requests
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QComboBox, QTextEdit,
                               QLabel, QTableWidget, QTableWidgetItem, QSplitter,
                               QMessageBox, QLineEdit)
from PySide6.QtCore import QTimer, Qt, Signal, QThread
from PySide6.QtGui import QColor
import socketio

import config


class SocketIOThread(QThread):
    """WebSocket 连接线程"""
    new_translation = Signal(dict)
    translation_corrected = Signal(dict)
    history_received = Signal(list)
    connection_status = Signal(bool)

    def __init__(self, server_url):
        super().__init__()
        self.server_url = server_url
        self.sio = socketio.Client()
        self.running = True

        @self.sio.on('connect')
        def on_connect():
            print('已连接到服务器')
            self.connection_status.emit(True)

        @self.sio.on('disconnect')
        def on_disconnect():
            print('与服务器断开连接')
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
            print(f'连接错误: {e}')
            self.connection_status.emit(False)

    def stop(self):
        self.running = False
        if self.sio.connected:
            self.sio.disconnect()


class AdminWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.server_url = f'http://localhost:{config.PORT}'
        self.is_recording = False
        self.socket_thread = None

        self.init_ui()
        self.load_devices()
        self.connect_to_server()

    def init_ui(self):
        self.setWindowTitle('EzySpeechTranslate - 管理员控制面板 (PySide6)')
        self.setGeometry(100, 100, 1400, 800)

        # 主窗口部件
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # 控制面板
        control_panel = self.create_control_panel()
        main_layout.addWidget(control_panel)

        # 分割器
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 左侧：实时预览
        preview_widget = self.create_preview_widget()
        splitter.addWidget(preview_widget)

        # 右侧：校对编辑区
        edit_widget = self.create_edit_widget()
        splitter.addWidget(edit_widget)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        main_layout.addWidget(splitter)

        # 状态栏
        self.statusBar().showMessage('就绪')

    def create_control_panel(self):
        """创建控制面板"""
        panel = QWidget()
        layout = QHBoxLayout(panel)

        # 音频设备选择
        layout.addWidget(QLabel('音频输入:'))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(300)
        layout.addWidget(self.device_combo)

        # 刷新设备按钮
        refresh_btn = QPushButton('🔄 刷新设备')
        refresh_btn.clicked.connect(self.load_devices)
        layout.addWidget(refresh_btn)

        layout.addSpacing(20)

        # 开始/停止按钮
        self.start_btn = QPushButton('▶ 开始录制')
        self.start_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 8px;')
        self.start_btn.clicked.connect(self.toggle_recording)
        layout.addWidget(self.start_btn)

        # 清空历史按钮
        clear_btn = QPushButton('🗑 清空历史')
        clear_btn.clicked.connect(self.clear_history)
        layout.addWidget(clear_btn)

        layout.addSpacing(20)

        # 连接状态
        self.status_label = QLabel('● 未连接')
        self.status_label.setStyleSheet('color: red; font-weight: bold;')
        layout.addWidget(self.status_label)

        layout.addStretch()

        return panel

    def create_preview_widget(self):
        """创建实时预览区"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel('实时翻译流:'))

        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setStyleSheet('font-size: 14px; background-color: #f5f5f5;')
        layout.addWidget(self.preview_text)

        return widget

    def create_edit_widget(self):
        """创建校对编辑区"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        layout.addWidget(QLabel('翻译历史与校对:'))

        # 表格
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(4)
        self.history_table.setHorizontalHeaderLabels(['时间', '英文原文', '中文翻译', '操作'])
        self.history_table.setColumnWidth(0, 150)
        self.history_table.setColumnWidth(1, 300)
        self.history_table.setColumnWidth(2, 300)
        self.history_table.setColumnWidth(3, 120)
        layout.addWidget(self.history_table)

        return widget

    def load_devices(self):
        """加载音频设备列表"""
        try:
            response = requests.get(f'{self.server_url}/api/devices', timeout=5)
            response.raise_for_status()
            devices = response.json()

            self.device_combo.clear()
            self.device_combo.addItem('默认设备', None)

            for device in devices:
                self.device_combo.addItem(
                    f"{device['name']} ({device['channels']}ch)",
                    device['index']
                )

            self.statusBar().showMessage(f'设备列表已更新 ({len(devices)} 个设备)')
        except requests.exceptions.ConnectionError:
            QMessageBox.critical(self, '连接错误',
                                 '无法连接到服务器！\n\n请确保后端服务正在运行:\npython app.py')
        except requests.exceptions.Timeout:
            QMessageBox.warning(self, '超时', '服务器响应超时，请重试')
        except requests.exceptions.JSONDecodeError:
            QMessageBox.critical(self, '数据错误',
                                 '服务器返回了无效的数据格式。\n\n可能的原因:\n1. 后端未正确启动\n2. 服务器返回了错误页面\n3. PyAudio 未正确安装')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法加载设备: {str(e)}')

    def connect_to_server(self):
        """连接到 WebSocket 服务器"""
        self.socket_thread = SocketIOThread(self.server_url)
        self.socket_thread.new_translation.connect(self.on_new_translation)
        self.socket_thread.translation_corrected.connect(self.on_translation_corrected)
        self.socket_thread.history_received.connect(self.on_history_received)
        self.socket_thread.connection_status.connect(self.on_connection_status)
        self.socket_thread.start()

    def toggle_recording(self):
        """切换录制状态"""
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
                    self.start_btn.setText('⏹ 停止录制')
                    self.start_btn.setStyleSheet('background-color: #f44336; color: white; padding: 8px;')
                    self.statusBar().showMessage('正在录制...')
                else:
                    QMessageBox.warning(self, '警告', response.json().get('error', '启动失败'))
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法启动录制: {str(e)}')
        else:
            try:
                requests.post(f'{self.server_url}/api/stop', timeout=5)
                self.is_recording = False
                self.start_btn.setText('▶ 开始录制')
                self.start_btn.setStyleSheet('background-color: #4CAF50; color: white; padding: 8px;')
                self.statusBar().showMessage('已停止录制')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法停止录制: {str(e)}')

    def clear_history(self):
        """清空历史记录"""
        reply = QMessageBox.question(
            self, '确认', '确定要清空所有历史记录吗？',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                requests.post(f'{self.server_url}/api/clear', timeout=5)
                self.history_table.setRowCount(0)
                self.preview_text.clear()
                self.statusBar().showMessage('历史已清空')
            except Exception as e:
                QMessageBox.critical(self, '错误', f'无法清空历史: {str(e)}')

    def on_new_translation(self, data):
        """处理新翻译"""
        preview_html = f"""
        <div style='margin: 10px; padding: 10px; background: white; border-left: 4px solid #2196F3;'>
            <p style='color: #666; font-size: 12px;'>{data['timestamp']}</p>
            <p style='margin: 5px 0;'><strong>EN:</strong> {data['english']}</p>
            <p style='margin: 5px 0; color: #2196F3;'><strong>CN:</strong> {data['chinese']}</p>
        </div>
        """
        self.preview_text.append(preview_html)

        scrollbar = self.preview_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

        self.add_row_to_table(data)

    def add_row_to_table(self, data):
        """添加行到表格"""
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)

        self.history_table.setItem(row, 0, QTableWidgetItem(data['timestamp']))
        self.history_table.setItem(row, 1, QTableWidgetItem(data['english']))

        chinese_item = QTableWidgetItem(data['corrected'])
        chinese_item.setData(Qt.ItemDataRole.UserRole, data['id'])
        self.history_table.setItem(row, 2, chinese_item)

        btn_widget = QWidget()
        btn_layout = QHBoxLayout(btn_widget)
        btn_layout.setContentsMargins(5, 2, 5, 2)

        save_btn = QPushButton('保存')
        save_btn.setStyleSheet('background-color: #2196F3; color: white;')
        save_btn.clicked.connect(lambda: self.save_correction(row))
        btn_layout.addWidget(save_btn)

        self.history_table.setCellWidget(row, 3, btn_widget)

    def save_correction(self, row):
        """保存校对"""
        chinese_item = self.history_table.item(row, 2)
        entry_id = chinese_item.data(Qt.ItemDataRole.UserRole)
        corrected_text = chinese_item.text()

        try:
            response = requests.post(
                f'{self.server_url}/api/correct',
                json={'id': entry_id, 'corrected': corrected_text},
                timeout=5
            )

            if response.status_code == 200:
                chinese_item.setBackground(QColor('#C8E6C9'))
                self.statusBar().showMessage(f'已保存第 {row + 1} 行的校对')
            else:
                QMessageBox.warning(self, '警告', '保存失败')
        except Exception as e:
            QMessageBox.critical(self, '错误', f'无法保存: {str(e)}')

    def on_translation_corrected(self, data):
        """处理翻译校对更新"""
        self.statusBar().showMessage(f'翻译已更新: ID {data["id"]}')

    def on_history_received(self, history):
        """接收历史记录"""
        self.history_table.setRowCount(0)
        for entry in history:
            self.add_row_to_table(entry)

    def on_connection_status(self, connected):
        """更新连接状态"""
        if connected:
            self.status_label.setText('● 已连接')
            self.status_label.setStyleSheet('color: green; font-weight: bold;')
        else:
            self.status_label.setText('● 未连接')
            self.status_label.setStyleSheet('color: red; font-weight: bold;')

    def closeEvent(self, event):
        """关闭窗口时清理"""
        if self.socket_thread:
            self.socket_thread.stop()
            self.socket_thread.wait()
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    window = AdminWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == '__main__':
    main()