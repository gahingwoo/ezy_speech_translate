"""
EzySpeechTranslate 系统测试脚本
用于检查所有依赖和功能是否正常
"""

import sys
import os

import config


def print_header(title):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_python_version():
    print_header("检查 Python 版本")
    version = sys.version_info
    print(f"Python {version.major}.{version.minor}.{version.micro}")

    if version.major >= 3 and version.minor >= 8:
        print("✓ Python 版本符合要求 (>= 3.8)")
        return True
    else:
        print("✗ Python 版本过低，需要 >= 3.8")
        return False


def test_imports():
    print_header("检查 Python 依赖包")

    packages = {
        'flask': 'Flask',
        'flask_socketio': 'Flask-SocketIO',
        'flask_cors': 'Flask-CORS',
        'whisper': 'OpenAI Whisper',
        'pyaudio': 'PyAudio',
        'googletrans': 'Google Translate',
        'numpy': 'NumPy',
        'socketio': 'Python-SocketIO',
    }

    results = {}
    for module, name in packages.items():
        try:
            __import__(module)
            print(f"✓ {name}")
            results[module] = True
        except ImportError:
            print(f"✗ {name} - 未安装")
            results[module] = False

    return all(results.values())


def test_qt6():
    print_header("检查 Qt6 依赖")

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import QTimer
        print("✓ PyQt6 已安装")
        return True
    except ImportError:
        print("✗ PyQt6 未安装")
        print("  安装命令: pip install PyQt6")
        return False


def test_audio_devices():
    print_header("检查音频设备")

    try:
        import pyaudio
        audio = pyaudio.PyAudio()

        input_devices = []
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                input_devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels']
                })

        if input_devices:
            print(f"✓ 找到 {len(input_devices)} 个输入设备:")
            for dev in input_devices:
                print(f"  [{dev['index']}] {dev['name']} ({dev['channels']}ch)")
            audio.terminate()
            return True
        else:
            print("✗ 未找到音频输入设备")
            audio.terminate()
            return False
    except Exception as e:
        print(f"✗ 音频设备检查失败: {e}")
        return False


def test_whisper_model():
    print_header("检查 Whisper 模型")

    try:
        import whisper
        print("正在加载 Whisper base 模型...")
        model = whisper.load_model("base")
        print("✓ Whisper 模型加载成功")

        # 测试转录
        import numpy as np
        test_audio = np.zeros(16000, dtype=np.float32)
        result = model.transcribe(test_audio)
        print("✓ Whisper 转录功能正常")
        return True
    except Exception as e:
        print(f"✗ Whisper 模型加载失败: {e}")
        return False


def test_translator():
    print_header("检查翻译服务")

    try:
        from googletrans import Translator
        translator = Translator()

        # 测试翻译
        result = translator.translate("Hello", src='en', dest='zh-cn')
        print(f"✓ Google Translate 正常")
        print(f"  测试翻译: Hello -> {result.text}")
        return True
    except Exception as e:
        print(f"✗ 翻译服务失败: {e}")
        print("  注意: Google Translate API 可能有访问限制")
        return False


def test_file_structure():
    print_header("检查文件结构")

    required_files = {
        'app.py': 'Flask 后端',
        'admin_gui.py': 'Qt6 管理界面',
        'requirements.txt': '依赖列表',
    }

    required_dirs = {
        'templates': '网页模板目录',
    }

    all_ok = True

    for file, desc in required_files.items():
        if os.path.exists(file):
            print(f"✓ {file} - {desc}")
        else:
            print(f"✗ {file} - {desc} (缺失)")
            all_ok = False

    for dir, desc in required_dirs.items():
        if os.path.isdir(dir):
            print(f"✓ {dir}/ - {desc}")
        else:
            print(f"⚠ {dir}/ - {desc} (缺失，将自动创建)")
            try:
                os.makedirs(dir, exist_ok=True)
                print(f"  已创建 {dir}/ 目录")
            except:
                all_ok = False

    # 检查 index.html
    if os.path.exists('templates/index.html'):
        print("✓ templates/index.html - 听众端网页")
    else:
        print("✗ templates/index.html - 听众端网页 (缺失)")
        all_ok = False

    return all_ok


def test_network():
    print_header("检查网络和端口")

    import socket

    # 检查端口是否可用
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('localhost', config.PORT))
    sock.close()

    if result == 0:
        print(f"⚠ 端口 {config.PORT} 已被占用")
        print("  建议: 关闭占用端口的程序或修改配置")
        return False
    else:
        print(f"✓ 端口 {config.PORT} 可用")
        return True


def generate_report(results):
    print_header("测试报告")

    total = len(results)
    passed = sum(results.values())

    print(f"\n总测试项: {total}")
    print(f"通过: {passed}")
    print(f"失败: {total - passed}")
    print(f"成功率: {passed / total * 100:.1f}%")

    if passed == total:
        print("\n🎉 所有测试通过！系统已准备就绪。")
        print("\n启动方法:")
        print("  1. 启动后端: python app.py")
        print("  2. 启动管理界面: python admin_gui.py")
        print(f"  3. 打开浏览器: http://localhost:{config.PORT}")
    else:
        print("\n⚠️  部分测试失败，请先解决上述问题。")
        print("\n常见问题解决:")
        print("  1. 依赖缺失: pip install -r requirements.txt")
        print("  2. 音频问题: 检查麦克风连接和系统权限")
        print("  3. 网络问题: 关闭占用端口的程序")


def main():
    print("=" * 60)
    print("  EzySpeechTranslate 系统测试")
    print("=" * 60)

    results = {
        'Python 版本': test_python_version(),
        'Python 依赖': test_imports(),
        'Qt6': test_qt6(),
        '音频设备': test_audio_devices(),
        'Whisper 模型': test_whisper_model(),
        '翻译服务': test_translator(),
        '文件结构': test_file_structure(),
        '网络端口': test_network(),
    }

    generate_report(results)

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n测试被中断")
    except Exception as e:
        print(f"\n\n测试出错: {e}")
        import traceback

        traceback.print_exc()