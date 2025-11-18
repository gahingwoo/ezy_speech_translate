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

import os
import sys
import subprocess
import platform


# ---------------------------
# Utility Functions
# ---------------------------

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")


def print_step(step_num, text):
    print(f"\n[{step_num}] {text}")


def run(cmd):
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
# Checks
# ---------------------------

def check_python_version():
    print_step(1, "Checking Python version...")
    v = sys.version_info
    if not (3, 8) <= (v.major, v.minor) <= (3, 14):
        print(f"❌ Require Python 3.8 ~ 3.14, found {v.major}.{v.minor}")
        return False
    print(f"✓ Python {v.major}.{v.minor}.{v.micro}")
    return True


def check_openssl():
    print_step(2, "Checking OpenSSL availability...")
    if run("openssl version"):
        out = subprocess.run("openssl version", shell=True,
                             capture_output=True, text=True)
        print(f"✓ OpenSSL available: {out.stdout.strip()}")
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

    if run(f"{sys.executable} -m venv venv"):
        print("✓ venv created")
        return True
    else:
        print("❌ Failed to create venv")
        return False


def get_pip():
    if platform.system() == "Windows":
        return "venv\\Scripts\\pip"
    else:
        return "venv/bin/pip"


def install_dependencies():
    print_step(4, "Installing dependencies...")

    pip = get_pip()

    print("Upgrading pip...")
    run(f"{pip} install --upgrade pip")

    print("Installing requirements.txt...")
    if run(f"{pip} install -r requirements.txt"):
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
        "scripts"
    ]

    for d in dirs:
        os.makedirs(d, exist_ok=True)
        print(f"✓ {d}/")

    return True


# ---------------------------
# SSL Certificate
# ---------------------------

def generate_ssl():
    print_step(6, "Checking SSL certificate...")

    cert = "config/ssl/cert.pem"
    key = "config/ssl/key.pem"

    if os.path.exists(cert) and os.path.exists(key):
        print("✓ SSL already exists")
        return True

    print("Generating self-signed certificate (valid 365 days)...")
    cmd = (
        "openssl req -x509 -newkey rsa:2048 -nodes "
        f"-keyout {key} -out {cert} -days 365 "
        '-subj "/CN=localhost"'
    )

    if run(cmd):
        print("✓ SSL generated")
        return True

    print("⚠️ Failed to auto-generate SSL.")
    print("   You may generate manually later.")
    return True  # not fatal


# ---------------------------
# Run Scripts
# ---------------------------

def create_run_scripts():
    print_step(7, "Creating run scripts...")

    # admin → app/admin/server.py
    # user  → app/user/server.py

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
        run("chmod +x start_server.sh")
        run("chmod +x start_admin.sh")

    print("✓ Run scripts created")
    return True


# ---------------------------
# Verify Structure
# ---------------------------

def verify():
    print_step(8, "Verifying project files...")

    required = [
        "app/user/server.py",
        "app/admin/server.py",
        "requirements.txt",
        "config/config.yaml"
    ]

    ok = True
    for f in required:
        if os.path.exists(f):
            print(f"  ✓ {f}")
        else:
            print(f"  ✗ {f} (missing)")
            ok = False

    return ok


# ---------------------------
# Success Message
# ---------------------------

def success():
    print_header("🎉 Setup Complete!")

    print("Start user server:")
    print("  ./start_server.sh")

    print("Start admin panel:")
    print("  ./start_admin.sh")

    print("\nSSL certs saved in config/ssl/")
    print("------------------------------")
    print("cert.pem")
    print("key.pem")
    print("------------------------------")

    print("Logs saved in logs/app.log (once app starts)")
    print("\nHave fun 😎")


# ---------------------------
# Main
# ---------------------------

def main():
    print_header("EzySpeechTranslate Setup")

    if not check_python_version():
        sys.exit(1)

    openssl_ok = check_openssl()

    steps = [
        create_venv,
        install_dependencies,
        ensure_directories,
    ]

    if openssl_ok:
        steps.append(generate_ssl)

    steps += [
        create_run_scripts,
        verify,
    ]

    for step in steps:
        if not step():
            print("\n❌ Setup failed.")
            sys.exit(1)

    success()


if __name__ == "__main__":
    main()