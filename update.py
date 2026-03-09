"""
EzySpeechTranslate Update Script
Updates the project from git while preserving config files
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from datetime import datetime


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
        print(f"ℹ {text}")
    
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
    
    def git_pull(self):
        """Pull latest changes from git"""
        self.print_step(2, "Updating from git...")
        
        # Check if git repo exists
        git_dir = self.project_root / ".git"
        if not git_dir.exists():
            self.print_info("Not a git repository, skipping git pull")
            return
        
        try:
            # Fetch all changes
            result = subprocess.run(
                ["git", "fetch", "--all"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                self.print_error(f"Git fetch failed: {result.stderr}")
            
            # Pull changes
            result = subprocess.run(
                ["git", "pull", "origin", "main"],
                cwd=self.project_root,
                capture_output=True,
                text=True
            )
            
            # Git pull can return non-zero if already up-to-date
            # Check for actual errors
            if "fatal" in result.stderr.lower() and "does not exist" in result.stderr.lower():
                # Try master branch instead
                result = subprocess.run(
                    ["git", "pull", "origin", "master"],
                    cwd=self.project_root,
                    capture_output=True,
                    text=True
                )
            
            if result.stdout:
                print(result.stdout)
            
            self.print_success("Git repository updated")
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
