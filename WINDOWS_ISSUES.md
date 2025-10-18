# Windows 常见问题解决指南

## 问题 1: PyQt6 DLL 加载失败

### 错误信息
```
ImportError: DLL load failed while importing QtCore: The specified procedure could not be found.
```

### 原因
PyQt6 在 Windows 上需要特定的 Visual C++ 运行库。

### 解决方案

#### 方案 A: 安装 Visual C++ Redistributable（推荐）

1. **下载并安装 Visual C++ Redistributable**
   - 下载地址: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - 双击运行安装程序
   - 重启计算机

2. **重新安装 PyQt6**
   ```cmd
   pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip
   pip cache purge
   pip install PyQt6
   ```

3. **测试**
   ```cmd
   python -c "from PyQt6.QtWidgets import QApplication; print('OK')"
   ```

#### 方案 B: 使用 PySide6 替代（最简单）

PySide6 是 Qt 官方的 Python 绑定，通常在 Windows 上更稳定。

1. **安装 PySide6**
   ```cmd
   pip install PySide6
   ```

2. **使用 PySide6 版本的管理界面**
   ```cmd
   python admin_gui_pyside.py
   ```

#### 方案 C: 使用自动修复脚本

```cmd
python fix_common_issues.py
```
选择选项 `6` 或 `8`

### 验证修复

```cmd
# 测试 PyQt6
python -c "from PyQt6 import QtCore; print('PyQt6 OK')"

# 或测试 PySide6  
python -c "from PySide6 import QtCore; print('PySide6 OK')"
```

---

## 问题 2: SocketIO async_mode 错误

### 错误信息
```
ValueError: Invalid async_mode specified
```

### 解决方案

```cmd
# 卸载冲突的包
pip uninstall -y eventlet

# 安装正确的依赖
pip install simple-websocket

# 升级 flask-socketio
pip install --upgrade flask-socketio
```

---

## 问题 3: PyAudio 安装失败

### 错误信息
```
error: Microsoft Visual C++ 14.0 or greater is required
```

### 解决方案 A: 使用预编译的 Wheel

```cmd
# 下载预编译的 PyAudio wheel
# 访问: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

# 选择对应 Python 版本的文件，例如:
# PyAudio‑0.2.14‑cp39‑cp39‑win_amd64.whl (Python 3.9, 64位)

# 安装下载的 wheel 文件
pip install PyAudio‑0.2.14‑cp39‑cp39‑win_amd64.whl
```

### 解决方案 B: 使用 pipwin

```cmd
pip install pipwin
pipwin install pyaudio
```

---

## 问题 4: FFmpeg 未找到

### 错误信息
```
FileNotFoundError: [WinError 2] The system cannot find the file specified
```

### 解决方案

#### 方法 1: 使用 Chocolatey (推荐)

```cmd
# 1. 安装 Chocolatey (管理员权限)
# 访问: https://chocolatey.org/install

# 2. 安装 FFmpeg
choco install ffmpeg

# 3. 验证
ffmpeg -version
```

#### 方法 2: 手动安装

1. **下载 FFmpeg**
   - 访问: https://www.gyan.dev/ffmpeg/builds/
   - 下载 `ffmpeg-release-essentials.7z`

2. **解压到固定位置**
   ```
   解压到: C:\ffmpeg
   ```

3. **添加到系统 PATH**
   - 右键"此电脑" → "属性"
   - "高级系统设置" → "环境变量"
   - 编辑"Path"，添加: `C:\ffmpeg\bin`

4. **验证**
   ```cmd
   ffmpeg -version
   ```

---

## 问题 5: 端口 5000 被占用

### 错误信息
```
OSError: [WinError 10048] Only one usage of each socket address is normally permitted
```

### 解决方案

#### 查找占用进程

```cmd
netstat -ano | findstr :5000
```

#### 结束进程

```cmd
# 假设 PID 是 1234
taskkill /PID 1234 /F
```

#### 或修改端口

编辑 `app.py` 最后一行:
```python
socketio.run(app, host='0.0.0.0', port=5001, debug=False)
```

---

## 问题 6: 麦克风权限问题

### 症状
- 找不到音频设备
- 录制时无声音

### 解决方案

1. **检查 Windows 隐私设置**
   - 设置 → 隐私和安全性 → 麦克风
   - 确保"允许应用访问麦克风"已开启
   - 确保允许桌面应用访问麦克风

2. **检查麦克风是否工作**
   - 右键任务栏音量图标 → "声音设置"
   - 输入 → 测试麦克风

3. **在应用中重新选择设备**
   - 启动管理界面
   - 点击"刷新设备"
   - 选择正确的麦克风

---

## 问题 7: 虚拟声卡设置（捕获系统音频）

### 使用 VB-CABLE

1. **下载并安装**
   - 访问: https://vb-audio.com/Cable/
   - 下载 "VBCABLE_Driver_Pack43.zip"
   - 解压并运行 `VBCABLE_Setup_x64.exe`（管理员权限）

2. **配置**
   - 右键任务栏音量图标 → "声音设置"
   - 输出设备选择: "CABLE Input"
   - 这样系统音频会被发送到虚拟声卡

3. **在应用中使用**
   - 管理界面中选择: "CABLE Output"
   - 开始录制

4. **同时听到音频**（可选）
   - 打开"控制面板" → "声音"
   - "录制"标签 → 右键"CABLE Output" → "属性"
   - "侦听"标签 → 勾选"侦听此设备"
   - 选择您的扬声器/耳机

---

## 完整诊断和修复流程

### 步骤 1: 运行诊断

```cmd
python diagnose.py
```

### 步骤 2: 使用自动修复

```cmd
python fix_common_issues.py
```

### 步骤 3: 使用跨平台启动脚本

为了避免批处理文件的编码问题，推荐使用 Python 启动脚本：

```cmd
python start.py
```

这个脚本：
- ✅ 自动创建虚拟环境
- ✅ 自动安装依赖
- ✅ 完美支持中文显示
- ✅ 提供友好的菜单界面
- ✅ 自动选择可用的 GUI 框架（PyQt6 或 PySide6）

---

## 推荐配置（Windows）

### 完整安装流程

1. **安装 Python 3.9+**
   - 下载: https://www.python.org/downloads/
   - 安装时勾选 "Add Python to PATH"

2. **安装 Visual C++ Redistributable**
   - 下载: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - 运行安装

3. **安装 FFmpeg**
   ```cmd
   choco install ffmpeg
   ```
   或手动下载: https://www.gyan.dev/ffmpeg/builds/

4. **运行安装向导**
   ```cmd
   python install.py
   ```

5. **启动系统**
   ```cmd
   python start.py
   ```

---

## 故障排除速查表

| 问题 | 快速解决 |
|------|---------|
| PyQt6 DLL 错误 | `pip install PySide6` 然后用 `admin_gui_pyside.py` |
| SocketIO 错误 | `pip uninstall eventlet && pip install simple-websocket` |
| PyAudio 错误 | 使用 pipwin: `pip install pipwin && pipwin install pyaudio` |
| FFmpeg 未找到 | `choco install ffmpeg` 或手动下载 |
| 端口占用 | `netstat -ano | findstr :5000` 然后 `taskkill` |
| 中文乱码 | 使用 `python start.py` 而不是批处理文件 |

---

## 常用命令

```cmd
# 诊断系统
python diagnose.py

# 修复问题
python fix_common_issues.py

# 启动系统
python start.py

# 测试安装
python test_system.py
```

---