"""
EzySpeechTranslate Setup Script

structure:
  app/
    admin/
    user/
    core/
    templates/
    static/css/
    static/js/
  config/ssl/
  logs/
  exports/
  data/
  scripts/
"""

"""
EzySpeechTranslate Setup Script - With Key Encryption
Automatically generates a secure key and stores it encrypted.
"""

import os
import sys
import subprocess
import platform
import secrets
import hashlib
import base64
from cryptography.fernet import Fernet
import json
import socket
import getpass
from pathlib import Path


# ---------------------------
# Utility Functions
# ---------------------------

def print_header(text):
    """Prints a large banner header."""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    """Prints a numbered setup step."""
    print(f"\n[{step_num}] {text}")


def run_command(cmd):
    """Run shell command and return True/False."""
    try:
        result = subprocess.run(
            cmd, shell=True, check=False,
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return True
        else:
            print(result.stderr.strip())
            return False
    except Exception as e:
        print(f"Error running command: {e}")
        return False


# ---------------------------
# Key Encryption Utilities
# ---------------------------

class MachineBoundEncryption:
    """Simple Machine-Bound Key Encryption (Uses machine features to generate a key)"""
    
    @staticmethod
    def get_machine_derived_key():
        """Generates a consistent encryption key based on hostname and username."""
        # Use hostname and username to create a consistent ID
        machine_id = f"{socket.gethostname()}{getpass.getuser()}"
        key_hash = hashlib.sha256(machine_id.encode()).digest()
        return base64.urlsafe_b64encode(key_hash)
    
    @staticmethod
    def encrypt_xor(plaintext: str) -> str:
        """Performs simple XOR encryption."""
        key = MachineBoundEncryption.get_machine_derived_key()
        encrypted_bytes = []
        
        for i, char_byte in enumerate(plaintext.encode()):
            key_char = key[i % len(key)]
            encrypted_bytes.append(char_byte ^ key_char)
        
        return base64.b64encode(bytes(encrypted_bytes)).decode()
    
    @staticmethod
    def decrypt_xor(ciphertext: str) -> str:
        """Decrypts the XOR-encrypted string."""
        try:
            key = MachineBoundEncryption.get_machine_derived_key()
            encrypted_bytes = base64.b64decode(ciphertext.encode())
            decrypted_bytes = []
            
            for i, byte in enumerate(encrypted_bytes):
                key_char = key[i % len(key)]
                decrypted_bytes.append(byte ^ key_char)
            
            return bytes(decrypted_bytes).decode()
        except:
            # Return None on decryption failure (e.g., wrong machine key, corrupt data)
            return None


def generate_secure_password(length=16):
    """Generates a secure password."""
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def generate_secret_key(length=32):
    """Generates a hexadecimal secret key."""
    return secrets.token_hex(length)


def prompt_admin_password():
    """
    Allows the operator to provide a custom admin password.
    Falls back to a random password when the operator opts out.
    """
    print("\nWould you like to set the admin password manually?")
    choice = input("Type 'y' to enter your own password or press ENTER to auto-generate: ").strip().lower()

    if choice != 'y':
        return generate_secure_password(16), False

    while True:
        user_password = getpass.getpass("Enter admin password (min 8 chars): ")
        if len(user_password) < 8:
            print("⚠️  Password too short. Please try again.")
            continue

        confirm_password = getpass.getpass("Confirm admin password: ")
        if user_password != confirm_password:
            print("⚠️  Passwords do not match. Please retry.")
            continue

        print("✓ Admin password set.")
        return user_password, True


# ---------------------------
# Checks
# ---------------------------

def check_python_version():
    print_step(1, "Checking Python version...")
    version_info = sys.version_info
    if not (3, 8) <= (version_info.major, version_info.minor) <= (3, 14):
        print(f"❌ Require Python 3.8 ~ 3.14, found {version_info.major}.{version_info.minor}")
        return False
    print(f"✓ Python {version_info.major}.{version_info.minor}.{version_info.micro}")
    return True


def check_openssl_availability():
    print_step(2, "Checking OpenSSL availability...")
    if run_command("openssl version"):
        result = subprocess.run("openssl version", shell=True,
                                 capture_output=True, text=True)
        print(f"✓ OpenSSL available: {result.stdout.strip()}")
        return True
    else:
        print("⚠️ OpenSSL not found. SSL cert generation skipped.")
        return False


# ---------------------------
# Virtual Environment
# ---------------------------

def create_venv():
    print_step(3, "Creating virtual environment...")

    if os.path.exists("venv"):
        print("✓ venv already exists")
        return True

    if run_command(f"{sys.executable} -m venv venv"):
        print("✓ venv created")
        return True
    else:
        print("❌ Failed to create venv")
        return False


def get_pip_executable():
    """Gets the path to the pip executable inside the venv."""
    if platform.system() == "Windows":
        return "venv\\Scripts\\pip"
    else:
        return "venv/bin/pip"


def install_dependencies():
    print_step(4, "Installing dependencies...")

    pip_exec = get_pip_executable()

    print("Upgrading pip...")
    run_command(f"{pip_exec} install --upgrade pip")

    print("Installing requirements.txt...")
    if run_command(f"{pip_exec} install -r requirements.txt"):
        print("✓ Dependencies installed")
        return True

    print("❌ Failed to install dependencies")
    return False


# ---------------------------
# Project Structure
# ---------------------------

def ensure_directories():
    print_step(5, "Ensuring project directory structure...")

    dirs = [
        "logs",
        "config/ssl",
        "app/templates",
        "app/static/css",
        "app/static/js",
        "scripts",
        "data"
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"✓ {d}/")

    return True


# ---------------------------
# Configure Secrets
# ---------------------------

def configure_secrets():
    print_step(6, "Configuring secure secrets...")
    
    config_path = Path("config/config.yaml")
    # Use `config/secrets.key` (JSON) as the canonical secrets store
    secrets_key_path = config_path.parent / 'secrets.key'

    if not config_path.exists():
        print("❌ config/config.yaml not found")
        return False

    # Check if secrets are already configured
    if secrets_key_path.exists():
        response = input("\n⚠️  Secrets already configured. Regenerate? (y/N): ").strip().lower()
        if response != 'y':
            print("✓ Using existing secrets")
            return True
    
    print("\n🔐 Generating secure secrets...")
    
    # Generate keys
    admin_password, is_manual_password = prompt_admin_password()
    jwt_secret = generate_secret_key(32)
    server_secret_key = generate_secret_key(32)

    # Use Fernet symmetric encryption and persist tokens + key into config/secrets.key (JSON)
    try:
        key = Fernet.generate_key()
        f = Fernet(key)

        new_data = {
            'fernet_key': key.decode(),
            'admin_password': f.encrypt(admin_password.encode()).decode(),
            'jwt_secret': f.encrypt(jwt_secret.encode()).decode(),
            'server_secret_key': f.encrypt(server_secret_key.encode()).decode()
        }

        secrets_key_path.write_text(json.dumps(new_data, indent=2))
        try:
            os.chmod(secrets_key_path, 0o600)
        except Exception:
            pass
    except Exception as e:
        print(f"Warning: Failed to generate/write secrets.key: {e}")
        return False

    print("\n✅ Secrets generated and stored in config/secrets.key (Fernet)")
    print("=" * 60)
    print("🔑 YOUR ADMIN CREDENTIALS (SAVE THESE!):")
    print("=" * 60)
    print(f"Username: admin")
    if is_manual_password:
        print("Password: (user provided)")
    else:
        print(f"Password: {admin_password}")
    print("=" * 60)
    print("\n⚠️  IMPORTANT: Save this password now!")
    print("    It's encrypted and stored in config/secrets.key")
    print("    The config.yaml will reference it automatically.\n")
    
    # Wait for user confirmation
    input("Press ENTER after you've saved the password...")
    
    return True


# ---------------------------
# SSL Certificate
# ---------------------------

def generate_ssl_certificate():
    print_step(7, "Checking SSL certificate...")

    cert_path = "config/ssl/cert.pem"
    key_path = "config/ssl/key.pem"

    if os.path.exists(cert_path) and os.path.exists(key_path):
        print("✓ SSL already exists")
        return True

    print("Generating self-signed certificate (valid 365 days)...")
    cmd = (
        "openssl req -x509 -newkey rsa:2048 -nodes "
        f"-keyout {key_path} -out {cert_path} -days 365 "
        '-subj "/CN=localhost"'
    )

    if run_command(cmd):
        print("✓ SSL generated")
        return True

    print("⚠️ Failed to auto-generate SSL.")
    print("    You may generate manually later.")
    return True


# ---------------------------
# Run Scripts
# ---------------------------

def create_run_scripts():
    print_step(8, "Creating run scripts...")

    if platform.system() == "Windows":
        with open("start_server.bat", "w") as f:
            f.write("venv\\Scripts\\python app\\user\\server.py\n")
        with open("start_admin.bat", "w") as f:
            f.write("venv\\Scripts\\python app\\admin\\server.py\n")
    else:
        with open("start_server.sh", "w") as f:
            f.write("#!/bin/bash\n")
            f.write("venv/bin/python app/user/server.py\n")
        with open("start_admin.sh", "w") as f:
            f.write("#!/bin/bash\n")
            f.write("venv/bin/python app/admin/server.py\n")
        run_command("chmod +x start_server.sh")
        run_command("chmod +x start_admin.sh")

    print("✓ Run scripts created")
    return True


# ---------------------------
# Verify Structure
# ---------------------------

def verify_project_files():
    print_step(10, "Verifying project files...")

    required_files = [
        "app/user/server.py",
        "app/admin/server.py",
        "requirements.txt",
        "config/config.yaml"
    ]

    is_ok = True
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"  ✓ {file_path}")
        else:
            print(f"  ✗ {file_path} (missing)")
            is_ok = False

    return is_ok


# ---------------------------
# Success Message
# ---------------------------

def print_success_message():
    print_header("🎉 Setup Complete!")

    print("🔐 Security Features Enabled:")
    print("  ✓ Passwords encrypted and stored in config/secrets.key")
    print("  ✓ Automatic decryption on server start")
    print("  ✓ No plaintext passwords in config.yaml")
    
    print("\n📝 Start servers:")
    if platform.system() == "Windows":
        print("  start_server.bat  (User server)")
        print("  start_admin.bat   (Admin panel)")
    else:
        print("  ./start_server.sh  (User server)")
        print("  ./start_admin.sh   (Admin panel)")

    print("\n🌐 Access URLs:")
    print("  User:  https://localhost:1915")
    print("  Admin: https://localhost:1916")
    
    print("\n📂 Important Files:")
    print("  config/secrets.key        - Encrypted secrets (Fernet key + tokens)")
    print("  config/config.yaml        - Main configuration")
    print("  config/secure_loader.py   - Auto-decryption loader")
    print("  config/ssl/cert.pem       - SSL certificate")
    print("  config/ssl/key.pem        - SSL private key")

    print("\n⚠️  Security Notes:")
    print("  • config/secrets.key contains the Fernet key and encrypted tokens — protect it and do not commit")
    print("  • Do not copy secrets.key to other machines")
    print("  • Run setup.py again on new deployment machines to provision new secrets.key")
    print("  • Ensure config/secrets.key is added to .gitignore")
    
    print("\n🎯 Next Steps:")
    print("  1. Save your admin password somewhere safe")
    print("  2. Start the servers using the generated scripts")
    print("  3. Login with username: admin")
    print("  4. Enjoy! 😎")


# ---------------------------
# Main
# ---------------------------

def main():
    print_header("🚀 EzySpeechTranslate Secure Setup")

    if not check_python_version():
        sys.exit(1)

    openssl_ok = check_openssl_availability()

    setup_steps = [
        create_venv,
        install_dependencies,
        ensure_directories,
        configure_secrets,
    ]

    if openssl_ok:
        setup_steps.append(generate_ssl_certificate)

    setup_steps += [
        create_run_scripts,
        verify_project_files,
    ]

    for step_function in setup_steps:
        if not step_function():
            print("\n❌ Setup failed.")
            sys.exit(1)

    print_success_message()


if __name__ == "__main__":
    main()