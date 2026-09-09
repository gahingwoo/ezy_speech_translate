#!/usr/bin/env python3
"""
EzySpeechTranslate SystemD Installation Script
Supports: Ubuntu, Debian, RHEL/CentOS (with SELinux)
Installs application to /opt/ezy_speech_translate with systemd services
"""

import os
import sys
import subprocess
import shutil
import tempfile
import json
import platform
from pathlib import Path
from typing import Dict, List, Tuple, Optional


class Colors:
    """ANSI color codes for terminal output"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class InstallationError(Exception):
    """Custom exception for installation errors"""
    pass


class SystemDetector:
    """Detects and manages system information"""
    
    @staticmethod
    def get_distro_info() -> Tuple[str, str, bool]:
        """
        Detect Linux distribution and return (distro_name, version, is_rhel_based)
        """
        try:
            # Try /etc/os-release first (most reliable)
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    key, value = line.strip().split('=', 1) if '=' in line else (line.strip(), '')
                    os_info[key] = value.strip('"')
            
            distro_id = os_info.get('ID', '').lower()
            distro_version = os_info.get('VERSION_ID', 'unknown')
            
            # Check if RHEL-based or Debian-based
            is_rhel = distro_id in ['rhel', 'centos', 'fedora', 'rocky', 'almalinux', 'ol']
            is_debian = distro_id in ['debian', 'ubuntu']
            
            if is_rhel:
                return 'RHEL', distro_version, True
            elif is_debian:
                distro_name = 'Ubuntu' if distro_id == 'ubuntu' else 'Debian'
                return distro_name, distro_version, False
            else:
                return distro_id.upper(), distro_version, 'rhel' in os_info.get('ID_LIKE', '').lower()
                
        except FileNotFoundError:
            raise InstallationError("Cannot determine Linux distribution. /etc/os-release not found.")
    
    @staticmethod
    def get_selinux_status() -> Tuple[bool, str]:
        """
        Check if SELinux is available and its current mode.
        Returns (is_enforcing, mode_str)
        """
        try:
            result = subprocess.run(
                ['getenforce'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                mode = result.stdout.strip()
                is_enforcing = mode.lower() == 'enforcing'
                return is_enforcing, mode
            return False, 'Disabled'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, 'Not Available'
    
    @staticmethod
    def is_root() -> bool:
        """Check if running as root or with sudo"""
        return os.geteuid() == 0


class PackageManager:
    """Handles package installation"""
    
    @staticmethod
    def install_packages(distro_is_rhel: bool, packages: List[str]) -> None:
        """Install required system packages"""
        print(f"{Colors.OKBLUE}Installing system packages...{Colors.ENDC}")
        
        if distro_is_rhel:
            # RHEL/CentOS/Fedora
            cmd = ['dnf', 'install', '-y'] + packages
            # Fallback to yum for older systems
            if shutil.which('dnf') is None:
                cmd = ['yum', 'install', '-y'] + packages
        else:
            # Debian/Ubuntu
            subprocess.run(['apt-get', 'update'], check=True, capture_output=True)
            cmd = ['apt-get', 'install', '-y'] + packages
        
        try:
            subprocess.run(cmd, check=True)
            print(f"{Colors.OKGREEN}System packages installed successfully{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install system packages: {e}")


class UserManager:
    """Manages system user creation and management"""
    
    @staticmethod
    def user_exists(username: str) -> bool:
        """Check if user already exists"""
        try:
            with open('/etc/passwd', 'r') as f:
                return any(line.startswith(f"{username}:") for line in f)
        except FileNotFoundError:
            return False
    
    @staticmethod
    def create_service_user(username: str, home_dir: str) -> None:
        """Create a service user with no shell"""
        if UserManager.user_exists(username):
            print(f"{Colors.WARNING}User '{username}' already exists{Colors.ENDC}")
            return
        
        print(f"{Colors.OKBLUE}Creating service user '{username}'...{Colors.ENDC}")
        
        try:
            # Create user with home directory set to app location
            subprocess.run(
                [
                    'useradd',
                    '--system',
                    '--no-create-home',
                    '--home-dir', home_dir,
                    '--shell', '/usr/sbin/nologin',
                    username
                ],
                check=True,
                capture_output=True
            )
            print(f"{Colors.OKGREEN}Service user '{username}' created{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to create user '{username}': {e}")


class FileManager:
    """Manages file operations and permissions"""
    
    @staticmethod
    def copy_application(src_dir: str, dest_dir: str, username: str) -> None:
        """Copy application files to installation directory"""
        print(f"{Colors.OKBLUE}Copying application files to {dest_dir}...{Colors.ENDC}")
        
        try:
            # Create destination directory if it doesn't exist
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            
            # Copy application files
            src_path = Path(src_dir)
            dest_path = Path(dest_dir)
            
            # Exclude directories
            exclude_dirs = {'.git', '__pycache__', '.pytest_cache', 'venv_old', '.venv', 'venv'}
            exclude_files = {'.gitignore', '.env', '.env.local'}
            
            for src_file in src_path.iterdir():
                if src_file.is_dir():
                    if src_file.name not in exclude_dirs:
                        dest_subdir = dest_path / src_file.name
                        shutil.copytree(src_file, dest_subdir, dirs_exist_ok=True,
                                      ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
                else:
                    if src_file.name not in exclude_files:
                        shutil.copy2(src_file, dest_path / src_file.name)
            
            # Set permissions
            FileManager.set_permissions(dest_dir, username)
            print(f"{Colors.OKGREEN}Application files copied successfully{Colors.ENDC}")
            
        except Exception as e:
            raise InstallationError(f"Failed to copy application: {e}")
    
    @staticmethod
    def set_permissions(app_dir: str, username: str) -> None:
        """Set correct ownership and permissions"""
        print(f"{Colors.OKBLUE}Setting file permissions...{Colors.ENDC}")
        
        try:
            # Recursively set ownership
            subprocess.run(
                ['chown', '-R', f'{username}:{username}', app_dir],
                check=True,
                capture_output=True
            )
            
            # Set directory permissions (755)
            subprocess.run(
                ['find', app_dir, '-type', 'd', '-exec', 'chmod', '755', '{}', '+'],
                check=True,
                capture_output=True
            )
            
            # Set file permissions (644)
            subprocess.run(
                ['find', app_dir, '-type', 'f', '-exec', 'chmod', '644', '{}', '+'],
                check=True,
                capture_output=True
            )
            
            # Make Python scripts executable
            subprocess.run(
                ['find', app_dir, '-type', 'f', '-name', '*.py', '-exec', 'chmod', '755', '{}', '+'],
                check=True,
                capture_output=True
            )
            
            print(f"{Colors.OKGREEN}File permissions set correctly{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to set permissions: {e}")
    
    @staticmethod
    def create_logs_dir(app_dir: str, username: str) -> str:
        """Create and configure logs directory"""
        logs_dir = os.path.join(app_dir, 'logs')
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            subprocess.run(
                ['chown', f'{username}:{username}', logs_dir],
                check=True,
                capture_output=True
            )
            subprocess.run(
                ['chmod', '755', logs_dir],
                check=True,
                capture_output=True
            )
            return logs_dir
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to create logs directory: {e}")

    @staticmethod
    def create_data_dir(app_dir: str, username: str) -> str:
        """Create and configure data directory (SQLite DB lives here)"""
        data_dir = os.path.join(app_dir, 'data')
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            subprocess.run(
                ['chown', f'{username}:{username}', data_dir],
                check=True,
                capture_output=True
            )
            subprocess.run(
                ['chmod', '755', data_dir],
                check=True,
                capture_output=True
            )
            return data_dir
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to create data directory: {e}")


class VirtualEnvironmentManager:
    """Manages Python virtual environment"""
    
    @staticmethod
    def create_venv(app_dir: str, username: str) -> str:
        """Create and configure Python virtual environment"""
        print(f"{Colors.OKBLUE}Creating Python virtual environment...{Colors.ENDC}")
        
        venv_dir = os.path.join(app_dir, 'venv')
        
        try:
            # Create venv
            subprocess.run(
                [sys.executable, '-m', 'venv', venv_dir],
                check=True,
                capture_output=True
            )
            
            # Upgrade pip
            pip_exe = os.path.join(venv_dir, 'bin', 'pip')
            subprocess.run(
                [pip_exe, 'install', '--upgrade', 'pip', 'setuptools', 'wheel'],
                check=True,
                capture_output=True
            )
            
            # Install requirements
            requirements_file = os.path.join(app_dir, 'requirements.txt')
            if os.path.exists(requirements_file):
                print(f"{Colors.OKBLUE}Installing Python dependencies...{Colors.ENDC}")
                subprocess.run(
                    [pip_exe, 'install', '-r', requirements_file],
                    check=True,
                    capture_output=True
                )
            
            # Set ownership
            subprocess.run(
                ['chown', '-R', f'{username}:{username}', venv_dir],
                check=True,
                capture_output=True
            )
            
            print(f"{Colors.OKGREEN}Virtual environment created successfully{Colors.ENDC}")
            return venv_dir
            
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to create virtual environment: {e}")


class SELinuxManager:
    """Manages SELinux configuration"""
    
    @staticmethod
    def configure_selinux(app_dir: str) -> None:
        """Configure SELinux contexts for the application"""
        if not os.path.exists('/usr/sbin/semanage'):
            print(f"{Colors.WARNING}SELinux management tools not found, skipping SELinux configuration{Colors.ENDC}")
            return
        
        print(f"{Colors.OKBLUE}Configuring SELinux...{Colors.ENDC}")
        
        selinux_contexts = [
            # admin_home_t: read-only app files (code, config, static assets)
            (app_dir, 'admin_home_t'),
            (os.path.join(app_dir, 'logs'), 'admin_home_t'),
            (os.path.join(app_dir, 'config'), 'admin_home_t'),
            # var_lib_t: writable service data — required for SQLite writes
            (os.path.join(app_dir, 'data'), 'var_lib_t'),
        ]
        
        try:
            for path, context in selinux_contexts:
                if os.path.exists(path):
                    subprocess.run(
                        ['semanage', 'fcontext', '-a', '-t', context, f"{path}(.*/)?"],
                        capture_output=True
                    )
            
            # Restore contexts
            subprocess.run(
                ['restorecon', '-Rv', app_dir],
                capture_output=True
            )
            
            print(f"{Colors.OKGREEN}SELinux configuration applied{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            print(f"{Colors.WARNING}SELinux configuration incomplete: {e}{Colors.ENDC}")


class SystemdServiceManager:
    """Manages systemd service creation and configuration"""
    
    @staticmethod
    def create_user_service(app_dir: str, venv_dir: str, username: str) -> str:
        """Create systemd service for user server"""
        service_content = f"""[Unit]
Description=EzySpeechTranslate User Server
Documentation=https://github.com/gahingwoo/ezy_speech_translate
After=network.target
Wants=ezy-admin.service

[Service]
Type=notify
User={username}
Group={username}
WorkingDirectory={app_dir}
Environment="PATH={os.path.join(venv_dir, 'bin')}:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart={os.path.join(venv_dir, 'bin', 'python')} -c "from app.user.server import app, socketio; socketio.run(app)"
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ezy-user

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={app_dir}
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
"""
        return service_content
    
    @staticmethod
    def create_admin_service(app_dir: str, venv_dir: str, username: str) -> str:
        """Create systemd service for admin server"""
        service_content = f"""[Unit]
Description=EzySpeechTranslate Admin Server (HTTPS)
Documentation=https://github.com/gahingwoo/ezy_speech_translate
After=network.target
Before=ezy-user.service

[Service]
Type=notify
User={username}
Group={username}
WorkingDirectory={app_dir}
Environment="PATH={os.path.join(venv_dir, 'bin')}:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart={os.path.join(venv_dir, 'bin', 'python')} -c "from app.admin.server import app, socketio; socketio.run(app)"
ExecReload=/bin/kill -HUP $MAINPID
KillMode=mixed
KillSignal=SIGTERM
Restart=on-failure
RestartSec=10s
StandardOutput=journal
StandardError=journal
SyslogIdentifier=ezy-admin

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths={app_dir}
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictRealtime=true
RestrictNamespaces=true
LockPersonality=true
MemoryDenyWriteExecute=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

[Install]
WantedBy=multi-user.target
"""
        return service_content
    
    @staticmethod
    def install_services(app_dir: str, venv_dir: str, username: str) -> None:
        """Install systemd service files"""
        print(f"{Colors.OKBLUE}Installing systemd services...{Colors.ENDC}")
        
        systemd_dir = '/etc/systemd/system'
        
        services = {
            'ezy-user.service': SystemdServiceManager.create_user_service(app_dir, venv_dir, username),
            'ezy-admin.service': SystemdServiceManager.create_admin_service(app_dir, venv_dir, username),
        }
        
        try:
            for service_name, service_content in services.items():
                service_path = os.path.join(systemd_dir, service_name)
                with open(service_path, 'w') as f:
                    f.write(service_content)
                
                subprocess.run(
                    ['chmod', '644', service_path],
                    check=True,
                    capture_output=True
                )
                print(f"{Colors.OKGREEN}{service_name} installed{Colors.ENDC}")
            
            # Reload systemd daemon
            subprocess.run(
                ['systemctl', 'daemon-reload'],
                check=True,
                capture_output=True
            )
            
            print(f"{Colors.OKGREEN}Systemd services installed successfully{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise InstallationError(f"Failed to install systemd services: {e}")


class Installer:
    """Main installation orchestrator"""
    
    def __init__(self):
        self.app_dir = '/opt/ezy_speech_translate'
        self.service_user = 'ezyspeech'
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
    
    def print_header(self) -> None:
        """Print installation header"""
        print(f"\n{Colors.BOLD}{Colors.HEADER}")
        print("╔════════════════════════════════════════════════════════╗")
        print("║   EzySpeechTranslate SystemD Installation Script       ║")
        print("║   Supported: Ubuntu, Debian, RHEL/CentOS/Rocky        ║")
        print("╚════════════════════════════════════════════════════════╝")
        print(f"{Colors.ENDC}\n")
    
    def validate_environment(self) -> None:
        """Validate installation environment"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 1: Environment Validation{Colors.ENDC}")
        
        # Check root
        if not SystemDetector.is_root():
            raise InstallationError("This script requires root privileges. Please run with sudo.")
        print(f"{Colors.OKGREEN}Running with root privileges{Colors.ENDC}")
        
        # Detect distro
        distro_name, distro_version, is_rhel = SystemDetector.get_distro_info()
        print(f"{Colors.OKGREEN}Detected: {distro_name} {distro_version}{Colors.ENDC}")
        
        # Check SELinux (if RHEL)
        if is_rhel:
            is_enforcing, mode = SystemDetector.get_selinux_status()
            print(f"{Colors.OKGREEN}SELinux: {mode}{Colors.ENDC}")
            if is_enforcing:
                print(f"{Colors.WARNING}SELinux is in Enforcing mode - will configure context{Colors.ENDC}")
        
        self.distro_is_rhel = is_rhel
        print()
    
    def install_dependencies(self) -> None:
        """Install required system packages"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 2: Installing System Dependencies{Colors.ENDC}")
        
        packages = [
            'python3-pip',
            'python3-venv',
            'python3-dev',
        ]
        
        PackageManager.install_packages(self.distro_is_rhel, packages)
        print()
    
    def setup_service_user(self) -> None:
        """Create service user"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 3: Creating Service User{Colors.ENDC}")
        
        UserManager.create_service_user(self.service_user, self.app_dir)
        print()
    
    def deploy_application(self) -> None:
        """Deploy application files"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 4: Deploying Application{Colors.ENDC}")
        
        FileManager.copy_application(self.src_dir, self.app_dir, self.service_user)
        FileManager.create_logs_dir(self.app_dir, self.service_user)
        FileManager.create_data_dir(self.app_dir, self.service_user)
        print()
    
    def setup_virtual_environment(self) -> str:
        """Setup Python virtual environment"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 5: Setting Up Python Environment{Colors.ENDC}")
        
        venv_dir = VirtualEnvironmentManager.create_venv(self.app_dir, self.service_user)
        print()
        return venv_dir
    
    def configure_selinux(self) -> None:
        """Configure SELinux if needed"""
        if not self.distro_is_rhel:
            return
        
        print(f"{Colors.HEADER}{Colors.BOLD}Step 6: Configuring SELinux{Colors.ENDC}")
        
        SELinuxManager.configure_selinux(self.app_dir)
        print()
    
    def install_services(self, venv_dir: str) -> None:
        """Install systemd services"""
        print(f"{Colors.HEADER}{Colors.BOLD}Step 7: Installing SystemD Services{Colors.ENDC}")
        
        SystemdServiceManager.install_services(self.app_dir, venv_dir, self.service_user)
        print()
    
    def print_summary(self) -> None:
        """Print installation summary"""
        print(f"{Colors.HEADER}{Colors.BOLD}Installation Complete!{Colors.ENDC}")
        print(f"\n{Colors.OKGREEN}Summary:{Colors.ENDC}")
        print(f"  • Application Directory: {self.app_dir}")
        print(f"  • Service User: {self.service_user}")
        print(f"  • User Service: ezy-user.service")
        print(f"  • Admin Service: ezy-admin.service")
        print(f"  • Logs Directory: {os.path.join(self.app_dir, 'logs')}")
        
        print(f"\n{Colors.OKGREEN}Next Steps:{Colors.ENDC}")
        print(f"  1. Enable services:")
        print(f"     {Colors.BOLD}sudo systemctl enable ezy-user.service ezy-admin.service{Colors.ENDC}")
        
        print(f"\n  2. Start services:")
        print(f"     {Colors.BOLD}sudo systemctl start ezy-admin.service ezy-user.service{Colors.ENDC}")
        
        print(f"\n  3. Check service status:")
        print(f"     {Colors.BOLD}sudo systemctl status ezy-user.service{Colors.ENDC}")
        print(f"     {Colors.BOLD}sudo systemctl status ezy-admin.service{Colors.ENDC}")
        
        print(f"\n  4. View logs:")
        print(f"     {Colors.BOLD}sudo journalctl -u ezy-user.service -f{Colors.ENDC}")
        print(f"     {Colors.BOLD}sudo journalctl -u ezy-admin.service -f{Colors.ENDC}")
        
        print(f"\n  5. Configuration file:")
        print(f"     {Colors.BOLD}{os.path.join(self.app_dir, 'config', 'config.yaml')}{Colors.ENDC}")
        
        print()
    
    def run(self) -> None:
        """Execute installation"""
        try:
            self.print_header()
            self.validate_environment()
            self.install_dependencies()
            self.setup_service_user()
            self.deploy_application()
            venv_dir = self.setup_virtual_environment()
            self.configure_selinux()
            self.install_services(venv_dir)
            self.print_summary()
            
            print(f"{Colors.OKGREEN}{Colors.BOLD}Installation successful!{Colors.ENDC}\n")
            
        except InstallationError as e:
            print(f"\n{Colors.FAIL}{Colors.BOLD}Installation failed:{Colors.ENDC}")
            print(f"{Colors.FAIL}{str(e)}{Colors.ENDC}\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n{Colors.FAIL}{Colors.BOLD}Unexpected error:{Colors.ENDC}")
            print(f"{Colors.FAIL}{str(e)}{Colors.ENDC}\n")
            sys.exit(1)


def main():
    """Main entry point"""
    if __name__ != '__main__':
        return
    
    # Check if running on Linux
    if platform.system() != 'Linux':
        print(f"{Colors.FAIL}Error: This script only supports Linux systems.{Colors.ENDC}")
        sys.exit(1)
    
    installer = Installer()
    installer.run()


if __name__ == '__main__':
    main()
