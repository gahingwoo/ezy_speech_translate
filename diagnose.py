#!/usr/bin/env python3
"""
EzySpeechTranslate 诊断脚本
快速诊断和修复常见问题
"""

import sys
import subprocess
import platform


def print_section(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_python():
    print_section("检查 Python 环境")
    version = sys.version_info
    print(f"Python 版本: {version.major}.{version.minor}.{version.micro}")
    print(f"可执行文件: {sys.executable}")
    print(f"平台: {platform.system()} {platform.release()}")

    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 版本过低，需要 >= 3.8")
        return False
    print("✓ Python 版本符合要求")
    return True


def check_pyaudio():
    print_section("诊断 PyAudio")

    try:
        import pyaudio
        print("✓ PyAudio 已安装")

        # 测试音频设备
        audio = pyaudio.PyAudio()
        device_count = audio.get_device_count()
        print(f"✓ 找到 {device_count} 个音频设备")

        print("\n可用输入设备:")
        has_input = False
        for i in range(device_count):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                has_input = True
                print(f"  [{i}] {info['name']}")
                print(f"      通道: {info['maxInputChannels']}, 采样率: {int(info['defaultSampleRate'])} Hz")

        audio.terminate()

        if not has_input:
            print("\n❌ 没有找到可用的输入设备")
            print("\n解决方案:")
            print("1. 检查麦克风是否连接")
            print("2. 检查系统声音设置中是否启用了麦克风")
            print("3. 重启计算机后重试")
            return False

        return True

    except ImportError:
        print("❌ PyAudio 未安装")
        print("\n安装方法:")

        if platform.system() == "Windows":
            print("pip install pyaudio")
        elif platform.system() == "Darwin":  # macOS
            print("brew install portaudio")
            print("pip install pyaudio")
        else:  # Linux
            print("sudo apt-get install portaudio19-dev python3-pyaudio")
            print("pip install pyaudio")

        return False
    except Exception as e:
        print(f"❌ PyAudio 测试失败: {e}")
        return False


def check_whisper():
    print_section("诊断 Whisper")

    try:
        import whisper
        print("✓ Whisper 已安装")

        # 检查 FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✓ FFmpeg 已安装")
            else:
                print("⚠️  FFmpeg 可能未正确安装")
        except FileNotFoundError:
            print("❌ FFmpeg 未安装")
            print("\n安装方法:")
            if platform.system() == "Windows":
                print("下载: https://ffmpeg.org/download.html")
                print("或使用: choco install ffmpeg")
            elif platform.system() == "Darwin":
                print("brew install ffmpeg")
            else:
                print("sudo apt-get install ffmpeg")
            return False
        except subprocess.TimeoutExpired:
            print("⚠️  FFmpeg 响应超时")

        # 尝试加载模型
        print("\n测试加载 Whisper 模型...")
        print("(首次运行需要下载，请耐心等待...)")
        try:
            model = whisper.load_model("tiny")
            print("✓ Whisper 模型加载成功")
            return True
        except Exception as e:
            print(f"❌ 模型加载失败: {e}")
            return False

    except ImportError:
        print("❌ Whisper 未安装")
        print("\n安装方法:")
        print("pip install openai-whisper")
        return False


def check_flask():
    print_section("诊断 Flask 环境")

    packages = {
        'flask': 'Flask',
        'flask_socketio': 'Flask-SocketIO',
        'flask_cors': 'Flask-CORS',
        'socketio': 'Python-SocketIO',
        'eventlet': 'Eventlet',
    }

    all_ok = True
    for module, name in packages.items():
        try:
            __import__(module)
            print(f"✓ {name}")
        except ImportError:
            print(f"❌ {name} 未安装")
            all_ok = False

    if not all_ok:
        print("\n安装缺失的包:")
        print("pip install flask flask-socketio flask-cors python-socketio[client] eventlet")

    return all_ok


def check_translator():
    print_section("诊断翻译服务")

    try:
        from googletrans import Translator
        print("✓ googletrans 已安装")

        # 测试翻译
        print("\n测试翻译功能...")
        translator = Translator()
        result = translator.translate("Hello", src='en', dest='zh-cn')
        print(f"✓ 翻译测试成功: Hello -> {result.text}")
        return True

    except ImportError:
        print("❌ googletrans 未安装")
        print("\n安装方法:")
        print("pip install googletrans==4.0.0rc1")
        return False
    except Exception as e:
        print(f"⚠️  翻译测试失败: {e}")
        print("\n可能原因:")
        print("1. 网络连接问题")
        print("2. Google Translate API 访问受限")
        print("3. 需要更新 googletrans 版本")
        print("\n建议:")
        print("pip install --upgrade googletrans==4.0.0rc1")
        return False


def check_qt6():
    print_section("诊断 Qt6 环境")

    try:
        from PyQt6.QtWidgets import QApplication
        print("✓ PyQt6 已安装")

        # 测试创建应用
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        print("✓ Qt6 应用创建成功")
        return True

    except ImportError:
        print("❌ PyQt6 未安装")
        print("\n安装方法:")
        print("pip install PyQt6")
        return False
    except Exception as e:
        print(f"❌ Qt6 测试失败: {e}")
        return False


def check_server():
    print_section("检查后端服务")

    try:
        import requests
        response = requests.get('http://localhost:5000/api/status', timeout=3)

        if response.status_code == 200:
            status = response.json()
            print("✓ 后端服务正在运行")
            print(f"  系统就绪: {status.get('system_ready')}")
            print(f"  Whisper 加载: {status.get('whisper_loaded')}")
            print(f"  录制中: {status.get('is_recording')}")
            print(f"  历史记录: {status.get('history_count')} 条")
            return True
        else:
            print(f"⚠️  服务器响应异常: {response.status_code}")
            return False

    except ImportError:
        print("⚠️  requests 未安装")
        print("pip install requests")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 无法连接到后端服务")
        print("\n解决方案:")
        print("1. 启动后端: python app.py")
        print("2. 检查端口 5000 是否被占用")
        return False
    except Exception as e:
        print(f"❌ 检查服务失败: {e}")
        return False


def check_files():
    print_section("检查项目文件")

    import os

    files = {
        'app.py': '后端服务',
        'admin_gui.py': '管理界面',
        'requirements.txt': '依赖列表',
        'templates/index.html': '听众端网页',
    }

    all_ok = True
    for file, desc in files.items():
        if os.path.exists(file):
            size = os.path.getsize(file)
            print(f"✓ {file} ({size} bytes) - {desc}")
        else:
            print(f"❌ {file} - {desc} (缺失)")
            all_ok = False

    return all_ok


def auto_fix():
    print_section("尝试自动修复")

    print("1. 创建必要的目录...")
    import os
    os.makedirs('templates', exist_ok=True)
    print("   ✓ templates/ 目录已创建")

    print("\n2. 检查并安装缺失的包...")
    try:
        import subprocess
        result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'],
                                capture_output=True, text=True)
        if result.returncode == 0:
            print("   ✓ 依赖包安装完成")
        else:
            print(f"   ⚠️  部分包安装失败:\n{result.stderr}")
    except Exception as e:
        print(f"   ❌ 自动安装失败: {e}")


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║     EzySpeechTranslate 系统诊断工具                      ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)

    results = {}

    # 执行所有检查
    results['Python'] = check_python()
    results['PyAudio'] = check_pyaudio()
    results['Whisper'] = check_whisper()
    results['Flask'] = check_flask()
    results['Translator'] = check_translator()
    results['Qt6'] = check_qt6()
    results['Files'] = check_files()
    results['Server'] = check_server()

    # 生成报告
    print_section("诊断报告")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    print(f"\n通过: {passed}/{total}")
    print(f"失败: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 所有检查通过！系统可以正常使用。")
    else:
        print("\n⚠️  发现问题，请根据上述提示进行修复。")

        choice = input("\n是否尝试自动修复？(y/n): ")
        if choice.lower() == 'y':
            auto_fix()

    print("\n" + "=" * 60)
    print("诊断完成！")
    print("=" * 60)
    print("\n下一步操作:")
    if results['Server']:
        print("✓ 后端已运行，可以启动管理界面:")
        print("  python admin_gui.py")
    else:
        print("1. 启动后端服务:")
        print("   python app.py")
        print("\n2. 在新终端启动管理界面:")
        print("   python admin_gui.py")
        print("\n3. 在浏览器打开:")
        print("   http://localhost:5000")
    print("\n" + "=" * 60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n诊断被中断")
    except Exception as e:
        print(f"\n\n诊断出错: {e}")
        import traceback

        traceback.print_exc()