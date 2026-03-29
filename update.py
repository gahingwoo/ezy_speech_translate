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


REMOTE_URL = "https://github.com/gahingwoo/ezy_speech_translate.git"


class UpdateManager:
    def __init__(self):
        self.project_root = Path(__file__).parent
        self.config_dir = self.project_root / "config"
        self.backup_dir = Path("/tmp") / f"ezyspeech_config_backup_{os.getuid()}"
        self.venv_dir = self.project_root / "venv"
        self.python_exe = self._get_python_executable()

    def _get_python_executable(self):
        if self.venv_dir.exists():
            if sys.platform == "win32":
                return str(self.venv_dir / "Scripts" / "python.exe")
            else:
                return str(self.venv_dir / "bin" / "python")
        return sys.executable

    def print_header(self, text):
        print("\n" + "=" * 60)
        print(f"  {text}")
        print("=" * 60 + "\n")

    def print_step(self, step_num, text):
        print(f"[{step_num}] {text}")

    def print_success(self, text):
        print(f"✓ {text}")

    def print_error(self, text):
        print(f"✗ {text}")
        sys.exit(1)

    def print_info(self, text):
        print(f"{text}")

    def backup_config(self):
        self.print_step(1, "Backing up configuration files...")
        if not self.config_dir.exists():
            self.print_info("Config directory does not exist")
            return
        if self.backup_dir.exists():
            shutil.rmtree(self.backup_dir)
        shutil.copytree(self.config_dir, self.backup_dir)
        self.print_success(f"Config backed up to {self.backup_dir}")

    def _check_network(self):
        try:
            socket.create_connection(("github.com", 443), timeout=5)
            return True
        except Exception:
            return False

    def git_pull(self):
        """Pull latest changes via fetch + reset --hard (works regardless of local state)"""
        self.print_step(2, "Updating from git...")

        if not self._check_network():
            self.print_error("Network error: Cannot reach github.com. Check your internet connection.")

        git_dir = self.project_root / ".git"

        # If no .git at all, just clone fresh into a temp dir then move files over
        if not git_dir.exists():
            self.print_info("No git repository found — cloning fresh...")
            self._clone_fresh()
            return

        # Ensure remote origin is set
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=self.project_root, capture_output=True, text=True
        )
        if result.returncode != 0:
            self.print_info("Remote 'origin' missing — setting it now...")
            subprocess.run(
                ["git", "remote", "add", "origin", REMOTE_URL],
                cwd=self.project_root, check=True, capture_output=True
            )

        # Fix dubious ownership (project dir owned by service user, run as root)
        subprocess.run(
            ["git", "config", "--global", "--add", "safe.directory", str(self.project_root)],
            capture_output=True
        )

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            self.print_info(f"Fetching from git (attempt {attempt}/{max_retries})...")
            try:
                # Fetch all updates, prune deleted remote branches, and sync tags
                result = subprocess.run(
                    ["git", "fetch", "origin", "--all", "--prune", "--tags"],
                    cwd=self.project_root, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    raise RuntimeError(f"fetch failed: {result.stderr.strip()}")

                # Detect default branch
                target_branch = None
                for branch in ["main", "master"]:
                    check = subprocess.run(
                        ["git", "ls-remote", "--heads", "origin", branch],
                        cwd=self.project_root, capture_output=True, text=True, timeout=30
                    )
                    if check.stdout.strip():
                        target_branch = branch
                        break
                if not target_branch:
                    self.print_error("Could not find 'main' or 'master' branch on remote.")

                self.print_info(f"Resetting to origin/{target_branch}...")
                subprocess.run(
                    ["git", "checkout", "-B", target_branch, f"origin/{target_branch}"],
                    cwd=self.project_root, capture_output=True, text=True, timeout=60
                )
                result = subprocess.run(
                    ["git", "reset", "--hard", f"origin/{target_branch}"],
                    cwd=self.project_root, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    raise RuntimeError(f"reset failed: {result.stderr.strip()}")

                # Clean up untracked files to ensure complete sync
                # -f: force, -d: remove directories, -e: exclude pattern
                result = subprocess.run(
                    ["git", "clean", "-fd"],
                    cwd=self.project_root, capture_output=True, text=True, timeout=60
                )
                if result.returncode != 0:
                    self.print_info(f"Warning: git clean had issues: {result.stderr.strip()}")

                self.print_success(f"Updated from {target_branch} branch (all new files synced)")
                return

            except subprocess.TimeoutExpired:
                err = "operation timed out"
            except RuntimeError as e:
                err = str(e)

            if attempt < max_retries:
                wait = 2 ** attempt
                self.print_info(f"Error: {err} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                self.print_error(f"Git update failed after {max_retries} attempts.\nLast error: {err}")

    def _clone_fresh(self):
        """Clone into a temp dir, move files over (preserves project_root path)"""
        tmp_dir = Path("/tmp") / "ezyspeech_clone_tmp"
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            self.print_info(f"Cloning repository (attempt {attempt}/{max_retries})...")
            try:
                result = subprocess.run(
                    ["git", "clone", REMOTE_URL, str(tmp_dir)],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    break
                err = result.stderr.strip()
            except subprocess.TimeoutExpired:
                err = "clone timed out"

            if attempt < max_retries:
                wait = 2 ** attempt
                self.print_info(f"Clone failed: {err} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                self.print_error(f"Git clone failed after {max_retries} attempts.\nLast error: {err}")

        # Move .git and all non-config files into project_root
        for item in tmp_dir.iterdir():
            dest = self.project_root / item.name
            if item.name == "config":
                continue  # config is restored separately from backup
            if dest.exists():
                if dest.is_dir():
                    shutil.rmtree(dest)
                else:
                    dest.unlink()
            shutil.move(str(item), str(dest))

        shutil.rmtree(tmp_dir, ignore_errors=True)
        self.print_success("Repository cloned successfully")

    def restore_config(self):
        self.print_step(3, "Restoring configuration files...")
        if not self.backup_dir.exists():
            self.print_info("No config backup found, skipping restore")
            return
        if self.config_dir.exists():
            shutil.rmtree(self.config_dir)
        shutil.copytree(self.backup_dir, self.config_dir)
        self.print_success("Config files restored")

    def update_dependencies(self):
        self.print_step(4, "Updating Python dependencies...")
        requirements_file = self.project_root / "requirements.txt"
        if not requirements_file.exists():
            self.print_error("requirements.txt not found")
        try:
            if self.venv_dir.exists():
                pip_exe = str(self.venv_dir / ("Scripts/pip.exe" if sys.platform == "win32" else "bin/pip"))
            else:
                pip_exe = self.python_exe.replace("python", "pip")
            result = subprocess.run(
                [pip_exe, "install", "-q", "-r", str(requirements_file)],
                cwd=self.project_root, capture_output=True, text=True
            )
            if result.returncode != 0:
                self.print_error(f"Dependency update failed: {result.stderr}")
            self.print_success("Dependencies updated")
        except Exception as e:
            self.print_error(f"Failed to update dependencies: {str(e)}")

    def clean_pycache(self):
        self.print_step(5, "Cleaning Python cache files...")
        removed_count = 0
        for pycache_dir in self.project_root.glob("**/__pycache__"):
            try:
                shutil.rmtree(pycache_dir)
                removed_count += 1
            except Exception as e:
                self.print_info(f"Could not remove {pycache_dir}: {e}")
        for pyc_file in self.project_root.glob("**/*.pyc"):
            try:
                pyc_file.unlink()
                removed_count += 1
            except Exception as e:
                self.print_info(f"Could not remove {pyc_file}: {e}")
        self.print_success(f"Cleaned {removed_count} cache items")

    def cleanup_backup(self):
        if self.backup_dir.exists():
            try:
                shutil.rmtree(self.backup_dir)
                self.print_info("Temporary backup directory removed")
            except Exception as e:
                self.print_info(f"Could not remove backup directory: {e}")

    def run(self):
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
    manager = UpdateManager()
    manager.run()


if __name__ == "__main__":
    main()