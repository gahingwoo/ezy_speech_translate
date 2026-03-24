#!/usr/bin/env python3
"""
EzySpeechTranslate 联合管理工具 (ezy_manager.py)
Unified Management Tool (ezy_manager.py)

整合安装、配置和服务管理功能
Integrate installation, configuration and service management

支持命令 / Supported Commands:
  - install    安装应用到/opt并配置systemd服务 / Install application
  - manage     管理systemd服务 (start/stop/restart/status/logs等) / Manage systemd services
  - setup      初始化应用配置 / Initialize application configuration
  - uninstall  卸载应用和服务 / Uninstall application and services
  - help       显示帮助信息 / Show help information
"""

import os
import sys
import subprocess
import shutil
import platform
import secrets
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

REMOTE_URL = "https://github.com/gahingwoo/ezy_speech_translate.git"

class Colors:
    """ANSI color codes"""
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


# ============================================================================
# 多语言支持系统 (Multi-language Support System)
# ============================================================================

class I18n:
    """国际化翻译系统 (Internationalization Translation System)"""
    
    # 中文 (Chinese / 简体中文)
    ZH = 'zh'
    # 英文 (English)
    EN = 'en'
    
    # 默认语言 (Default language)
    DEFAULT_LANG = 'zh'
    
    # 翻译字典 (Translation Dictionary)
    TRANSLATIONS = {
        'zh': {
            # 系统消息 (System Messages)
            'installing_packages': '正在安装系统包...',
            'install_packages_success': '✓ 系统包安装成功',
            'package_install_failed': '包安装失败: {}',
            'user_exists': "⚠ 用户 '{}' 已存在",
            'creating_service_user': "创建服务用户 '{}' ...",
            'service_user_created': "✓ 服务用户 '{}' 创建成功",
            'user_create_failed': '创建用户失败: {}',
            'copying_application': '复制应用文件到 {}...',
            'copy_success': '✓ 应用文件复制成功',
            'copy_failed': '文件复制失败: {}',
            'setting_permissions': '设置文件权限...',
            'permissions_set': '✓ 文件权限设置成功',
            'permission_failed': '权限设置失败: {}',
            'creating_venv': '创建Python虚拟环境...',
            'installing_deps': '安装Python依赖...',
            'venv_success': '✓ 虚拟环境创建成功',
            'venv_failed': '虚拟环境创建失败: {}',
            'configuring_selinux': '配置SELinux...',
            'selinux_success': '✓ SELinux配置成功',
            'selinux_incomplete': '⚠ SELinux配置不完整: {}',
            'selinux_not_found': '⚠ SELinux管理工具未找到，跳过配置',
            'installing_services': '安装systemd服务...',
            'service_installed': '✓ {} 安装成功',
            'services_success': '✓ Systemd服务安装成功',
            'service_install_failed': '服务安装失败: {}',
            'restart_failed': '服务重启失败: {}',
            'reload_failed': '服务重载失败: {}',
            
            # 安装步骤 (Installation Steps)
            'step_validation': '第1步: 环境验证',
            'step_dependencies': '第2步: 安装系统依赖',
            'step_user': '第3步: 创建服务用户',
            'step_deploy': '第4步: 部署应用',
            'step_venv': '第5步: 设置Python环境',
            'step_selinux': '第6步: 配置SELinux',
            'step_services': '第7步: 安装SystemD服务',
            
            # 验证过程 (Validation Process)
            'requires_root': "此脚本需要root权限。请使用 'sudo' 运行。",
            'root_ok': '✓ 已获得root权限',
            'detected': '✓ 检测到: {} {}',
            'selinux_status': '✓ SELinux: {}',
            'selinux_enforcing': '⚠ SELinux是在Enforcing模式 - 将配置context',
            
            # 安装完成 (Installation Complete)
            'install_complete': '安装完成！',
            'summary': '总结:',
            'app_dir': '  • 应用目录: {}',
            'service_user': '  • 服务用户: {}',
            'logs_dir': '  • 日志目录: {}',
            'config_file': '  • 配置文件: {}',
            'next_steps': '下一步:',
            'install_success': '✓ 安装成功！',
            'install_failed': '✗ 安装失败:',
            'unexpected_error': '✗ 异常错误:',
            
            # 服务管理 (Service Management)
            'starting_services': '正在启动服务...',
            'services_started': '✓ 服务启动成功',
            'services_start_failed': '✗ 服务启动失败: {}',
            'stopping_services': '正在停止服务...',
            'services_stopped': '✓ 服务停止成功',
            'services_stop_failed': '✗ 服务停止失败: {}',
            'restarting_services': '正在重启服务...',
            'services_restarted': '✓ 服务重启成功',
            'services_restart_failed': '✗ 服务重启失败: {}',
            'reloading_services': '正在重载服务...',
            'services_reloaded': '✓ 服务重载成功',
            'enabling_services': '正在启用开机自启...',
            'services_enabled': '✓ 开机自启启用成功',
            'services_enable_failed': '✗ 启用失败: {}',
            'disabling_services': '正在禁用开机自启...',
            'services_disabled': '✓ 开机自启禁用成功',
            'services_disable_failed': '✗ 禁用失败: {}',
            'requires_sudo': "错误: 此命令需要root权限。使用 'sudo'.",
            'service_status': '服务状态:',
            
            # 配置 (Configuration)
            'setting_config': '===== 应用配置设置 =====',
            'config_exists': '⚠ 配置文件已存在: {}',
            'overwrite_config': '是否覆盖配置文件? [y/N]: ',
            'keep_config': '✓ 保留现有配置',
            'generating_config': '生成默认配置文件...',
            'config_generated': '✓ 配置文件生成成功',
            'config_location': '  位置: {}',
            'config_failed': '✗ 配置生成失败: {}',
            
            # 卸载 (Uninstall)
            'uninstall_title': '===== 卸载 EzySpeechTranslate =====',
            'uninstall_warning': '⚠ 警告: 这将删除应用和systemd服务!',
            'confirm_uninstall': "确认卸载? (type 'yes' to confirm): ",
            'uninstall_cancelled': '✓ 卸载已取消',
            'stopping_uninstall': '停止服务...',
            'services_stopped_uninstall': '✓ 服务已停止',
            'deleting_services': '删除systemd服务文件...',
            'services_deleted': '✓ 服务文件已删除',
            'deleting_app': '删除应用目录...',
            'app_deleted': '✓ 应用目录已删除',
            'deleting_user': '删除服务用户...',
            'user_deleted': '✓ 服务用户已删除',
            'uninstall_complete': '✓ 卸载完成!',
            
            # 错误 (Errors)
            'linux_only': '错误: 仅支持Linux系统。',
            'cancel_operation': '操作已取消',
            'error': '错误: {}',
            'manage_required': '错误: 需要指定manage子命令',
            'unknown_distro': '无法检测Linux发行版',
        },
        'en': {
            # 系统消息 (System Messages)
            'installing_packages': 'Installing system packages...',
            'install_packages_success': '✓ System packages installed successfully',
            'package_install_failed': 'Package installation failed: {}',
            'user_exists': "⚠ User '{}' already exists",
            'creating_service_user': "Creating service user '{}' ...",
            'service_user_created': "✓ Service user '{}' created successfully",
            'user_create_failed': 'Failed to create user: {}',
            'copying_application': 'Copying application files to {}...',
            'copy_success': '✓ Application files copied successfully',
            'copy_failed': 'Failed to copy application: {}',
            'setting_permissions': 'Setting file permissions...',
            'permissions_set': '✓ File permissions set correctly',
            'permission_failed': 'Failed to set permissions: {}',
            'creating_venv': 'Creating Python virtual environment...',
            'installing_deps': 'Installing Python dependencies...',
            'venv_success': '✓ Virtual environment created successfully',
            'venv_failed': 'Failed to create virtual environment: {}',
            'configuring_selinux': 'Configuring SELinux...',
            'selinux_success': '✓ SELinux configuration applied',
            'selinux_incomplete': '⚠ SELinux configuration incomplete: {}',
            'selinux_not_found': '⚠ SELinux management tools not found, skipping configuration',
            'installing_services': 'Installing systemd services...',
            'service_installed': '✓ {} installed',
            'services_success': '✓ Systemd services installed successfully',
            'service_install_failed': 'Failed to install systemd services: {}',
            'restart_failed': 'Failed to restart services: {}',
            'reload_failed': 'Failed to reload services: {}',
            
            # 安装步骤 (Installation Steps)
            'step_validation': 'Step 1: Environment Validation',
            'step_dependencies': 'Step 2: Installing System Dependencies',
            'step_user': 'Step 3: Creating Service User',
            'step_deploy': 'Step 4: Deploying Application',
            'step_venv': 'Step 5: Setting Up Python Environment',
            'step_selinux': 'Step 6: Configuring SELinux',
            'step_services': 'Step 7: Installing SystemD Services',
            
            # 验证过程 (Validation Process)
            'requires_root': "This script requires root privileges. Please run with 'sudo'.",
            'root_ok': '✓ Running with root privileges',
            'detected': '✓ Detected: {} {}',
            'selinux_status': '✓ SELinux: {}',
            'selinux_enforcing': '⚠ SELinux is in Enforcing mode - will configure context',
            
            # 安装完成 (Installation Complete)
            'install_complete': 'Installation Complete!',
            'summary': 'Summary:',
            'app_dir': '  • Application Directory: {}',
            'service_user': '  • Service User: {}',
            'logs_dir': '  • Logs Directory: {}',
            'config_file': '  • Configuration File: {}',
            'next_steps': 'Next Steps:',
            'install_success': '✓ Installation successful!',
            'install_failed': '✗ Installation failed:',
            'unexpected_error': '✗ Unexpected error:',
            
            # 服务管理 (Service Management)
            'starting_services': 'Starting services...',
            'services_started': '✓ Services started successfully',
            'services_start_failed': '✗ Failed to start services: {}',
            'stopping_services': 'Stopping services...',
            'services_stopped': '✓ Services stopped successfully',
            'services_stop_failed': '✗ Failed to stop services: {}',
            'restarting_services': 'Restarting services...',
            'services_restarted': '✓ Services restarted successfully',
            'services_restart_failed': '✗ Failed to restart services: {}',
            'reloading_services': 'Reloading service configuration...',
            'services_reloaded': '✓ Services reloaded successfully',
            'enabling_services': 'Enabling services on boot...',
            'services_enabled': '✓ Services enabled successfully',
            'services_enable_failed': '✗ Failed to enable services: {}',
            'disabling_services': 'Disabling services from boot...',
            'services_disabled': '✓ Services disabled successfully',
            'services_disable_failed': '✗ Failed to disable services: {}',
            'requires_sudo': "Error: This command requires root privileges. Use 'sudo'.",
            'service_status': 'Service Status:',
            
            # 配置 (Configuration)
            'setting_config': '===== Application Configuration Setup =====',
            'config_exists': '⚠ Configuration file already exists: {}',
            'overwrite_config': 'Overwrite configuration file? [y/N]: ',
            'keep_config': '✓ Keep existing configuration',
            'generating_config': 'Generating default configuration file...',
            'config_generated': '✓ Configuration file generated successfully',
            'config_location': '  Location: {}',
            'config_failed': '✗ Configuration generation failed: {}',
            
            # 卸载 (Uninstall)
            'uninstall_title': '===== Uninstall EzySpeechTranslate =====',
            'uninstall_warning': '⚠ Warning: This will delete the application and systemd services!',
            'confirm_uninstall': "Confirm uninstall? (type 'yes' to confirm): ",
            'uninstall_cancelled': '✓ Uninstall cancelled',
            'stopping_uninstall': 'Stopping services...',
            'services_stopped_uninstall': '✓ Services stopped',
            'deleting_services': 'Deleting systemd service files...',
            'services_deleted': '✓ Service files deleted',
            'deleting_app': 'Deleting application directory...',
            'app_deleted': '✓ Application directory deleted',
            'deleting_user': 'Deleting service user...',
            'user_deleted': '✓ Service user deleted',
            'uninstall_complete': '✓ Uninstall complete!',
            
            # 错误 (Errors)
            'linux_only': 'Error: This script only supports Linux systems.',
            'cancel_operation': 'Operation cancelled',
            'error': 'Error: {}',
            'manage_required': 'Error: Need to specify manage subcommand',
            'unknown_distro': 'Cannot determine Linux distribution',
        }
    }
    
    # 当前语言 (Current Language)
    current_lang = DEFAULT_LANG
    
    @classmethod
    def set_language(cls, lang: str):
        """设置当前语言 (Set current language)"""
        if lang in ['zh', 'en']:
            cls.current_lang = lang
        else:
            cls.current_lang = cls.DEFAULT_LANG
    
    @classmethod
    def t(cls, key: str, *args) -> str:
        """翻译文本 (Translate text)
        
        用法 (Usage):
            I18n.t('key_name')
            I18n.t('key_with_param', 'value')
        """
        translation = cls.TRANSLATIONS.get(cls.current_lang, {}).get(
            key, 
            cls.TRANSLATIONS['en'].get(key, key)
        )
        
        if args:
            try:
                return translation.format(*args)
            except IndexError:
                return translation
        return translation


class ManagerException(Exception):
    """Custom exception"""
    pass


# ============================================================================
# 部分 1: 安装功能 (Installation)
# ============================================================================

class SystemDetector:
    """系统信息检测"""
    
    @staticmethod
    def get_distro_info() -> Tuple[str, str, bool]:
        """检测Linux发行版"""
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    key, value = line.strip().split('=', 1) if '=' in line else (line.strip(), '')
                    os_info[key] = value.strip('"')
            
            distro_id = os_info.get('ID', '').lower()
            distro_version = os_info.get('VERSION_ID', 'unknown')
            
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
            raise ManagerException(I18n.t('unknown_distro'))
    
    @staticmethod
    def get_selinux_status() -> Tuple[bool, str]:
        """检查SELinux状态"""
        try:
            result = subprocess.run(['getenforce'], capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                mode = result.stdout.strip()
                is_enforcing = mode.lower() == 'enforcing'
                return is_enforcing, mode
            return False, 'Disabled'
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False, 'Not Available'
    
    @staticmethod
    def is_root() -> bool:
        """检查是否为root用户"""
        return os.geteuid() == 0


class PackageManager:
    """系统包管理"""
    
    @staticmethod
    def install_packages(distro_is_rhel: bool, packages: List[str]) -> None:
        """安装系统包"""
        print(f"{Colors.OKBLUE}{I18n.t('installing_packages')}{Colors.ENDC}")
        
        if distro_is_rhel:
            # RHEL/CentOS/Rocky 特定的包
            cmd = ['dnf', 'install', '-y'] + packages
            if shutil.which('dnf') is None:
                # Fallback to yum for older systems
                cmd = ['yum', 'install', '-y'] + packages
        else:
            # Debian/Ubuntu
            subprocess.run(['apt-get', 'update'], check=True, capture_output=True)
            cmd = ['apt-get', 'install', '-y'] + packages
        
        try:
            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                # Show warnings but don't fail - some packages might already be installed
                if 'already installed' not in result.stdout and 'Nothing to do' not in result.stdout:
                    print(f"{Colors.WARNING}⚠ Package installation notes: {result.stdout}{Colors.ENDC}")
            print(f"{Colors.OKGREEN}✓ {I18n.t('install_packages_success')}{Colors.ENDC}")
        except Exception as e:
            raise ManagerException(I18n.t('package_install_failed', str(e)))


class UserManager:
    """系统用户管理"""
    
    @staticmethod
    def user_exists(username: str) -> bool:
        """检查用户是否存在"""
        try:
            with open('/etc/passwd', 'r') as f:
                return any(line.startswith(f"{username}:") for line in f)
        except FileNotFoundError:
            return False
    
    @staticmethod
    def create_service_user(username: str, home_dir: str) -> None:
        """创建服务用户"""
        if UserManager.user_exists(username):
            print(f"{Colors.WARNING}⚠ {I18n.t('user_exists', username)}{Colors.ENDC}")
            return
        
        print(f"{Colors.OKBLUE}{I18n.t('creating_service_user', username)}{Colors.ENDC}")
        
        try:
            subprocess.run([
                'useradd', '--system', '--no-create-home',
                '--home-dir', home_dir, '--shell', '/usr/sbin/nologin',
                username
            ], check=True, capture_output=True)
            print(f"{Colors.OKGREEN}✓ {I18n.t('service_user_created', username)}{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise ManagerException(I18n.t('user_create_failed', str(e)))


class FileManager:
    """文件管理和权限设置"""
    
    @staticmethod
    def copy_application(src_dir: str, dest_dir: str, username: str) -> None:
        """复制应用文件"""
        print(f"{Colors.OKBLUE}{I18n.t('copying_application', dest_dir)}{Colors.ENDC}")
        
        try:
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            
            src_path = Path(src_dir)
            dest_path = Path(dest_dir)
            
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
            
            FileManager.set_permissions(dest_dir, username)
            print(f"{Colors.OKGREEN}✓ {I18n.t('copy_success')}{Colors.ENDC}")
            
        except Exception as e:
            raise ManagerException(I18n.t('copy_failed', str(e)))
    
    @staticmethod
    def set_permissions(app_dir: str, username: str) -> None:
        """设置文件权限"""
        print(f"{Colors.OKBLUE}{I18n.t('setting_permissions')}{Colors.ENDC}")
        
        try:
            subprocess.run(['chown', '-R', f'{username}:{username}', app_dir],
                         check=True, capture_output=True)
            subprocess.run(['find', app_dir, '-type', 'd', '-exec', 'chmod', '755', '{}', '+'],
                         check=True, capture_output=True)
            subprocess.run(['find', app_dir, '-type', 'f', '-exec', 'chmod', '644', '{}', '+'],
                         check=True, capture_output=True)
            subprocess.run(['find', app_dir, '-type', 'f', '-name', '*.py', '-exec', 'chmod', '755', '{}', '+'],
                         check=True, capture_output=True)
            print(f"{Colors.OKGREEN}✓ {I18n.t('permissions_set')}{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise ManagerException(I18n.t('permission_failed', str(e)))
    
    @staticmethod
    def create_logs_dir(app_dir: str, username: str) -> str:
        """创建日志目录"""
        logs_dir = os.path.join(app_dir, 'logs')
        Path(logs_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            subprocess.run(['chown', f'{username}:{username}', logs_dir],
                         check=True, capture_output=True)
            subprocess.run(['chmod', '755', logs_dir], check=True, capture_output=True)
            return logs_dir
        except subprocess.CalledProcessError as e:
            raise ManagerException(f"日志目录创建失败: {e}")


class VirtualEnvironmentManager:
    """Python虚拟环境管理"""
    
    @staticmethod
    def create_venv(app_dir: str, username: str) -> str:
        """创建虚拟环境"""
        print(f"{Colors.OKBLUE}{I18n.t('creating_venv')}{Colors.ENDC}")
        
        venv_dir = os.path.join(app_dir, 'venv')
        
        try:
            # 创建虚拟环境
            result = subprocess.run([sys.executable, '-m', 'venv', venv_dir],
                         check=True, capture_output=True, text=True)
            if result.returncode != 0:
                raise ManagerException(f"Failed to create venv: {result.stderr}")
            
            pip_exe = os.path.join(venv_dir, 'bin', 'pip')
            
            # 升级 pip, setuptools, wheel
            result = subprocess.run([pip_exe, 'install', '--upgrade', 'pip', 'setuptools', 'wheel'],
                         check=True, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"{Colors.WARNING}⚠ Warning upgrading pip tools: {result.stderr}{Colors.ENDC}")
            
            requirements_file = os.path.join(app_dir, 'requirements.txt')
            if os.path.exists(requirements_file):
                print(f"{Colors.OKBLUE}{I18n.t('installing_deps')}{Colors.ENDC}")
                # 安装依赖，显示输出以便调试
                result = subprocess.run([pip_exe, 'install', '-r', requirements_file],
                             check=False, capture_output=True, text=True)
                
                if result.returncode != 0:
                    # 显示详细的错误信息
                    error_msg = result.stderr if result.stderr else result.stdout
                    print(f"{Colors.WARNING}⚠ Pip installation output:{Colors.ENDC}")
                    print(error_msg)
                    
                    # 尝试安装，忽略某些可选的依赖问题
                    print(f"{Colors.OKBLUE}Retrying with --no-deps for problematic packages...{Colors.ENDC}")
                    result = subprocess.run([pip_exe, 'install', '-r', requirements_file, '--no-deps'],
                                 check=False, capture_output=True, text=True)
                    
                    if result.returncode != 0:
                        error_msg = result.stderr if result.stderr else result.stdout
                        raise ManagerException(f"Failed to install dependencies:\n{error_msg}")
                    
                    # 尝试安装主要依赖
                    print(f"{Colors.OKBLUE}Installing with relaxed constraints...{Colors.ENDC}")
                    result = subprocess.run([pip_exe, 'install', '-r', requirements_file, '--no-strict-collisions'],
                                 check=False, capture_output=True, text=True)
                
                if result.returncode == 0:
                    print(f"{Colors.OKGREEN}✓ Dependencies installed{Colors.ENDC}")
            
            subprocess.run(['chown', '-R', f'{username}:{username}', venv_dir],
                         check=True, capture_output=True)
            
            print(f"{Colors.OKGREEN}✓ {I18n.t('venv_success')}{Colors.ENDC}")
            return venv_dir
            
        except subprocess.CalledProcessError as e:
            raise ManagerException(I18n.t('venv_failed', str(e)))


class SELinuxManager:
    """SELinux配置"""
    
    @staticmethod
    def configure_selinux(app_dir: str) -> None:
        """配置SELinux"""
        if not os.path.exists('/usr/sbin/semanage'):
            print(f"{Colors.WARNING}⚠ {I18n.t('selinux_not_found')}{Colors.ENDC}")
            return
        
        print(f"{Colors.OKBLUE}{I18n.t('configuring_selinux')}{Colors.ENDC}")
        
        selinux_contexts = [
            (app_dir, 'admin_var_lib_t'),
            (os.path.join(app_dir, 'logs'), 'admin_var_lib_t'),
            (os.path.join(app_dir, 'config'), 'admin_var_lib_t'),
        ]
        
        try:
            for path, context in selinux_contexts:
                if os.path.exists(path):
                    subprocess.run(['semanage', 'fcontext', '-a', '-t', context, f"{path}(.*/)?"],
                                 capture_output=True)
            
            subprocess.run(['restorecon', '-Rv', app_dir], capture_output=True)
            print(f"{Colors.OKGREEN}✓ {I18n.t('selinux_success')}{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            print(f"{Colors.WARNING}⚠ {I18n.t('selinux_incomplete', str(e))}{Colors.ENDC}")


class SystemdServiceManager:
    """Systemd服务管理"""
    
    @staticmethod
    def create_user_service(app_dir: str, venv_dir: str, username: str) -> str:
        """生成用户服务内容"""
        return f"""[Unit]
Description=EzySpeechTranslate User Server
After=network.target

[Service]
Type=simple
User={username}
Group={username}
WorkingDirectory={app_dir}
Environment="PATH={os.path.join(venv_dir, 'bin')}:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart={os.path.join(venv_dir, 'bin', 'python')} {os.path.join(app_dir, 'app', 'user', 'server.py')}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    
    @staticmethod
    def create_admin_service(app_dir: str, venv_dir: str, username: str) -> str:
        """生成管理服务内容"""
        return f"""[Unit]
Description=EzySpeechTranslate Admin Server
After=network.target

[Service]
Type=simple
User={username}
Group={username}
WorkingDirectory={app_dir}
Environment="PATH={os.path.join(venv_dir, 'bin')}:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart={os.path.join(venv_dir, 'bin', 'python')} {os.path.join(app_dir, 'app', 'admin', 'server.py')}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
NoNewPrivileges=true

[Install]
WantedBy=multi-user.target
"""
    
    @staticmethod
    def install_services(app_dir: str, venv_dir: str, username: str) -> None:
        """安装systemd服务"""
        print(f"{Colors.OKBLUE}{I18n.t('installing_services')}{Colors.ENDC}")
        
        systemd_dir = '/etc/systemd/system'
        services = {
            'ezyspeech-user.service': SystemdServiceManager.create_user_service(app_dir, venv_dir, username),
            'ezyspeech-admin.service': SystemdServiceManager.create_admin_service(app_dir, venv_dir, username),
        }
        
        try:
            for service_name, service_content in services.items():
                service_path = os.path.join(systemd_dir, service_name)
                with open(service_path, 'w') as f:
                    f.write(service_content)
                subprocess.run(['chmod', '644', service_path], check=True, capture_output=True)
                print(f"{Colors.OKGREEN}✓ {I18n.t('service_installed', service_name)}{Colors.ENDC}")
            
            subprocess.run(['systemctl', 'daemon-reload'], check=True, capture_output=True)
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_success')}{Colors.ENDC}")
        except subprocess.CalledProcessError as e:
            raise ManagerException(I18n.t('service_install_failed', str(e)))


class Installer:
    """安装协调器"""
    
    def __init__(self, app_dir='/opt/ezy_speech_translate', service_user='ezyspeech'):
        self.app_dir = app_dir
        self.service_user = service_user
        self.src_dir = os.path.dirname(os.path.abspath(__file__))
        self.distro_is_rhel = False
    
    def validate_environment(self) -> None:
        """验证环境"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_validation')}{Colors.ENDC}")
        
        if not SystemDetector.is_root():
            raise ManagerException(I18n.t('requires_root'))
        print(f"{Colors.OKGREEN}✓ {I18n.t('root_ok')}{Colors.ENDC}")
        
        distro_name, distro_version, is_rhel = SystemDetector.get_distro_info()
        print(f"{Colors.OKGREEN}✓ {I18n.t('detected', distro_name, distro_version)}{Colors.ENDC}")
        
        if is_rhel:
            is_enforcing, mode = SystemDetector.get_selinux_status()
            print(f"{Colors.OKGREEN}✓ {I18n.t('selinux_status', mode)}{Colors.ENDC}")
            if is_enforcing:
                print(f"{Colors.WARNING}{I18n.t('selinux_enforcing')}{Colors.ENDC}")
        
        self.distro_is_rhel = is_rhel
        print()
    
    def install_dependencies(self) -> None:
        """安装依赖"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_dependencies')}{Colors.ENDC}")
        
        # 基础包
        if self.distro_is_rhel:
            # RHEL/CentOS/Rocky 依赖
            packages = [
                'python3-pip',
                'python3-devel',
                'gcc',
                'gcc-c++',
                'make',
                'openssl-devel',
                'libffi-devel',
                'git',
            ]
        else:
            # Debian/Ubuntu 依赖
            packages = [
                'python3-pip',
                'python3-dev',
                'python3-venv',
                'build-essential',
                'libssl-dev',
                'libffi-dev',
                'git',
            ]
        
        PackageManager.install_packages(self.distro_is_rhel, packages)
        print()
    
    def setup_service_user(self) -> None:
        """创建服务用户"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_user')}{Colors.ENDC}")
        UserManager.create_service_user(self.service_user, self.app_dir)
        print()
    
    def deploy_application(self) -> None:
        """部署应用 — 直接 git clone 到目标目录"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_deploy')}{Colors.ENDC}")

        dest = Path(self.app_dir)

        if dest.exists() and any(dest.iterdir()):
            # 目录已存在且非空，跳过 clone，update.py 负责更新
            print(f"{Colors.WARNING}⚠ {self.app_dir} already exists, skipping clone{Colors.ENDC}")
        else:
            dest.mkdir(parents=True, exist_ok=True)
            print(f"{Colors.OKBLUE}Cloning from {REMOTE_URL} ...{Colors.ENDC}")
            result = subprocess.run(
                ["git", "clone", REMOTE_URL, str(dest)],
                capture_output=True, text=True
            )
            if result.returncode != 0:
                raise ManagerException(f"git clone failed: {result.stderr.strip()}")
            print(f"{Colors.OKGREEN}✓ Repository cloned to {self.app_dir}{Colors.ENDC}")

        FileManager.set_permissions(self.app_dir, self.service_user)
        FileManager.create_logs_dir(self.app_dir, self.service_user)
        print()
    
    def setup_virtual_environment(self) -> str:
        """设置虚拟环境"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_venv')}{Colors.ENDC}")
        venv_dir = VirtualEnvironmentManager.create_venv(self.app_dir, self.service_user)
        print()
        return venv_dir
    
    def configure_selinux(self) -> None:
        """配置SELinux"""
        if not self.distro_is_rhel:
            return
        
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_selinux')}{Colors.ENDC}")
        SELinuxManager.configure_selinux(self.app_dir)
        print()
    
    def install_services(self, venv_dir: str) -> None:
        """安装服务"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('step_services')}{Colors.ENDC}")
        SystemdServiceManager.install_services(self.app_dir, venv_dir, self.service_user)
        print()
    
    def print_summary(self) -> None:
        """打印总结"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('install_complete')}{Colors.ENDC}")
        print(f"\n{Colors.OKGREEN}{I18n.t('summary')}{Colors.ENDC}")
        print(f"  • {I18n.t('app_dir', self.app_dir)}")
        print(f"  • {I18n.t('service_user', self.service_user)}")
        print(f"  • {I18n.t('logs_dir', os.path.join(self.app_dir, 'logs'))}")
        print(f"  • {I18n.t('config_file', os.path.join(self.app_dir, 'config', 'config.yaml'))}")
        
        print(f"\n{Colors.OKGREEN}{I18n.t('next_steps')}{Colors.ENDC}")
        print(f"  1. 使用管理工具启动服务:")
        print(f"     {Colors.BOLD}sudo python3 ezy_manager.py manage start{Colors.ENDC}")
        print(f"\n  2. 启用开机自启:")
        print(f"     {Colors.BOLD}sudo python3 ezy_manager.py manage enable{Colors.ENDC}")
        print(f"\n  3. 查看日志:")
        print(f"     {Colors.BOLD}python3 ezy_manager.py manage logs -u{Colors.ENDC}")
        print()
    
    def run(self) -> None:
        """执行安装"""
        try:
            print(f"\n{Colors.BOLD}{Colors.HEADER}")
            print("╔════════════════════════════════════════════════════════╗")
            print("║   EzySpeechTranslate 联合管理工具 - 安装向导              ║")
            print("║   Supported: Ubuntu, Debian, RHEL/CentOS/Rocky        ║")
            print("╚════════════════════════════════════════════════════════╝")
            print(f"{Colors.ENDC}\n")
            
            self.validate_environment()
            self.install_dependencies()
            self.setup_service_user()
            self.deploy_application()
            venv_dir = self.setup_virtual_environment()
            self.configure_selinux()
            self.install_services(venv_dir)
            self.print_summary()
            
            print(f"{Colors.OKGREEN}{Colors.BOLD}✓ {I18n.t('install_success')}{Colors.ENDC}\n")
            
        except ManagerException as e:
            print(f"\n{Colors.FAIL}{Colors.BOLD}✗ {I18n.t('install_failed')}{Colors.ENDC}")
            print(f"{Colors.FAIL}{str(e)}{Colors.ENDC}\n")
            sys.exit(1)
        except Exception as e:
            print(f"\n{Colors.FAIL}{Colors.BOLD}✗ {I18n.t('unexpected_error')}{Colors.ENDC}")
            print(f"{Colors.FAIL}{str(e)}{Colors.ENDC}\n")
            sys.exit(1)


# ============================================================================
# 部分 2: 服务管理功能 (Service Management)
# ============================================================================

class ServiceManager:
    """Systemd服务管理工具"""
    
    SERVICES = ['ezyspeech-user.service', 'ezyspeech-admin.service']
    APP_DIR = '/opt/ezy_speech_translate'
    
    @staticmethod
    def run_command(cmd: List[str], check: bool = True) -> tuple:
        """执行命令"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, '', str(e)
    
    @staticmethod
    def is_root() -> bool:
        """检查是否为root"""
        return os.geteuid() == 0
    
    @staticmethod
    def require_root():
        """需要root权限"""
        if not ServiceManager.is_root():
            print(f"{Colors.FAIL}{I18n.t('requires_sudo')}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def start_services():
        """启动服务"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('starting_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'start'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_started')}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {I18n.t('services_start_failed', stderr)}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def stop_services():
        """停止服务"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('stopping_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'stop'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_stopped')}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {I18n.t('services_stop_failed', stderr)}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def restart_services():
        """重启服务"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('restarting_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'restart'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_restarted')}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {I18n.t('services_restart_failed', stderr)}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def reload_services():
        """重载配置"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('reloading_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'reload'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_reloaded')}{Colors.ENDC}")
        else:
            print(f"{Colors.WARNING}⚠ {I18n.t('reload_failed')}{Colors.ENDC}")
    
    @staticmethod
    def enable_services():
        """启用开机自启"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('enabling_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'enable'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_enabled')}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {I18n.t('services_enable_failed', stderr)}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def disable_services():
        """禁用开机自启"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}{I18n.t('disabling_services')}{Colors.ENDC}")
        cmd = ['systemctl', 'disable'] + ServiceManager.SERVICES
        ret, _, stderr = ServiceManager.run_command(cmd)
        if ret == 0:
            print(f"{Colors.OKGREEN}✓ {I18n.t('services_disabled')}{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}✗ {I18n.t('services_disable_failed', stderr)}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def status_services():
        """查看服务状态"""
        print(f"{Colors.HEADER}{Colors.BOLD}{I18n.t('service_status')}{Colors.ENDC}\n")
        for service in ServiceManager.SERVICES:
            cmd = ['systemctl', 'is-active', service]
            ret, status, _ = ServiceManager.run_command(cmd)
            status = status.strip()
            color = Colors.OKGREEN if status == 'active' else Colors.WARNING
            print(f"  {service:<25} {color}{status}{Colors.ENDC}")
        print()
    
    @staticmethod
    def logs_all(lines: int = 50):
        """查看所有日志"""
        for service in ServiceManager.SERVICES:
            print(f"\n{Colors.HEADER}{Colors.BOLD}{service} 日志:{Colors.ENDC}\n")
            cmd = ['journalctl', '-u', service, '-n', str(lines)]
            ServiceManager.run_command(cmd, check=False)
    
    @staticmethod
    def logs_user(follow: bool = False):
        """查看用户服务日志"""
        args = ['-u', 'ezyspeech-user.service']
        if follow:
            args.insert(0, '-f')
        cmd = ['journalctl'] + args
        ServiceManager.run_command(cmd, check=False)
    
    @staticmethod
    def logs_admin(follow: bool = False):
        """查看管理服务日志"""
        args = ['-u', 'ezyspeech-admin.service']
        if follow:
            args.insert(0, '-f')
        cmd = ['journalctl'] + args
        ServiceManager.run_command(cmd, check=False)


# ============================================================================
# 部分 3: 应用配置功能 (Setup)
# ============================================================================

class ConfigurationManager:
    """应用配置管理"""
    
    @staticmethod
    def setup_config():
        """设置应用配置"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}{I18n.t('setting_config')}{Colors.ENDC}\n")
        
        config_file = '/opt/ezy_speech_translate/config/config.yaml'
        
        if os.path.exists(config_file):
            print(f"{Colors.WARNING}⚠ {I18n.t('config_exists', config_file)}{Colors.ENDC}")
            choice = input(f"\n{I18n.t('overwrite_config')}").strip().lower()
            if choice != 'y':
                print(f"{Colors.OKGREEN}✓ {I18n.t('keep_config')}{Colors.ENDC}\n")
                return
        
        print(f"{Colors.OKBLUE}{I18n.t('generating_config')}{Colors.ENDC}")
        
        # 生成默认配置
        default_config = """# EzySpeechTranslate 默认配置

# ============================================
# 用户服务器配置
# ============================================
server:
  host: "0.0.0.0"           # 监听地址
  port: 5000                # 监听端口
  use_https: false          # 是否使用HTTPS
  max_connections: 100

# ============================================
# 管理服务器配置
# ============================================
admin_server:
  host: "0.0.0.0"           # 监听地址
  port: 5001                # 监听端口
  use_https: true           # 建议使用HTTPS
  ssl_cert: "/opt/ezy_speech_translate/config/ssl/cert.pem"
  ssl_key: "/opt/ezy_speech_translate/config/ssl/key.pem"

# ============================================
# 日志配置
# ============================================
logging:
  level: "INFO"             # 日志级别
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
"""
        
        try:
            config_dir = os.path.dirname(config_file)
            os.makedirs(config_dir, exist_ok=True)
            
            with open(config_file, 'w') as f:
                f.write(default_config)
            
            # 设置权限
            subprocess.run(['chmod', '644', config_file], check=True, capture_output=True)
            subprocess.run(['chown', 'ezyspeech:ezyspeech', config_file], check=True, capture_output=True)
            
            print(f"{Colors.OKGREEN}✓ {I18n.t('config_generated')}{Colors.ENDC}")
            print(f"  {I18n.t('config_location', config_file)}\n")
            
        except Exception as e:
            print(f"{Colors.FAIL}✗ {I18n.t('config_failed', str(e))}{Colors.ENDC}\n")


# ============================================================================
# 部分 4: 卸载功能 (Uninstall)
# ============================================================================

class Uninstaller:
    """卸载程序"""
    
    APP_DIR = '/opt/ezy_speech_translate'
    SERVICE_USER = 'ezyspeech'
    
    @staticmethod
    def uninstall():
        """卸载应用"""
        if not SystemDetector.is_root():
            print(f"{Colors.FAIL}{I18n.t('linux_only')}{Colors.ENDC}")
            sys.exit(1)
        
        print(f"\n{Colors.HEADER}{Colors.BOLD}{I18n.t('uninstall_title')}{Colors.ENDC}\n")
        print(f"{Colors.WARNING}⚠ {I18n.t('uninstall_warning')}{Colors.ENDC}")
        
        confirm = input(f"\n{Colors.BOLD}{I18n.t('confirm_uninstall')}{Colors.ENDC}").strip()
        if confirm != 'yes':
            print(f"{Colors.OKGREEN}✓ {I18n.t('uninstall_cancelled')}{Colors.ENDC}\n")
            return
        
        print()
        
        # 1. 停止服务
        print(f"{Colors.OKBLUE}{I18n.t('stopping_uninstall')}{Colors.ENDC}")
        subprocess.run(['systemctl', 'stop', 'ezyspeech-user.service', 'ezyspeech-admin.service'],
                      capture_output=True)
        subprocess.run(['systemctl', 'disable', 'ezyspeech-user.service', 'ezyspeech-admin.service'],
                      capture_output=True)
        print(f"{Colors.OKGREEN}✓ {I18n.t('services_stopped_uninstall')}{Colors.ENDC}")
        
        # 2. 删除systemd文件
        print(f"{Colors.OKBLUE}{I18n.t('deleting_services')}{Colors.ENDC}")
        subprocess.run(['rm', f'/etc/systemd/system/ezyspeech-user.service'],
                      capture_output=True)
        subprocess.run(['rm', f'/etc/systemd/system/ezyspeech-admin.service'],
                      capture_output=True)
        subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
        print(f"{Colors.OKGREEN}✓ {I18n.t('services_deleted')}{Colors.ENDC}")
        
        # 3. 删除应用目录
        print(f"{Colors.OKBLUE}{I18n.t('deleting_app')}{Colors.ENDC}")
        if os.path.exists(Uninstaller.APP_DIR):
            shutil.rmtree(Uninstaller.APP_DIR)
        print(f"{Colors.OKGREEN}✓ {I18n.t('app_deleted')}{Colors.ENDC}")
        
        # 4. 删除用户
        print(f"{Colors.OKBLUE}{I18n.t('deleting_user')}{Colors.ENDC}")
        subprocess.run(['userdel', '-r', Uninstaller.SERVICE_USER], capture_output=True)
        print(f"{Colors.OKGREEN}✓ {I18n.t('user_deleted')}{Colors.ENDC}")
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ {I18n.t('uninstall_complete')}{Colors.ENDC}\n")


# ============================================================================
# 主程序入口和命令行解析
# ============================================================================

def main():
    """主程序"""
    parser = argparse.ArgumentParser(
        description='EzySpeechTranslate 联合管理工具 | Unified Management Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
{Colors.BOLD}示例 / Examples:{Colors.ENDC}
  sudo python3 ezy_manager.py install                     # 安装应用 / Install application
  python3 ezy_manager.py --lang zh manage status          # 中文显示状态 / Show status in Chinese
  python3 ezy_manager.py --lang en manage status          # English status output
  sudo python3 ezy_manager.py manage start                # 启动服务 / Start services
  sudo python3 ezy_manager.py manage restart              # 重启服务 / Restart services
  sudo python3 ezy_manager.py manage logs:user -f         # 实时日志 / Real-time user logs
  sudo python3 ezy_manager.py setup                       # 初始化配置 / Setup configuration
  sudo python3 ezy_manager.py uninstall                   # 卸载应用 / Uninstall application
""")
    
    # 添加全局 --lang 参数
    parser.add_argument(
        '--lang',
        choices=['zh', 'en'],
        default='zh',
        help='设置语言 (Set language): zh=中文, en=English [default: zh]'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='命令 (Commands)')
    
    # install 命令
    subparsers.add_parser('install', help='安装应用和systemd服务 (Install application and services)')
    
    # manage 命令
    manage_parser = subparsers.add_parser('manage', help='管理systemd服务 (Manage systemd services)')
    manage_subparsers = manage_parser.add_subparsers(dest='manage_cmd')
    manage_subparsers.add_parser('start', help='启动所有服务 (Start all services)')
    manage_subparsers.add_parser('stop', help='停止所有服务 (Stop all services)')
    manage_subparsers.add_parser('restart', help='重启所有服务 (Restart all services)')
    manage_subparsers.add_parser('reload', help='重载配置 (Reload configuration)')
    manage_subparsers.add_parser('enable', help='启用开机自启 (Enable autostart)')
    manage_subparsers.add_parser('disable', help='禁用开机自启 (Disable autostart)')
    manage_subparsers.add_parser('status', help='查看服务状态 (Show service status)')
    
    logs_parser_all = manage_subparsers.add_parser('logs', help='查看所有日志 (View all logs)')
    logs_parser_all.add_argument('-n', '--lines', type=int, default=50, help='显示行数 (Number of lines)')
    
    logs_parser_user = manage_subparsers.add_parser('logs:user', help='查看用户服务日志 (View user service logs)')
    logs_parser_user.add_argument('-f', '--follow', action='store_true', help='实时跟踪 (Follow in real-time)')
    
    logs_parser_admin = manage_subparsers.add_parser('logs:admin', help='查看管理服务日志 (View admin service logs)')
    logs_parser_admin.add_argument('-f', '--follow', action='store_true', help='实时跟踪 (Follow in real-time)')
    
    # setup 命令
    subparsers.add_parser('setup', help='初始化应用配置 (Setup application configuration)')
    
    # uninstall 命令
    subparsers.add_parser('uninstall', help='卸载应用 (Uninstall application)')
    
    args = parser.parse_args()
    
    # 设置语言
    I18n.set_language(args.lang)
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if platform.system() != 'Linux':
            print(f"{Colors.FAIL}{I18n.t('linux_only')}{Colors.ENDC}")
            sys.exit(1)
        
        if args.command == 'install':
            installer = Installer()
            installer.run()
        
        elif args.command == 'manage':
            if not args.manage_cmd:
                print(f"{Colors.FAIL}{I18n.t('manage_required')}{Colors.ENDC}")
                manage_parser.print_help()
                sys.exit(1)
            
            if args.manage_cmd == 'start':
                ServiceManager.start_services()
            elif args.manage_cmd == 'stop':
                ServiceManager.stop_services()
            elif args.manage_cmd == 'restart':
                ServiceManager.restart_services()
            elif args.manage_cmd == 'reload':
                ServiceManager.reload_services()
            elif args.manage_cmd == 'enable':
                ServiceManager.enable_services()
            elif args.manage_cmd == 'disable':
                ServiceManager.disable_services()
            elif args.manage_cmd == 'status':
                ServiceManager.status_services()
            elif args.manage_cmd == 'logs':
                ServiceManager.logs_all(lines=args.lines if hasattr(args, 'lines') else 50)
            elif args.manage_cmd == 'logs:user':
                ServiceManager.logs_user(follow=args.follow if hasattr(args, 'follow') else False)
            elif args.manage_cmd == 'logs:admin':
                ServiceManager.logs_admin(follow=args.follow if hasattr(args, 'follow') else False)
        
        elif args.command == 'setup':
            ConfigurationManager.setup_config()
        
        elif args.command == 'uninstall':
            Uninstaller.uninstall()
    
    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}{I18n.t('cancel_operation')}{Colors.ENDC}")
        sys.exit(1)
    except Exception as e:
        print(f"\n{Colors.FAIL}{I18n.t('error', str(e))}{Colors.ENDC}")
        sys.exit(1)


if __name__ == '__main__':
    main()
