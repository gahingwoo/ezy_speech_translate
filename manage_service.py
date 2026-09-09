#!/usr/bin/env python3
"""
EzySpeechTranslate Service Manager - 服务管理辅助工具
用于快速管理systemd服务
"""

import subprocess
import sys
import os
from typing import Optional, List


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


class ServiceManager:
    """Manages EzySpeechTranslate services"""
    
    SERVICES = ['ezy-user.service', 'ezy-admin.service']
    APP_DIR = '/opt/ezy_speech_translate'
    LOGS_DIR = os.path.join(APP_DIR, 'logs')
    
    @staticmethod
    def run_command(cmd: List[str], check: bool = True) -> tuple:
        """Run shell command and return (return_code, stdout, stderr)"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
            return result.returncode, result.stdout, result.stderr
        except Exception as e:
            return 1, '', str(e)
    
    @staticmethod
    def is_root() -> bool:
        """Check if running as root"""
        return os.geteuid() == 0
    
    @staticmethod
    def require_root():
        """Exit if not running as root"""
        if not ServiceManager.is_root():
            print(f"{Colors.FAIL}Error: This command requires root privileges. Use 'sudo'.{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def start_services():
        """Start all services"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Starting services...{Colors.ENDC}")
        
        cmd = ['systemctl', 'start'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services started successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to start services: {stderr}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def stop_services():
        """Stop all services"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Stopping services...{Colors.ENDC}")
        
        cmd = ['systemctl', 'stop'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services stopped successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to stop services: {stderr}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def restart_services():
        """Restart all services"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Restarting services...{Colors.ENDC}")
        
        cmd = ['systemctl', 'restart'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services restarted successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to restart services: {stderr}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def reload_services():
        """Reload configuration"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Reloading service configuration...{Colors.ENDC}")
        
        cmd = ['systemctl', 'reload'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services reloaded successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to reload services: {stderr}{Colors.ENDC}")
    
    @staticmethod
    def enable_services():
        """Enable services to start on boot"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Enabling services on boot...{Colors.ENDC}")
        
        cmd = ['systemctl', 'enable'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services enabled successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to enable services: {stderr}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def disable_services():
        """Disable services from starting on boot"""
        ServiceManager.require_root()
        print(f"{Colors.OKBLUE}Disabling services from boot...{Colors.ENDC}")
        
        cmd = ['systemctl', 'disable'] + ServiceManager.SERVICES
        ret, stdout, stderr = ServiceManager.run_command(cmd)
        
        if ret == 0:
            print(f"{Colors.OKGREEN}Services disabled successfully{Colors.ENDC}")
        else:
            print(f"{Colors.FAIL}Failed to disable services: {stderr}{Colors.ENDC}")
            sys.exit(1)
    
    @staticmethod
    def status_services():
        """Show all services status"""
        print(f"{Colors.HEADER}{Colors.BOLD}Service Status:{Colors.ENDC}\n")
        
        for service in ServiceManager.SERVICES:
            cmd = ['systemctl', 'is-active', service]
            ret, status, _ = ServiceManager.run_command(cmd)
            
            status = status.strip()
            color = Colors.OKGREEN if status == 'active' else Colors.WARNING
            
            print(f"  {service:<25} {color}{status}{Colors.ENDC}")
        
        print()
    
    @staticmethod
    def logs_user(follow: bool = False):
        """Show user service logs"""
        args = ['-u', 'ezy-user.service']
        if follow:
            args.insert(0, '-f')
        
        cmd = ['journalctl'] + args
        ServiceManager.run_command(cmd, check=False)
    
    @staticmethod
    def logs_admin(follow: bool = False):
        """Show admin service logs"""
        args = ['-u', 'ezy-admin.service']
        if follow:
            args.insert(0, '-f')
        
        cmd = ['journalctl'] + args
        ServiceManager.run_command(cmd, check=False)
    
    @staticmethod
    def logs_all(follow: bool = False, lines: int = 50):
        """Show logs for all services"""
        for service in ServiceManager.SERVICES:
            print(f"\n{Colors.HEADER}{Colors.BOLD}Logs for {service}:{Colors.ENDC}\n")
            
            args = ['-u', service, '-n', str(lines)]
            cmd = ['journalctl'] + args
            ServiceManager.run_command(cmd, check=False)
    
    @staticmethod
    def version():
        """Show application version info"""
        print(f"\n{Colors.HEADER}{Colors.BOLD}EzySpeechTranslate Service Manager{Colors.ENDC}")
        print(f"Version: 1.0")
        print(f"Installation Directory: {ServiceManager.APP_DIR}")
        print(f"Services: {', '.join(ServiceManager.SERVICES)}")
        print()


def print_help():
    """Print help message"""
    help_text = f"""
{Colors.HEADER}{Colors.BOLD}EzySpeechTranslate Service Manager{Colors.ENDC}

Usage: ezy-service <command> [options]

{Colors.BOLD}Service Control Commands:{Colors.ENDC}
  start               Start all services
  stop                Stop all services
  restart             Restart all services
  reload              Reload configuration
  enable              Enable services to start on boot
  disable             Disable services from starting on boot
  status              Show services status

{Colors.BOLD}Log Commands:{Colors.ENDC}
  logs                Show logs for all services (last 50 lines)
  logs:user           Show user service logs
  logs:admin          Show admin service logs
  logs:user -f        Follow user service logs (real-time)
  logs:admin -f       Follow admin service logs (real-time)
  logs -n 100         Show last 100 lines for all services

{Colors.BOLD}Other Commands:{Colors.ENDC}
  version             Show version information
  help                Show this help message

{Colors.BOLD}Examples:{Colors.ENDC}
  sudo ezy-service start
  sudo ezy-service status
  sudo ezy-service restart
  ezy-service logs
  ezy-service logs:user -f
  sudo ezy-service enable

{Colors.BOLD}Note:{Colors.ENDC}
  Most commands require 'sudo' (root privileges).
  Log commands do not require sudo for non-enforcing output.

"""
    print(help_text)


def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print_help()
        sys.exit(0)
    
    command = sys.argv[1].lower()
    
    # Command routing
    if command == 'start':
        ServiceManager.start_services()
    elif command == 'stop':
        ServiceManager.stop_services()
    elif command == 'restart':
        ServiceManager.restart_services()
    elif command == 'reload':
        ServiceManager.reload_services()
    elif command == 'enable':
        ServiceManager.enable_services()
    elif command == 'disable':
        ServiceManager.disable_services()
    elif command == 'status':
        ServiceManager.status_services()
    elif command == 'logs':
        lines = 50
        if len(sys.argv) > 2 and sys.argv[2] == '-n':
            try:
                lines = int(sys.argv[3])
            except (ValueError, IndexError):
                pass
        ServiceManager.logs_all(lines=lines)
    elif command == 'logs:user':
        follow = len(sys.argv) > 2 and sys.argv[2] == '-f'
        ServiceManager.logs_user(follow=follow)
    elif command == 'logs:admin':
        follow = len(sys.argv) > 2 and sys.argv[2] == '-f'
        ServiceManager.logs_admin(follow=follow)
    elif command == 'version':
        ServiceManager.version()
    elif command in ['help', '-h', '--help']:
        print_help()
    else:
        print(f"{Colors.FAIL}Unknown command: {command}{Colors.ENDC}")
        print(f"Use '{Colors.BOLD}ezy-service help{Colors.ENDC}' for usage information.")
        sys.exit(1)


if __name__ == '__main__':
    main()
