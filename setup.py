"""
EzySpeechTranslate Setup Script
Automated installation and configuration with SSL certificate generation
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
        if result.returncode == 0:
            return True
        else:
            if result.stderr:
                print(f"Error output: {result.stderr}")
            return False
    except subprocess.CalledProcessError as e:
        print(f"Error: {e}")
        return False


def check_python_version():
    """Check Python version"""
    print_step(1, "Checking Python version...")
    version = sys.version_info

    if version.major < 3 or (version.major == 3 and version.minor < 8) or (version.major == 3 and version.minor > 14):
        print(f"❌ Python 3.8-3.14 required. Current: {version.major}.{version.minor}")
        return False

    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_openssl():
    """Check if OpenSSL is available"""
    print_step(2, "Checking OpenSSL...")

    if run_command("openssl version", check=False):
        result = subprocess.run("openssl version", shell=True,
                              capture_output=True, text=True)
        print(f"✓ OpenSSL available: {result.stdout.strip()}")
        return True
    else:
        print("⚠️  OpenSSL not found in PATH")
        print("   SSL certificates will need to be generated manually")
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

    directories = ['logs', 'exports', 'data', 'templates', 'static', 'static/css', 'static/js']

    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✓ Created: {directory}/")

    return True


def generate_ssl_certificates():
    """Generate self-signed SSL certificates"""
    print_step(6, "Generating SSL certificates...")

    # Check if certificates already exist
    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        print("✓ SSL certificates already exist")
        print("  cert.pem - Certificate file")
        print("  key.pem  - Private key file")
        return True

    # Try to generate certificates
    print("Generating self-signed SSL certificates...")
    print("(These will be valid for 365 days)")

    # Prepare OpenSSL command
    openssl_cmd = (
        'openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem '
        '-days 365 -nodes'
    )

    if run_command(openssl_cmd, check=False):
        print("✓ SSL certificates generated successfully")
        print("  cert.pem - Certificate file")
        print("  key.pem  - Private key file")
        return True
    else:
        print("\n⚠️  Could not auto-generate SSL certificates")
        print("\nPlease run this command manually:")
        print("-" * 60)
        print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem \\")
        print("  -days 365 -nodes")
        print("-" * 60)
        print("\nOr on Windows:")
        print("openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes")
        print("\n(You can continue setup, but servers won't start without certificates)")

        # Ask user if they want to continue
        response = input("\nContinue setup anyway? (y/n) [y]: ").strip().lower()
        if response in ['', 'y', 'yes']:
            return True
        else:
            return False


def copy_web_template():
    """Copy web template to templates directory"""
    print_step(7, "Setting up web interface...")

    templates_ready = True

    if not os.path.exists("templates/user.html"):
        print("⚠️  templates/user.html not found")
        templates_ready = False

    if not os.path.exists("templates/admin.html"):
        print("⚠️  templates/admin.html not found")
        templates_ready = False

    if not templates_ready:
        print("\n⚠️  Please ensure HTML templates are in templates/ directory")
        print("   You need to create:")
        print("   - templates/user.html")
        print("   - templates/admin.html")
    else:
        print("✓ Web interface templates found")

    return True


def create_run_scripts():
    """Create convenient run scripts"""
    print_step(8, "Creating run scripts...")

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


def verify_setup():
    """Verify that all required files are present"""
    print_step(9, "Verifying setup...")

    required_files = {
        'config.yaml': 'Configuration file',
        'user_server.py': 'Main server',
        'admin_server.py': 'Admin server',
        'requirements.txt': 'Dependencies list'
    }

    optional_files = {
        'cert.pem': 'SSL certificate',
        'key.pem': 'SSL private key',
        'templates/user.html': 'User interface',
        'templates/admin.html': 'Admin interface'
    }

    all_good = True

    print("\nRequired files:")
    for file, desc in required_files.items():
        if os.path.exists(file):
            print(f"  ✓ {file} - {desc}")
        else:
            print(f"  ✗ {file} - {desc} (MISSING!)")
            all_good = False

    print("\nOptional files:")
    for file, desc in optional_files.items():
        if os.path.exists(file):
            print(f"  ✓ {file} - {desc}")
        else:
            print(f"  ⚠ {file} - {desc} (missing)")

    return all_good


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
    print(f"   User Interface:  https://localhost:{server_port}")
    print(f"   Admin Interface: https://localhost:{admin_port}")

    print("\n   ⚠️  You'll see a security warning (self-signed certificate)")
    print("       Click 'Advanced' → 'Proceed to localhost' to continue")

    print("\n📋 Important Files:")
    print("-" * 60)
    print("  • config.yaml       - Main configuration")
    print("  • cert.pem, key.pem - SSL certificates")
    print("  • logs/app.log      - Application logs")
    print("  • README.md         - Full documentation")

    print("\n🔒 SSL Certificates:")
    print("-" * 60)
    if os.path.exists("cert.pem") and os.path.exists("key.pem"):
        print("  ✓ Self-signed certificates generated")
        print("  • Valid for 365 days")
        print("  • Suitable for development/local use")
        print("  • Use proper certificates in production")
    else:
        print("  ⚠️  SSL certificates not found!")
        print("  • Run: openssl req -x509 -newkey rsa:4096 \\")
        print("           -keyout key.pem -out cert.pem -days 365 -nodes")

    print("\n🔐 Security Reminders:")
    print("-" * 60)
    print("  • Default admin credentials are in config.yaml")
    print("  • Change passwords in production")
    print("  • Self-signed certs are for development only")
    print("  • Use real SSL certificates in production")

    print("\n💡 Tips:")
    print("-" * 60)
    print("  • See README.md for detailed usage instructions")
    print("  • Check logs/app.log for troubleshooting")
    print(f"  • Main server runs on port {server_port}")
    print(f"  • Admin interface runs on port {admin_port}")
    print("  • Use Chrome/Edge for best Speech Recognition support")

    print("\n" + "=" * 60)
    print("\nHappy translating! 🌍")


def main():
    """Main setup function"""
    print_header("EzySpeechTranslate Setup")
    print("This script will install and configure EzySpeechTranslate")

    # Check prerequisites
    if not check_python_version():
        sys.exit(1)

    has_openssl = check_openssl()

    # Setup steps
    steps = [
        ("Creating virtual environment", create_virtual_env),
        ("Installing dependencies", install_dependencies),
        ("Creating directories", create_directories),
    ]

    # Add SSL generation if OpenSSL is available
    if has_openssl:
        steps.append(("Generating SSL certificates", generate_ssl_certificates))

    steps.extend([
        ("Setting up web interface", copy_web_template),
        ("Creating run scripts", create_run_scripts),
        ("Verifying setup", verify_setup)
    ])

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