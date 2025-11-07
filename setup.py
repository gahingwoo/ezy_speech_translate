"""
EzySpeechTranslate Setup Script
Automated installation and configuration with custom port selection
"""

import os
import sys
import subprocess
import platform
import secrets


def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Print step number"""
    print(f"\n[{step_num}] {text}")


def run_command(cmd, check=True):
    """Run shell command"""
    try:
        result = subprocess.run(cmd, shell=True, check=check,
                                capture_output=True, text=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return False


def check_python_version():
    """Check Python version"""
    print_step(1, "Checking Python version...")
    version = sys.version_info

    if version.major < 3 or (version.major == 3 and version.minor < 8) or (version.major == 3 and version.minor > 12):
        print(f"❌ Python 3.8-3.12 required. Current: {version.major}.{version.minor}")
        return False

    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True

def create_virtual_env():
    """Create virtual environment"""
    print_step(3, "Creating virtual environment...")

    if os.path.exists("venv"):
        print("✓ Virtual environment already exists")
        return True

    if run_command(f"{sys.executable} -m venv venv"):
        print("✓ Virtual environment created")
        return True
    else:
        print("❌ Failed to create virtual environment")
        return False


def get_pip_command():
    """Get pip command based on platform"""
    if platform.system() == "Windows":
        return "venv\\Scripts\\pip"
    else:
        return "venv/bin/pip"


def install_dependencies():
    """Install Python dependencies"""
    print_step(4, "Installing dependencies...")
    print("This may take several minutes...")

    pip_cmd = get_pip_command()

    # Upgrade pip
    print("\nUpgrading pip...")
    if not run_command(f"{pip_cmd} install --upgrade pip"):
        print("⚠ Failed to upgrade pip, continuing anyway...")

    # Install requirements
    print("\nInstalling packages...")
    if run_command(f"{pip_cmd} install -r requirements.txt"):
        print("✓ Dependencies installed")
        return True
    else:
        print("❌ Failed to install dependencies")
        return False


def create_directories():
    """Create necessary directories"""
    print_step(5, "Creating directories...")

    directories = ['logs', 'exports', 'data', 'templates']

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created: {directory}/")

    return True


def generate_secrets():
    """Generate random secret keys"""
    return {
        'secret_key': secrets.token_hex(32),
        'jwt_secret': secrets.token_hex(32),
        'admin_password': secrets.token_urlsafe(16)
    }


def get_port_input(prompt, default):
    """Get and validate port input"""
    while True:
        try:
            port_input = input(f"{prompt} [{default}]: ").strip() or str(default)
            port = int(port_input)

            if port < 1024 or port > 65535:
                print("⚠️  Port must be between 1024 and 65535")
                continue

            return port
        except ValueError:
            print("⚠️  Invalid port number. Please enter a number.")

def copy_web_template():
    """Copy web template to templates directory"""
    print_step(7, "Setting up web interface...")

    if not os.path.exists("templates/user.html"):
        print("⚠️  Please ensure user.html is in templates/ directory")
        print("   You can create it manually from the provided HTML")
        return True

    if not os.path.exists("templates/admin.html"):
        print("⚠️  Please ensure admin.html is in templates/ directory")
        print("   You can create it manually from the provided HTML")
        return True

    print("✓ Web interface ready")
    return True

def create_run_scripts():
    """Create convenient run scripts"""
    print_step(9, "Creating run scripts...")

    if platform.system() == "Windows":
        # Windows batch files
        with open("start_server.bat", 'w') as f:
            f.write("@echo off\n")
            f.write("echo Starting EzySpeechTranslate Main Server...\n")
            f.write("venv\\Scripts\\python user_server.py\n")
            f.write("pause\n")

        with open("start_admin.bat", 'w') as f:
            f.write("@echo off\n")
            f.write("echo Starting Admin Interface...\n")
            f.write("venv\\Scripts\\python admin_server.py\n")
            f.write("pause\n")

        print("✓ Created start_server.bat and start_admin.bat")

    else:
        # Unix shell scripts
        with open("start_server.sh", 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Starting EzySpeechTranslate Main Server...'\n")
            f.write("venv/bin/python user_server.py\n")

        with open("start_admin.sh", 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Starting Admin Interface...'\n")
            f.write("venv/bin/python admin_server.py\n")

        # Make executable
        os.chmod("start_server.sh", 0o755)
        os.chmod("start_admin.sh", 0o755)

        print("✓ Created start_server.sh and start_admin.sh")

    return True


def print_success_message():
    """Print setup completion message"""
    print_header("🎉 Setup Complete!")

    # Read ports from config
    try:
        import yaml
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        server_port = config.get('server', {}).get('port', 1915)
        admin_port = config.get('admin_server', {}).get('port', 1916)
    except:
        server_port = 1915
        admin_port = 1916

    print("EzySpeechTranslate is ready to use!")
    print("\n📚 Quick Start Guide:")
    print("-" * 60)

    if platform.system() == "Windows":
        print("\n1. Start the main server:")
        print("   start_server.bat")
        print("\n2. In a new terminal, start admin interface:")
        print("   start_admin.bat")
    else:
        print("\n1. Start the main server:")
        print("   ./start_server.sh")
        print("   # Or: venv/bin/python user_server.py")
        print("\n2. In a new terminal, start admin interface:")
        print("   ./start_admin.sh")
        print("   # Or: venv/bin/python admin_server.py")

    print(f"\n3. Open web interfaces:")
    print(f"   User Interface:  http://localhost:{server_port}")
    print(f"   Admin Interface: http://localhost:{admin_port}")

    print("\n📋 Important Files:")
    print("-" * 60)
    print("  • config.yaml       - Main configuration")
    print("  • logs/app.log      - Application logs")
    print("  • README.md         - Full documentation")

    print("\n🔒 Security Reminders:")
    print("-" * 60)
    print("  • Change passwords in production")
    print("  • Use HTTPS in production deployments")

    print("\n💡 Tips:")
    print("-" * 60)
    print("  • See README.md for detailed usage instructions")
    print("  • Check logs/app.log for troubleshooting")
    print("  • Use 'base' model for best performance/accuracy balance")
    print(f"  • Main server runs on port {server_port}")
    print(f"  • Admin interface runs on port {admin_port}")

    print("\n" + "=" * 60)
    print("\nHappy translating! 🌍")


def main():
    """Main setup function"""
    print_header("EzySpeechTranslate Setup")
    print("This script will install and configure EzySpeechTranslate")

    # Check prerequisites
    if not check_python_version():
        sys.exit(1)

    # Setup steps
    steps = [
        ("Creating virtual environment", create_virtual_env),
        ("Installing dependencies", install_dependencies),
        ("Creating directories", create_directories),
        ("Setting up web interface", copy_web_template),
        ("Creating run scripts", create_run_scripts)
    ]

    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            sys.exit(1)

    # Success
    print_success_message()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Setup failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)