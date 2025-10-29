"""
EzySpeechTranslate Setup Script
Automated installation and configuration
"""

import os
import sys
import subprocess
import platform
import secrets
import shutil
from pathlib import Path


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


def check_ffmpeg():
    """Check if FFmpeg is installed"""
    print_step(2, "Checking FFmpeg installation...")

    if run_command("ffmpeg -version", check=False):
        print("✓ FFmpeg is installed")
        return True
    else:
        print("❌ FFmpeg not found")
        print("\nPlease install FFmpeg:")

        if platform.system() == "Windows":
            print("  - Download from: https://ffmpeg.org/download.html")
            print("  - Or use: choco install ffmpeg")
        elif platform.system() == "Darwin":
            print("  - Run: brew install ffmpeg")
        else:
            print("  - Run: sudo apt-get install ffmpeg / sudo yum install ffmpeg")

        return False


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


def setup_config():
    """Setup configuration file"""
    print_step(6, "Configuring application...")

    config_file = "config.yaml"

    if os.path.exists(config_file):
        response = input("\nconfig.yaml exists. Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("✓ Keeping existing configuration")
            return True

    # Generate secrets
    secrets_data = generate_secrets()

    print("\n📝 Configuration Setup")
    print("-" * 40)

    # Get user input
    admin_username = input("Admin username [admin]: ").strip() or "admin"

    print("\n⚠️  IMPORTANT: Save these credentials!")
    print("-" * 40)
    print(f"Username: {admin_username}")
    print(f"Password: {secrets_data['admin_password']}")
    print("-" * 40)

    input("\nPress Enter after saving credentials...")

    # Choose model size
    print("\nWhisper Model Size:")
    print("  1. tiny   - Fastest, least accurate (~75MB)")
    print("  2. base   - Good balance (~150MB) [Recommended]")
    print("  3. small  - Better accuracy (~500MB)")
    print("  4. medium - High accuracy (~1.5GB)")
    print("  5. large  - Best accuracy (~3GB)")

    model_choice = input("\nSelect model (1-5) [2]: ").strip() or "2"
    model_map = {'1': 'tiny', '2': 'base', '3': 'small', '4': 'medium', '5': 'large'}
    model_size = model_map.get(model_choice, 'base')

    # Server settings
    server_host = input("\nServer host [0.0.0.0]: ").strip() or "0.0.0.0"
    server_port = input("Server port [5000]: ").strip() or "5000"

    # Create config content
    config_content = f"""# EzySpeechTranslate Configuration File
# Generated by setup.py

# Server Configuration
server:
  host: "{server_host}"
  port: {server_port}
  debug: false
  secret_key: "{secrets_data['secret_key']}"

# Authentication
authentication:
  enabled: true
  admin_username: "{admin_username}"
  admin_password: "{secrets_data['admin_password']}"
  session_timeout: 3600
  jwt_secret: "{secrets_data['jwt_secret']}"

# Audio Configuration
audio:
  sample_rate: 16000
  channels: 1
  block_duration: 5
  silence_threshold: 0.01
  device_index: null

# Whisper Model Configuration
whisper:
  model_size: "{model_size}"
  device: "cpu"
  compute_type: "int8"
  language: "en"
  beam_size: 5
  vad_filter: true

# Translation Configuration
translation:
  default_target_language: "zh-cn"
  cache_enabled: true
  supported_languages:
    - "zh-cn"
    - "zh-tw"
    - "es"
    - "fr"
    - "de"
    - "ja"
    - "ko"
    - "ru"
    - "ar"
    - "pt"
    - "it"
    - "nl"
    - "pl"
    - "tr"
    - "vi"
    - "th"
    - "id"
    - "ms"
    - "hi"

# GUI Configuration
gui:
  window_title: "EzySpeechTranslate Admin"
  window_size: "1200x800"
  theme: "default"
  font_size: 10
  auto_scroll: true
  max_history: 1000

# Logging Configuration
logging:
  level: "INFO"
  file: "logs/app.log"
  max_bytes: 10485760
  backup_count: 5
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

# Database Configuration
database:
  enabled: false
  type: "sqlite"
  path: "data/translations.db"

# Export Configuration
export:
  default_format: "txt"
  output_directory: "exports"
  include_timestamps: true
  include_corrections: true
"""

    # Write config file
    try:
        with open(config_file, 'w') as f:
            f.write(config_content)
        print(f"\n✓ Configuration saved to {config_file}")

        # Save credentials to separate file
        creds_file = "CREDENTIALS.txt"
        with open(creds_file, 'w') as f:
            f.write("EzySpeechTranslate Admin Credentials\n")
            f.write("=" * 40 + "\n\n")
            f.write(f"Username: {admin_username}\n")
            f.write(f"Password: {secrets_data['admin_password']}\n")
            f.write(f"\nServer: http://{server_host}:{server_port}\n")
            f.write("\n⚠️  Keep this file secure and delete after saving credentials!\n")

        print(f"✓ Credentials saved to {creds_file}")
        return True

    except Exception as e:
        print(f"❌ Failed to create config: {e}")
        return False


def copy_web_template():
    """Copy web template to templates directory"""
    print_step(7, "Setting up web interface...")

    # The index.html content is already provided in the document
    # In a real setup, this would copy from a templates source

    if not os.path.exists("templates/index.html"):
        print("⚠️  Please ensure index.html is in templates/ directory")
        print("   You can create it manually from the provided HTML")
        return True

    print("✓ Web interface ready")
    return True


def download_whisper_model():
    """Pre-download Whisper model"""
    print_step(8, "Downloading Whisper model...")
    print("This may take a few minutes...")

    python_cmd = "venv\\Scripts\\python" if platform.system() == "Windows" else "venv/bin/python"

    # Read model size from config
    try:
        import yaml
        with open("config.yaml", 'r') as f:
            config = yaml.safe_load(f)
        model_size = config.get('whisper', {}).get('model_size', 'base')
    except:
        model_size = 'base'

    code = f'''
from faster_whisper import WhisperModel
print("Downloading {model_size} model...")
model = WhisperModel("{model_size}", device="cpu", compute_type="int8")
print("Model downloaded successfully!")
'''

    if run_command(f'{python_cmd} -c "{code}"'):
        print("✓ Whisper model downloaded")
        return True
    else:
        print("⚠️  Model download failed, will download on first use")
        return True  # Non-critical failure


def create_run_scripts():
    """Create convenient run scripts"""
    print_step(9, "Creating run scripts...")

    if platform.system() == "Windows":
        # Windows batch files
        with open("start_server.bat", 'w') as f:
            f.write("@echo off\n")
            f.write("echo Starting EzySpeechTranslate Server...\n")
            f.write("venv\\Scripts\\python app.py\n")
            f.write("pause\n")

        with open("start_admin.bat", 'w') as f:
            f.write("@echo off\n")
            f.write("echo Starting Admin GUI...\n")
            f.write("venv\\Scripts\\python admin_gui.py\n")
            f.write("pause\n")

        print("✓ Created start_server.bat and start_admin.bat")

    else:
        # Unix shell scripts
        with open("start_server.sh", 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Starting EzySpeechTranslate Server...'\n")
            f.write("venv/bin/python app.py\n")

        with open("start_admin.sh", 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Starting Admin GUI...'\n")
            f.write("venv/bin/python admin_gui.py\n")

        # Make executable
        os.chmod("start_server.sh", 0o755)
        os.chmod("start_admin.sh", 0o755)

        print("✓ Created start_server.sh and start_admin.sh")

    return True


def print_success_message():
    """Print setup completion message"""
    print_header("🎉 Setup Complete!")

    print("EzySpeechTranslate is ready to use!")
    print("\n📚 Quick Start Guide:")
    print("-" * 60)

    if platform.system() == "Windows":
        print("\n1. Start the server:")
        print("   start_server.bat")
        print("\n2. In a new terminal, start admin GUI:")
        print("   start_admin.bat")
    else:
        print("\n1. Start the server:")
        print("   ./start_server.sh")
        print("   # Or: venv/bin/python app.py")
        print("\n2. In a new terminal, start admin GUI:")
        print("   ./start_admin.sh")
        print("   # Or: venv/bin/python admin_gui.py")

    print("\n3. Open web client:")
    print("   http://localhost:5000")

    print("\n📋 Important Files:")
    print("-" * 60)
    print("  • config.yaml       - Main configuration")
    print("  • CREDENTIALS.txt   - Login credentials (KEEP SECURE!)")
    print("  • logs/app.log      - Application logs")
    print("  • README.md         - Full documentation")

    print("\n🔒 Security Reminders:")
    print("-" * 60)
    print("  • Save your admin credentials from CREDENTIALS.txt")
    print("  • Delete CREDENTIALS.txt after saving")
    print("  • Change passwords in production")
    print("  • Use HTTPS in production deployments")

    print("\n💡 Tips:")
    print("-" * 60)
    print("  • See README.md for detailed usage instructions")
    print("  • Check logs/app.log for troubleshooting")
    print("  • Use 'base' model for best performance/accuracy balance")

    print("\n" + "=" * 60)
    print("\nHappy translating! 🌍")


def main():
    """Main setup function"""
    print_header("EzySpeechTranslate Setup")
    print("This script will install and configure EzySpeechTranslate")

    # Check prerequisites
    if not check_python_version():
        sys.exit(1)

    if not check_ffmpeg():
        print("\n⚠️  FFmpeg is required. Please install it and run setup again.")
        sys.exit(1)

    # Setup steps
    steps = [
        ("Creating virtual environment", create_virtual_env),
        ("Installing dependencies", install_dependencies),
        ("Creating directories", create_directories),
        ("Configuring application", setup_config),
        ("Setting up web interface", copy_web_template),
        ("Downloading Whisper model", download_whisper_model),
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