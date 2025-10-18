#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EzySpeechTranslate 启动脚本
跨平台支持 Windows/Linux/macOS
"""

import sys
import os
import subprocess
import platform
import time
import signal


def print_banner():
    """打印欢迎横幅"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║           EzySpeechTranslate 启动器                      ║
║           实时语音翻译系统                                ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


def print_section(title):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 版本过低: {version.major}.{version.minor}.{version.micro}")
        print("需要 Python 3.8 或更高版本")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_venv():
    """检查并创建虚拟环境"""
    print_section("检查虚拟环境")

    if not os.path.exists('venv'):
        print("虚拟环境不存在，正在创建...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            print("✓ 虚拟环境创建成功")
            return True, True  # 存在, 新创建
        except Exception as e:
            print(f"❌ 创建虚拟环境失败: {e}")
            return False, False
    else:
        print("✓ 虚拟环境已存在")
        return True, False


def get_venv_python():
    """获取虚拟环境的 Python 路径"""
    system = platform.system()
    if system == "Windows":
        return os.path.join('venv', 'Scripts', 'python.exe')
    else:
        return os.path.join('venv', 'bin', 'python')


def get_venv_pip():
    """获取虚拟环境的 pip 路径"""
    system = platform.system()
    if system == "Windows":
        return os.path.join('venv', 'Scripts', 'pip.exe')
    else:
        return os.path.join('venv', 'bin', 'pip')


def install_dependencies(force=False):
    """安装依赖"""
    print_section("检查依赖")

    pip_path = get_venv_pip()
    marker_file = os.path.join('venv', '.installed')

    if os.path.exists(marker_file) and not force:
        print("✓ 依赖已安装")
        return True

    if not os.path.exists('requirements.txt'):
        print("❌ 找不到 requirements.txt")
        return False

    print("正在安装依赖包...")
    print("这可能需要几分钟时间，请耐心等待...\n")

    try:
        # 升级 pip
        subprocess.run([pip_path, 'install', '--upgrade', 'pip'],
                       capture_output=True)

        # 安装依赖
        result = subprocess.run([pip_path, 'install', '-r', 'requirements.txt'],
                                capture_output=False)

        if result.returncode == 0:
            # 创建标记文件
            with open(marker_file, 'w') as f:
                f.write('installed')
            print("\n✓ 依赖安装完成")
            return True
        else:
            print("\n⚠️  部分依赖安装失败")
            return False

    except Exception as e:
        print(f"\n❌ 安装失败: {e}")
        return False


def check_files():
    """检查必要文件"""
    print_section("检查项目文件")

    required_files = {
        'app.py': '后端服务',
        'requirements.txt': '依赖列表',
    }

    optional_files = {
        'admin_gui.py': 'PyQt6 管理界面',
        'admin_gui_pyside.py': 'PySide6 管理界面',
        'templates/index.html': '听众端网页',
    }

    all_ok = True

    for file, desc in required_files.items():
        if os.path.exists(file):
            print(f"✓ {file} - {desc}")
        else:
            print(f"❌ {file} - {desc} (缺失)")
            all_ok = False

    for file, desc in optional_files.items():
        if os.path.exists(file):
            print(f"✓ {file} - {desc}")
        else:
            print(f"⚠️  {file} - {desc} (缺失)")

    # 创建必要目录
    if not os.path.exists('templates'):
        print("创建 templates 目录...")
        os.makedirs('templates', exist_ok=True)

    return all_ok


def start_backend():
    """启动后端服务"""
    print_section("启动后端服务")
    print()
    print("Flask 后端正在启动...")
    print("服务地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务")
    print()

    python_path = get_venv_python()

    try:
        subprocess.run([python_path, 'app.py'])
    except KeyboardInterrupt:
        print("\n\n后端服务已停止")
    except Exception as e:
        print(f"\n❌ 启动失败: {e}")


def start_admin_gui():
    """启动管理界面"""
    print_section("启动管理员界面")
    print()

    python_path = get_venv_python()

    # 首先尝试 PyQt6
    if os.path.exists('admin_gui.py'):
        print("尝试启动 PyQt6 管理界面...")
        try:
            result = subprocess.run([python_path, '-c', 'import PyQt6'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✓ 使用 PyQt6 版本")
                subprocess.run([python_path, 'admin_gui.py'])
                return
            else:
                print("⚠️  PyQt6 不可用")
        except:
            print("⚠️  PyQt6 检查失败")

    # 尝试 PySide6
    if os.path.exists('admin_gui_pyside.py'):
        print("尝试启动 PySide6 管理界面...")
        try:
            result = subprocess.run([python_path, '-c', 'import PySide6'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✓ 使用 PySide6 版本")
                subprocess.run([python_path, 'admin_gui_pyside.py'])
                return
            else:
                print("⚠️  PySide6 不可用")
        except:
            print("⚠️  PySide6 检查失败")

    print("\n❌ 无可用的管理界面")
    print("请安装 PyQt6 或 PySide6:")
    print("  pip install PyQt6")
    print("  或")
    print("  pip install PySide6")


def start_both():
    """同时启动后端和管理界面"""
    print_section("启动完整系统")
    print()

    python_path = get_venv_python()
    backend_process = None

    try:
        # 启动后端（后台）
        print("1/2 启动后端服务（后台）...")
        backend_process = subprocess.Popen([python_path, 'app.py'],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)

        # 等待后端启动
        print("等待后端启动...")
        time.sleep(3)

        # 检查后端是否正常运行
        if backend_process.poll() is not None:
            print("❌ 后端启动失败")
            print("请先单独启动后端检查错误")
            return

        print("✓ 后端服务已启动")
        print()

        # 启动管理界面
        print("2/2 启动管理员界面...")
        start_admin_gui()

    except KeyboardInterrupt:
        print("\n\n正在停止服务...")
    finally:
        # 清理后端进程
        if backend_process:
            print("关闭后端服务...")
            if platform.system() == "Windows":
                backend_process.terminate()
            else:
                backend_process.send_signal(signal.SIGTERM)

            # 等待进程结束
            try:
                backend_process.wait(timeout=5)
                print("✓ 后端服务已关闭")
            except subprocess.TimeoutExpired:
                backend_process.kill()
                print("✓ 后端服务已强制关闭")


def run_diagnostics():
    """运行诊断"""
    print_section("运行系统诊断")
    print()

    if os.path.exists('diagnose.py'):
        python_path = get_venv_python()
        subprocess.run([python_path, 'diagnose.py'])
    else:
        print("❌ 找不到 diagnose.py")


def show_menu():
    """显示主菜单"""
    print_section("启动选项")
    print()
    print("[1] 启动后端服务")
    print("[2] 启动管理员界面")
    print("[3] 同时启动后端和管理界面（推荐）")
    print("[4] 运行系统诊断")
    print("[5] 重新安装依赖")
    print("[0] 退出")
    print()

    choice = input("请选择 (0-5): ").strip()
    return choice


def main():
    """主函数"""
    print_banner()

    # 检查 Python 版本
    if not check_python_version():
        input("\n按 Enter 键退出...")
        return 1

    # 检查虚拟环境
    venv_exists, is_new = check_venv()
    if not venv_exists:
        input("\n按 Enter 键退出...")
        return 1

    # 安装依赖
    if not install_dependencies(force=is_new):
        print("\n⚠️  依赖安装有问题，但可以继续")
        choice = input("是否继续？(y/n): ").strip().lower()
        if choice != 'y':
            return 1

    # 检查文件
    if not check_files():
        print("\n❌ 缺少必要文件")
        input("\n按 Enter 键退出...")
        return 1

    # 显示菜单并处理选择
    while True:
        choice = show_menu()

        if choice == '1':
            start_backend()
        elif choice == '2':
            start_admin_gui()
        elif choice == '3':
            start_both()
        elif choice == '4':
            run_diagnostics()
        elif choice == '5':
            install_dependencies(force=True)
        elif choice == '0':
            print("\n再见！")
            return 0
        else:
            print("\n❌ 无效选择，请重试")
            time.sleep(1)

        print("\n" + "=" * 60)
        input("按 Enter 键返回菜单...")
        print("\033[2J\033[H")  # 清屏（跨平台）


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n程序被中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n发生错误: {e}")
        import traceback

        traceback.print_exc()
        input("\n按 Enter 键退出...")
        sys.exit(1)