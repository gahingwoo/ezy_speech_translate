#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EzySpeechTranslate Startup Script
Cross-platform support for Windows/Linux/macOS
"""

import sys
import os
import subprocess
import platform
import time
import signal

import config


def print_banner():
    """Prints the welcome banner"""
    print("""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║             EzySpeechTranslate Launcher                  ║
║             Real-time Voice Translation System           ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
    """)


def print_section(title):
    """Prints a section title"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_python_version():
    """Checks the Python version"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python version too low: {version.major}.{version.minor}.{version.micro}")
        print("Python 3.8 or higher is required")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_venv():
    """Checks for and creates the virtual environment"""
    print_section("Checking Virtual Environment")

    if not os.path.exists('venv'):
        print("Virtual environment does not exist, creating...")
        try:
            subprocess.run([sys.executable, '-m', 'venv', 'venv'], check=True)
            print("✓ Virtual environment created successfully")
            return True, True  # Exists, Newly created
        except Exception as e:
            print(f"❌ Failed to create virtual environment: {e}")
            return False, False
    else:
        print("✓ Virtual environment already exists")
        return True, False


def get_venv_python():
    """Gets the path to the virtual environment's Python executable"""
    system = platform.system()
    if system == "Windows":
        return os.path.join('venv', 'Scripts', 'python.exe')
    else:
        return os.path.join('venv', 'bin', 'python')


def get_venv_pip():
    """Gets the path to the virtual environment's pip executable"""
    system = platform.system()
    if system == "Windows":
        return os.path.join('venv', 'Scripts', 'pip.exe')
    else:
        return os.path.join('venv', 'bin', 'pip')


def install_dependencies(force=False):
    """Installs dependencies"""
    print_section("Checking Dependencies")

    pip_path = get_venv_pip()
    marker_file = os.path.join('venv', '.installed')

    if os.path.exists(marker_file) and not force:
        print("✓ Dependencies already installed")
        return True

    if not os.path.exists('requirements.txt'):
        print("❌ requirements.txt not found")
        return False

    print("Installing dependency packages...")
    print("This may take a few minutes, please be patient...\n")

    try:
        # Upgrade pip
        subprocess.run([pip_path, 'install', '--upgrade', 'pip'],
                       capture_output=True)

        # Install dependencies
        result = subprocess.run([pip_path, 'install', '-r', 'requirements.txt'],
                                capture_output=False)

        if result.returncode == 0:
            # Create marker file
            with open(marker_file, 'w') as f:
                f.write('installed')
            print("\n✓ Dependencies installation complete")
            return True
        else:
            print("\n⚠️  Some dependencies failed to install")
            return False

    except Exception as e:
        print(f"\n❌ Installation failed: {e}")
        return False


def check_files():
    """Checks for necessary files"""
    print_section("Checking Project Files")

    required_files = {
        'app.py': 'Backend Service',
        'requirements.txt': 'Dependency List',
    }

    optional_files = {
        'admin_gui.py': 'PyQt6 Admin Interface',
        'admin_gui_pyside.py': 'PySide6 Admin Interface',
        'templates/index.html': 'Listener Web Page',
    }

    all_ok = True

    for file, desc in required_files.items():
        if os.path.exists(file):
            print(f"✓ {file} - {desc}")
        else:
            print(f"❌ {file} - {desc} (Missing)")
            all_ok = False

    for file, desc in optional_files.items():
        if os.path.exists(file):
            print(f"✓ {file} - {desc}")
        else:
            print(f"⚠️  {file} - {desc} (Missing)")

    # Create necessary directories
    if not os.path.exists('templates'):
        print("Creating templates directory...")
        os.makedirs('templates', exist_ok=True)

    return all_ok


def start_backend():
    """Starts the backend service"""
    print_section("Starting Backend Service")
    print()
    print("Flask backend is starting...")
    print(f"Service Address: http://localhost:{config.PORT}")
    print("Press Ctrl+C to stop the service")
    print()

    python_path = get_venv_python()

    try:
        subprocess.run([python_path, 'app.py'])
    except KeyboardInterrupt:
        print("\n\nBackend service stopped")
    except Exception as e:
        print(f"\n❌ Startup failed: {e}")


def start_admin_gui():
    """Starts the admin interface"""
    print_section("Starting Admin Interface")
    print()

    python_path = get_venv_python()

    # First attempt PyQt6
    if os.path.exists('admin_gui.py'):
        print("Attempting to start PyQt6 Admin Interface...")
        try:
            result = subprocess.run([python_path, '-c', 'import PyQt6'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✓ Using PyQt6 version")
                subprocess.run([python_path, 'admin_gui.py'])
                return
            else:
                print("⚠️  PyQt6 not available")
        except:
            print("⚠️  PyQt6 check failed")

    # Attempt PySide6
    if os.path.exists('admin_gui_pyside.py'):
        print("Attempting to start PySide6 Admin Interface...")
        try:
            result = subprocess.run([python_path, '-c', 'import PySide6'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✓ Using PySide6 version")
                subprocess.run([python_path, 'admin_gui_pyside.py'])
                return
            else:
                print("⚠️  PySide6 not available")
        except:
            print("⚠️  PySide6 check failed")

    print("\n❌ No admin interface available")
    print("Please install PyQt6 or PySide6:")
    print("  pip install PyQt6")
    print("  or")
    print("  pip install PySide6")


def start_both():
    """Starts both the backend and the admin interface simultaneously"""
    print_section("Starting Full System")
    print()

    python_path = get_venv_python()
    backend_process = None

    try:
        # Start backend (in background)
        print("1/2 Starting backend service (background)...")
        backend_process = subprocess.Popen([python_path, 'app.py'],
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE)

        # Wait for backend to start
        print("Waiting for backend to start...")
        time.sleep(3)

        # Check if backend is running normally
        if backend_process.poll() is not None:
            print("❌ Backend failed to start")
            print("Please try starting the backend separately to check for errors")
            return

        print("✓ Backend service started")
        print()

        # Start admin interface
        print("2/2 Starting admin interface...")
        start_admin_gui()

    except KeyboardInterrupt:
        print("\n\nStopping services...")
    finally:
        # Clean up backend process
        if backend_process:
            print("Shutting down backend service...")
            if platform.system() == "Windows":
                backend_process.terminate()
            else:
                backend_process.send_signal(signal.SIGTERM)

            # Wait for process to end
            try:
                backend_process.wait(timeout=5)
                print("✓ Backend service shut down")
            except subprocess.TimeoutExpired:
                backend_process.kill()
                print("✓ Backend service forcibly shut down")


def run_diagnostics():
    """Runs diagnostics"""
    print_section("Running System Diagnostics")
    print()

    if os.path.exists('diagnose.py'):
        python_path = get_venv_python()
        subprocess.run([python_path, 'diagnose.py'])
    else:
        print("❌ diagnose.py not found")


def show_menu():
    """Displays the main menu"""
    print_section("Startup Options")
    print()
    print("[1] Start Backend Service")
    print("[2] Start Admin Interface")
    print("[3] Start Both Backend and Admin Interface (Recommended)")
    print("[4] Run System Diagnostics")
    print("[5] Reinstall Dependencies")
    print("[0] Exit")
    print()

    choice = input("Please select (0-5): ").strip()
    return choice


def main():
    """Main function"""
    print_banner()

    # Check Python version
    if not check_python_version():
        input("\nPress Enter to exit...")
        return 1

    # Check virtual environment
    venv_exists, is_new = check_venv()
    if not venv_exists:
        input("\nPress Enter to exit...")
        return 1

    # Install dependencies
    if not install_dependencies(force=is_new):
        print("\n⚠️  There was an issue with dependency installation, but you may continue")
        choice = input("Do you want to continue? (y/n): ").strip().lower()
        if choice != 'y':
            return 1

    # Check files
    if not check_files():
        print("\n❌ Missing required files")
        input("\nPress Enter to exit...")
        return 1

    # Show menu and process selection
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
            print("\nGoodbye!")
            return 0
        else:
            print("\n❌ Invalid choice, please try again")
            time.sleep(1)

        print("\n" + "=" * 60)
        input("Press Enter to return to the menu...")
        print("\033[2J\033[H")  # Clear screen (cross-platform)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nProgram interrupted")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nAn error occurred: {e}")
        import traceback

        traceback.print_exc()
        input("\nPress Enter to exit...")
        sys.exit(1)