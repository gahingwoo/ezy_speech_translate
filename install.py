#!/usr/bin/env python3
"""
EzySpeechTranslate 安装向导
自动化安装和配置过程
"""

import sys
import os
import subprocess
import platform

import config


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║        EzySpeechTranslate 安装向导                       ║
║        版本 1.0.1                                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


def print_step(step, total, message):
    print(f"\n[{step}/{total}] {message}")
    print("-" * 60)


def run_command(cmd, description, shell=False):
    """执行命令并显示结果"""
    print(f"执行: {description}")
    try:
        result = subprocess.run(
            cmd,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode == 0:
            print("✓ 成功")
            if result.stdout:
                print(result.stdout[:200])  # 只显示前200字符
            return True
        else:
            print(f"✗ 失败 (返回码: {result.returncode})")
            if result.stderr:
                print(f"错误: {result.stderr[:500]}")
            return False

    except subprocess.TimeoutExpired:
        print("✗ 超时（可能需要更长时间）")
        return False
    except Exception as e:
        print(f"✗ 错误: {e}")
        return False


def check_python():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print(f"✗ Python 版本过低: {version.major}.{version.minor}")
        print("需要 Python 3.8 或更高版本")
        return False


def check_system_dependencies():
    """检查系统依赖"""
    system = platform.system()

    if system == "Linux":
        print("\n请确保已安装以下系统包:")
        print("  sudo apt-get install portaudio19-dev python3-dev ffmpeg")
        print("  或")
        print("  sudo yum install portaudio-devel python3-devel ffmpeg")

    elif system == "Darwin":  # macOS
        print("\n请确保已安装以下系统包:")
        print("  brew install portaudio ffmpeg")

    elif system == "Windows":
        print("\n请确保已安装 FFmpeg:")
        print("  下载: https://ffmpeg.org/download.html")
        print("  或使用: choco install ffmpeg")

    response = input("\n系统依赖是否已安装？(y/n): ")
    return response.lower() == 'y'


def create_venv():
    """创建虚拟环境"""
    if os.path.exists('venv'):
        print("虚拟环境已存在")
        return True

    return run_command(
        [sys.executable, '-m', 'venv', 'venv'],
        "创建虚拟环境"
    )


def get_pip_command():
    """获取 pip 命令"""
    if platform.system() == "Windows":
        return 'venv\\Scripts\\pip.exe'
    else:
        return 'venv/bin/pip'


def install_dependencies():
    """安装 Python 依赖"""
    pip_cmd = get_pip_command()

    # 升级 pip
    print("\n升级 pip...")
    run_command(
        [pip_cmd, 'install', '--upgrade', 'pip'],
        "升级 pip"
    )

    # 安装依赖
    print("\n安装项目依赖...")
    return run_command(
        [pip_cmd, 'install', '-r', 'requirements.txt'],
        "安装所有依赖包（这可能需要几分钟）"
    )


def create_directories():
    """创建必要的目录"""
    dirs = ['templates', 'logs', 'exports']

    for d in dirs:
        try:
            os.makedirs(d, exist_ok=True)
            print(f"✓ 创建目录: {d}/")
        except Exception as e:
            print(f"✗ 创建目录 {d}/ 失败: {e}")
            return False

    return True


def download_whisper_model():
    """预下载 Whisper 模型"""
    print("\n预下载 Whisper 模型...")
    print("这将下载约 150MB 的数据，请耐心等待...")

    response = input("是否现在下载？(y/n，可以稍后自动下载): ")
    if response.lower() != 'y':
        print("跳过预下载，首次运行时会自动下载")
        return True

    # 使用虚拟环境的 Python
    if platform.system() == "Windows":
        python_cmd = 'venv\\Scripts\\python.exe'
    else:
        python_cmd = 'venv/bin/python'

    test_code = """
import whisper
print('下载 Whisper base 模型...')
model = whisper.load_model('base')
print('模型下载完成！')
"""

    return run_command(
        [python_cmd, '-c', test_code],
        "下载 Whisper 模型"
    )


def create_startup_scripts():
    """创建启动脚本快捷方式"""
    if platform.system() == "Windows":
        # 创建 Windows 批处理文件
        with open('start.bat', 'w', encoding='utf-8') as f:
            f.write('@echo off\n')
            f.write(' """venv\Scripts\\activate""" \n')
            f.write('python start.py \n')
        print("✓ 创建启动脚本: start.bat")

    else:
        # 创建 Unix shell 脚本
        with open('start.sh', 'w') as f:
            f.write('#!/bin/bash\n')
            f.write('./venv/bin/python start.py\n')
        os.chmod('start.sh', 0o755)
        print("✓ 创建启动脚本: start.sh")

    return True


def test_installation():
    """测试安装"""
    print("\n运行系统测试...")

    if platform.system() == "Windows":
        python_cmd = 'venv\\Scripts\\python.exe'
    else:
        python_cmd = 'venv/bin/python'

    if os.path.exists('test_system.py'):
        return run_command(
            [python_cmd, 'test_system.py'],
            "运行系统测试"
        )
    else:
        print("⚠️  测试脚本不存在，跳过测试")
        return True


def show_next_steps():
    """显示后续步骤"""
    print("\n" + "=" * 60)
    print("  安装完成！")
    print("=" * 60)

    print("\n📝 下一步操作:\n")

    if platform.system() == "Windows":
        print("方式一: 使用启动脚本")
        print("  双击运行: 启动系统.bat")
        print()
        print("方式二: 手动启动")
        print("  1. 启动后端:")
        print("     venv\\Scripts\\python.exe app.py")
        print()
        print("  2. 启动管理界面（新命令窗口）:")
        print("     venv\\Scripts\\python.exe admin_gui.py")
    else:
        print("方式一: 使用启动脚本")
        print("  ./启动系统.sh")
        print()
        print("方式二: 手动启动")
        print("  1. 启动后端:")
        print("     venv/bin/python app.py")
        print()
        print("  2. 启动管理界面（新终端）:")
        print("     venv/bin/python admin_gui.py")

    print("\n  3. 打开浏览器访问听众端:")
    print(f"     http://localhost:{config.PORT}")

    print("\n" + "=" * 60)
    print("\n💡 提示:")
    print("  - 首次运行会自动下载 Whisper 模型")
    print("  - 确保麦克风已连接并授予权限")
    print("  - 遇到问题请运行: python diagnose.py")
    print("\n" + "=" * 60 + "\n")


def main():
    print_banner()

    print("欢迎使用 EzySpeechTranslate 安装向导！")
    print("本向导将帮助您完成系统的安装和配置。\n")

    input("按 Enter 键继续...")

    total_steps = 8
    current_step = 0

    # 步骤 1: 检查 Python
    current_step += 1
    print_step(current_step, total_steps, "检查 Python 环境")
    if not check_python():
        print("\n安装终止：Python 版本不符合要求")
        return 1

    # 步骤 2: 检查系统依赖
    current_step += 1
    print_step(current_step, total_steps, "检查系统依赖")
    if not check_system_dependencies():
        print("\n请先安装系统依赖，然后重新运行安装向导")
        return 1

    # 步骤 3: 创建虚拟环境
    current_step += 1
    print_step(current_step, total_steps, "创建虚拟环境")
    if not create_venv():
        print("\n创建虚拟环境失败")
        return 1

    # 步骤 4: 安装依赖
    current_step += 1
    print_step(current_step, total_steps, "安装 Python 依赖")
    if not install_dependencies():
        print("\n⚠️  部分依赖安装失败，但可以继续")
        response = input("是否继续？(y/n): ")
        if response.lower() != 'y':
            return 1

    # 步骤 5: 创建目录
    current_step += 1
    print_step(current_step, total_steps, "创建项目目录")
    if not create_directories():
        print("\n创建目录失败")
        return 1

    # 步骤 6: 下载模型
    current_step += 1
    print_step(current_step, total_steps, "下载 Whisper 模型")
    download_whisper_model()

    # 步骤 7: 创建启动脚本
    current_step += 1
    print_step(current_step, total_steps, "创建启动脚本")
    create_startup_scripts()

    # 步骤 8: 测试安装
    current_step += 1
    print_step(current_step, total_steps, "测试安装")
    test_installation()

    # 显示后续步骤
    show_next_steps()

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n安装被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n安装出错: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)