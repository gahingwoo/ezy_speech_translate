#!/usr/bin/env python3
"""
快速修复常见问题
"""

import sys
import subprocess
import os


def print_header(msg):
    print("\n" + "=" * 60)
    print(f"  {msg}")
    print("=" * 60)


def fix_socketio():
    """修复 SocketIO async_mode 问题"""
    print_header("修复 SocketIO 配置问题")

    print("问题: Invalid async_mode specified")
    print("解决方案: 重新安装正确的依赖...")

    commands = [
        "pip uninstall -y eventlet",
        "pip install simple-websocket",
        "pip install --upgrade flask-socketio",
    ]

    for cmd in commands:
        print(f"\n执行: {cmd}")
        try:
            subprocess.run(cmd.split(), check=True)
            print("✓ 成功")
        except Exception as e:
            print(f"✗ 失败: {e}")

    print("\n✓ SocketIO 依赖已修复")


def fix_pyqt6():
    """修复 PyQt6 DLL 问题"""
    print_header("修复 PyQt6 问题")

    import platform
    if platform.system() != "Windows":
        print("此问题仅在 Windows 上出现")
        return

    print("问题: DLL load failed while importing QtCore")
    print("解决方案: 重新安装 PyQt6...\n")

    try:
        # 完全卸载
        print("1. 卸载旧版本...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "PyQt6", "PyQt6-Qt6", "PyQt6-sip"],
                       capture_output=True)

        # 清理缓存
        print("2. 清理 pip 缓存...")
        subprocess.run([sys.executable, "-m", "pip", "cache", "purge"],
                       capture_output=True)

        # 重新安装
        print("3. 重新安装 PyQt6...")
        subprocess.run([sys.executable, "-m", "pip", "install", "PyQt6==6.6.1"],
                       check=True)

        print("\n✓ PyQt6 已重新安装")
        print("\n如果问题仍然存在，请尝试:")
        print("1. 安装 Visual C++ Redistributable:")
        print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("2. 重启计算机")
        print("3. 或使用 PySide6 替代: pip install PySide6")

    except Exception as e:
        print(f"✗ 自动修复失败: {e}")
        print("\n手动修复步骤:")
        print("1. 完全卸载:")
        print("   pip uninstall PyQt6 PyQt6-Qt6 PyQt6-sip")
        print("\n2. 安装 Visual C++ Redistributable:")
        print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
        print("\n3. 重新安装:")
        print("   pip install PyQt6")
        print("\n或使用 PySide6 (Qt 官方版本):")
        print("   pip install PySide6")


def fix_pyaudio():
    """修复 PyAudio 问题"""
    print_header("修复 PyAudio 问题")

    print("尝试重新安装 PyAudio...")

    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "pyaudio"],
                       capture_output=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "pyaudio"],
                       check=True)
        print("✓ PyAudio 重新安装成功")
    except Exception as e:
        print(f"✗ 自动修复失败: {e}")
        print("\n手动修复方法:")
        print("Windows:")
        print("  pip install pyaudio")
        print("\nmacOS:")
        print("  brew install portaudio")
        print("  pip install pyaudio")
        print("\nLinux:")
        print("  sudo apt-get install portaudio19-dev")
        print("  pip install pyaudio")


def fix_googletrans():
    """修复 Google Translate 问题"""
    print_header("修复 Google Translate")

    print("重新安装 googletrans...")

    try:
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "googletrans"],
                       capture_output=True)
        subprocess.run([sys.executable, "-m", "pip", "install", "googletrans==4.0.0rc1"],
                       check=True)
        print("✓ googletrans 重新安装成功")
    except Exception as e:
        print(f"✗ 失败: {e}")


def fix_whisper():
    """修复 Whisper 问题"""
    print_header("修复 Whisper")

    print("检查 FFmpeg...")
    try:
        result = subprocess.run(['ffmpeg', '-version'],
                                capture_output=True, timeout=5)
        if result.returncode == 0:
            print("✓ FFmpeg 已安装")
        else:
            print("✗ FFmpeg 未正确安装")
            print_ffmpeg_install_guide()
    except FileNotFoundError:
        print("✗ FFmpeg 未安装")
        print_ffmpeg_install_guide()
    except:
        pass


def print_ffmpeg_install_guide():
    """打印 FFmpeg 安装指南"""
    import platform
    system = platform.system()

    print("\nFFmpeg 安装方法:")
    if system == "Windows":
        print("1. 下载: https://ffmpeg.org/download.html")
        print("2. 解压到 C:\\ffmpeg")
        print("3. 添加 C:\\ffmpeg\\bin 到系统 PATH")
        print("或使用: choco install ffmpeg")
    elif system == "Darwin":
        print("brew install ffmpeg")
    else:
        print("sudo apt-get install ffmpeg")


def fix_templates():
    """修复模板文件问题"""
    print_header("检查模板文件")

    if not os.path.exists('templates'):
        print("创建 templates 目录...")
        os.makedirs('templates')
        print("✓ 已创建")
    else:
        print("✓ templates 目录已存在")

    if not os.path.exists('templates/index.html'):
        print("⚠️  templates/index.html 缺失")
        print("请确保从完整项目中复制 index.html 文件")
    else:
        print("✓ index.html 已存在")


def reinstall_all():
    """重新安装所有依赖"""
    print_header("重新安装所有依赖")

    if not os.path.exists('requirements.txt'):
        print("✗ 找不到 requirements.txt")
        return

    print("这将重新安装所有 Python 包...")
    choice = input("是否继续？(y/n): ")

    if choice.lower() != 'y':
        print("已取消")
        return

    try:
        print("\n卸载旧版本...")
        subprocess.run([sys.executable, "-m", "pip", "uninstall", "-y", "-r", "requirements.txt"],
                       capture_output=True)

        print("\n安装新版本...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
                       check=True)
        print("\n✓ 所有依赖重新安装完成")
    except Exception as e:
        print(f"\n✗ 安装失败: {e}")


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║           EzySpeechTranslate 快速修复工具               ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    print("请选择要修复的问题:\n")
    print("[1] 修复 SocketIO 错误 (Invalid async_mode)")
    print("[2] 修复 PyAudio 问题 (无法加载设备)")
    print("[3] 修复 Google Translate 错误")
    print("[4] 修复 Whisper/FFmpeg 问题")
    print("[5] 检查模板文件")
    print("[6] 重新安装所有依赖")
    print("[7] 修复所有常见问题（推荐）")
    print("[0] 退出")

    choice = input("\n请选择 (0-7): ")

    if choice == '1':
        fix_socketio()
    elif choice == '2':
        fix_pyaudio()
    elif choice == '3':
        fix_googletrans()
    elif choice == '4':
        fix_whisper()
    elif choice == '5':
        fix_templates()
    elif choice == '6':
        reinstall_all()
    elif choice == '7':
        print("\n开始修复所有问题...")
        fix_socketio()
        fix_pyaudio()
        fix_googletrans()
        fix_whisper()
        fix_templates()
        print("\n" + "=" * 60)
        print("  修复完成！")
        print("=" * 60)
    elif choice == '0':
        print("退出")
        return
    else:
        print("无效选择")
        return

    print("\n" + "=" * 60)
    print("建议：运行 python diagnose.py 验证修复结果")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已中断")
    except Exception as e:
        print(f"\n\n出错: {e}")
        import traceback

        traceback.print_exc()