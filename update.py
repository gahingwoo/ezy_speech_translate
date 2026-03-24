"""
EzySpeechTranslate Update Script
Updates the project from git while preserving config files
"""

import os
import sys
import subprocess
import shutil
import time
import socket
from pathlib import Path
from datetime import datetime


REMOTE_URL = "https://github.com/gahingwoo/ezy_speech_translate.git"


class UpdateManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_dir = self.project_root / "config"
        self.backup_dir = self.project_root / ".config_backup"
        self.venv_dir = self.project_root / "venv"
        self.python_exe = self._get_python_executable()
        
    def _get_python_executable(self):
        """Get the correct Python executable path"""
        if self.venv_dir.exists():
            # If virtual environment exists, use it
            if sys.platform == "win32":
                return str(self.venv_dir / "Scripts" / "python.exe")
            else:
                return str(self.venv_dir / "bin" / "python")
        return sys.executable
    
    def print_header(self, text):
        """Prints a header"""
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60 + "\n")
    
    def print_step(self, step_num, text):
        """Prints a step"""
        print(f"[{step_num}] {text}")
    
    def print_success(self, text):
        """Prints success message"""
        print(f"✓ {text}")
    
    def print_error(self, text):
        """Prints error message"""
        print(f"✗ {text}")
        sys.exit(1)
    
    def print_info(self, text):
        """Prints info message"""
        print(f"{text}")
    
    def backup_config(self):
        """Backup config directory"""
        self.print_step(1, "Backing up configuration files...")
        
        if not self.config_dir.exists():
            self.print_info("Config directory does not exist")
            return
        
        # Remove old backup
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        
        # Create backup
        shutil.copytree(self.config_dir, self.backup_dir)
        self.print_success(f"Config backed up to {self.backup_dir}")
    
    def _check_network(self):
        """Check basic network connectivity"""
        try:
            socket.create_connection(("github.com", 443), timeout=5)
            return True
        except Exception:
            return False
    
    def _init_git_repo(self):
        """Initialize git repo and set remote origin"""
        git_dir = self.project_root / ".git"
        if git_dir.exists():
            self.print_info("Removing existing .git directory for re-initialization...")
            shutil.rmtree(git_dir)

        self.print_info("Initializing git repository...")
        subprocess.run(["git", "init"], cwd=self.project_root, check=True,
                       capture_output=True, text=True)
        subprocess.run(["git", "remote", "add", "origin", REMOTE_URL],
                       cwd=self.project_root, check=True, capture_output=True, text=True)
        self.print_success(f"Git repository initialized with remote: {REMOTE_URL}")

    def git_pull(self):
        """Pull latest changes from git with retry logic"""
        self.print_step(2, "Updating from git...")

        # Check network connectivity
        if not self._check_network():
            self.print_error("Network error: Cannot reach github.com. Check your internet connection.")

        # Initialize repo if .git is missing
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            self.print_info(".git directory not found, initializing repository...")
            self._init_git_repo()

        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                # Fetch all changes
                self.print_info(f"Fetching from git (attempt {retry_count + 1}/{max_retries})...")
                result = subprocess.run(
                    ["git", "fetch", "--all"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True,
                    timeout=60
                )

                if result.returncode != 0:
                    if "TLS" in result.stderr or "SSL" in result.stderr or "handshake" in result.stderr.lower():
                        # TLS/SSL issue — retry with backoff
                        retry_count += 1
                        if retry_count < max_retries:
                            wait_time = 2 ** retry_count
                            self.print_info(f"TLS connection issue, retrying in {wait_time}s...")
                            time.sleep(wait_time)
                            continue
                        else:
                            self.print_error(f"Git fetch failed after {max_retries} attempts: {result.stderr}")
                    else:
                        # Other fetch error — re-initialize .git and retry
                        self.print_info(f"Git fetch failed: {result.stderr.strip()}")
                        self.print_info("Re-initializing git repository and retrying...")
                        self._init_git_repo()
                        retry_count += 1
                        if retry_count < max_retries:
                            time.sleep(2)
                            continue
                        else:
                            self.print_error(f"Git fetch failed after re-initialization: {result.stderr}")

                # Pull changes — try main branch first, then master
                pull_success = False
                for branch in ["main", "master"]:
                    result = subprocess.run(
                        ["git", "pull", "origin", branch],
                        cwd=self.project_root,
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if result.returncode == 0:
                        if result.stdout:
                            print(result.stdout)
                        self.print_success(f"Git repository updated from {branch} branch")
                        pull_success = True
                        break
                    elif "does not exist" not in result.stderr.lower():
                        # Real error, not just missing branch
                        break

                if pull_success:
                    break
                else:
                    retry_count += 1
                    if retry_count < max_retries:
                        wait_time = 2 ** retry_count
                        self.print_info(f"Retrying git pull in {wait_time}s...")
                        time.sleep(wait_time)
                    else:
                        self.print_error(f"Git pull failed after {max_retries} attempts")

            except subprocess.TimeoutExpired:
                retry_count += 1
                if retry_count < max_retries:
                    self.print_info(f"Git operation timeout, retrying in {2 ** retry_count}s...")
                    time.sleep(2 ** retry_count)
                else:
                    self.print_error(f"Git operations timed out after {max_retries} attempts")
            except Exception as e:
                self.print_error(f"Git update failed: {str(e)}")
    
    def restore_config(self):
        """Restore config files from backup"""
        self.print_step(3, "Restoring configuration files...")
        
        if not self.backup_dir.exists():
            self.print_info("No config backup found, skipping restore")
            return
        
        # Remove config directory if it exists
        if self.config_dir.exists():
            shutil.rmtree(self.config_dir)
        
        # Restore from backup
        shutil.copytree(self.backup_dir, self.config_dir)
        self.print_success("Config files restored")
    
    def update_dependencies(self):
        """Update dependencies from requirements.txt"""
        self.print_step(4, "Updating Python dependencies...")
        
        requirements_file = self.project_root / "requirements.txt"
        
        if not requirements_file.exists():
            self.print_error("requirements.txt not found")
        
        try:
            # Use the appropriate Python executable
            if self.venv_dir.exists():
                # If using venv, use pip from venv
                if sys.platform == "win32":
                    pip_exe = str(self.venv_dir / "Scripts" / "pip.exe")
                else:
                    pip_exe = str(self.venv_dir / "bin" / "pip")
            else:
                pip_exe = self.python_exe.replace("python", "pip")
            
            result = subprocess.run(
                [pip_exe, "install", "-q", "-r", str(requirements_file)],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.print_error(f"Dependency update failed: {result.stderr}")
            
            self.print_success("Dependencies updated")
        except Exception as e:
            self.print_error(f"Failed to update dependencies: {str(e)}")
    
    def clean_pycache(self):
        """Clean Python cache files"""
        self.print_step(5, "Cleaning Python cache files...")
        
        removed_count = 0
        
        # Find and remove __pycache__ directories
        for pycache_dir in self.project_root.glob("**/__pycache__"):
            try:
                shutil.rmtree(pycache_dir)
                removed_count += 1
            except Exception as e:
                self.print_info(f"Could not remove {pycache_dir}: {str(e)}")
        
        # Find and remove .pyc files
        for pyc_file in self.project_root.glob("**/*.pyc"):
            try:
                pyc_file.unlink()
                removed_count += 1
            except Exception as e:
                self.print_info(f"Could not remove {pyc_file}: {str(e)}")
        
        self.print_success(f"Cleaned {removed_count} cache items")
    
    def cleanup_backup(self):
        """Clean up backup directory"""
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
                self.print_info("Temporary backup directory removed")
            except Exception as e:
                self.print_info(f"Could not remove backup directory: {str(e)}")
    
    def run(self):
        """Execute the full update"""
        self.print_header("EzySpeechTranslate Update")
        
        print(f"Project root: {self.project_root}")
        print(f"Python executable: {self.python_exe}\n")
        
        try:
            self.backup_config()
            self.git_pull()
            self.restore_config()
            self.update_dependencies()
            self.clean_pycache()
            self.cleanup_backup()
            
            self.print_header("Update Complete! ✓")
            print("Your project has been updated successfully.")
            print("Config files were preserved during the update.\n")
        except KeyboardInterrupt:
            print("\n\nUpdate cancelled by user")
            self.cleanup_backup()
            sys.exit(1)
        except Exception as e:
            self.print_error(f"Unexpected error: {str(e)}")


def main():
    """Main entry point"""
    manager = UpdateManager()
    manager.run()


if __name__ == "__main__":
    main()
