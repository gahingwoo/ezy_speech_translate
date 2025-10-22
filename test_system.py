"""
EzySpeechTranslate System Test Script
Tests all components and connections
"""

import sys
import time
import requests
import json
import yaml
from datetime import datetime


class Colors:
    """ANSI color codes"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_test(name):
    """Print test name"""
    print(f"\n{Colors.BLUE}[TEST]{Colors.END} {name}...", end=" ")
    sys.stdout.flush()


def print_pass():
    """Print pass"""
    print(f"{Colors.GREEN}✓ PASS{Colors.END}")


def print_fail(message=""):
    """Print fail"""
    print(f"{Colors.RED}✗ FAIL{Colors.END}")
    if message:
        print(f"  {Colors.RED}Error: {message}{Colors.END}")


def print_warn(message):
    """Print warning"""
    print(f"{Colors.YELLOW}⚠ WARNING: {message}{Colors.END}")


def print_header(text):
    """Print section header"""
    print(f"\n{Colors.BOLD}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{Colors.END}\n")


class SystemTester:
    """System testing class"""

    def __init__(self):
        self.config = None
        self.base_url = None
        self.token = None
        self.tests_passed = 0
        self.tests_failed = 0

    def load_config(self):
        """Load configuration"""
        print_test("Loading configuration")
        try:
            with open('config.yaml', 'r') as f:
                self.config = yaml.safe_load(f)

            host = self.config.get('server', {}).get('host', 'localhost')
            if host == '0.0.0.0':
                host = 'localhost'
            port = self.config.get('server', {}).get('port', 5000)
            self.base_url = f"http://{host}:{port}"

            print_pass()
            self.tests_passed += 1
            return True
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_dependencies(self):
        """Test required dependencies"""
        print_test("Checking dependencies")

        required_modules = [
            'flask',
            'flask_socketio',
            'sounddevice',
            'numpy',
            'faster_whisper',
            'yaml',
            'jwt'
        ]

        missing = []
        for module in required_modules:
            try:
                __import__(module)
            except ImportError:
                missing.append(module)

        if missing:
            print_fail(f"Missing modules: {', '.join(missing)}")
            self.tests_failed += 1
            return False
        else:
            print_pass()
            self.tests_passed += 1
            return True

    def test_ffmpeg(self):
        """Test FFmpeg installation"""
        print_test("Checking FFmpeg")

        import subprocess
        try:
            result = subprocess.run(['ffmpeg', '-version'],
                                    capture_output=True, timeout=5)
            if result.returncode == 0:
                print_pass()
                self.tests_passed += 1
                return True
            else:
                print_fail("FFmpeg not working properly")
                self.tests_failed += 1
                return False
        except FileNotFoundError:
            print_fail("FFmpeg not installed")
            self.tests_failed += 1
            return False
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_audio_devices(self):
        """Test audio device access"""
        print_test("Checking audio devices")

        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]

            if input_devices:
                print_pass()
                print(f"  Found {len(input_devices)} input device(s)")
                self.tests_passed += 1
                return True
            else:
                print_fail("No input devices found")
                self.tests_failed += 1
                return False
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_server_connection(self):
        """Test server connection"""
        print_test("Connecting to server")

        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=5)
            if response.status_code == 200:
                data = response.json()
                print_pass()
                print(f"  Status: {data.get('status')}")
                print(f"  Clients: {data.get('clients')}")
                self.tests_passed += 1
                return True
            else:
                print_fail(f"HTTP {response.status_code}")
                self.tests_failed += 1
                return False
        except requests.exceptions.ConnectionError:
            print_fail("Server not running")
            print_warn("Please start the server with: python app.py")
            self.tests_failed += 1
            return False
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_authentication(self):
        """Test authentication"""
        print_test("Testing authentication")

        try:
            username = self.config.get('authentication', {}).get('admin_username')
            password = self.config.get('authentication', {}).get('admin_password')

            response = requests.post(
                f"{self.base_url}/api/login",
                json={'username': username, 'password': password},
                timeout=5
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.token = data.get('token')
                    print_pass()
                    self.tests_passed += 1
                    return True
                else:
                    print_fail("Login failed")
                    self.tests_failed += 1
                    return False
            else:
                print_fail(f"HTTP {response.status_code}")
                self.tests_failed += 1
                return False
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_api_endpoints(self):
        """Test API endpoints"""
        print_test("Testing API endpoints")

        if not self.token:
            print_fail("No authentication token")
            self.tests_failed += 1
            return False

        headers = {'Authorization': f'Bearer {self.token}'}

        endpoints = [
            ('/api/config', 'GET'),
            ('/api/translations', 'GET'),
        ]

        try:
            for endpoint, method in endpoints:
                url = f"{self.base_url}{endpoint}"

                if method == 'GET':
                    response = requests.get(url, headers=headers, timeout=5)
                else:
                    response = requests.post(url, headers=headers, timeout=5)

                if response.status_code not in [200, 201]:
                    print_fail(f"{endpoint} returned {response.status_code}")
                    self.tests_failed += 1
                    return False

            print_pass()
            self.tests_passed += 1
            return True

        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_whisper_model(self):
        """Test Whisper model loading"""
        print_test("Testing Whisper model")

        try:
            from faster_whisper import WhisperModel

            model_size = self.config.get('whisper', {}).get('model_size', 'base')
            device = self.config.get('whisper', {}).get('device', 'cpu')
            compute_type = self.config.get('whisper', {}).get('compute_type', 'int8')

            print(f"\n  Loading {model_size} model...", end=" ")
            sys.stdout.flush()

            model = WhisperModel(model_size, device=device, compute_type=compute_type)

            print_pass()
            print(f"  Model: {model_size}")
            print(f"  Device: {device}")
            self.tests_passed += 1
            return True

        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_file_structure(self):
        """Test file and directory structure"""
        print_test("Checking file structure")

        import os

        required_files = [
            'app.py',
            'admin_gui.py',
            'config.yaml',
            'requirements.txt',
            'README.md'
        ]

        required_dirs = [
            'templates',
            'logs',
            'exports',
            'data'
        ]

        missing_files = [f for f in required_files if not os.path.exists(f)]
        missing_dirs = [d for d in required_dirs if not os.path.exists(d)]

        if missing_files or missing_dirs:
            print_fail()
            if missing_files:
                print(f"  Missing files: {', '.join(missing_files)}")
            if missing_dirs:
                print(f"  Missing directories: {', '.join(missing_dirs)}")
            self.tests_failed += 1
            return False
        else:
            print_pass()
            self.tests_passed += 1
            return True

    def print_summary(self):
        """Print test summary"""
        print_header("Test Summary")

        total = self.tests_passed + self.tests_failed
        percentage = (self.tests_passed / total * 100) if total > 0 else 0

        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.tests_passed}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.tests_failed}{Colors.END}")
        print(f"Success Rate: {percentage:.1f}%")

        if self.tests_failed == 0:
            print(f"\n{Colors.GREEN}{Colors.BOLD}✓ All tests passed!{Colors.END}")
            print(f"\n{Colors.GREEN}System is ready to use.{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ Some tests failed.{Colors.END}")
            print(f"\n{Colors.YELLOW}Please fix the issues and run tests again.{Colors.END}")

    def run_all_tests(self):
        """Run all tests"""
        print_header("EzySpeechTranslate System Test")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Configuration and dependencies
        if not self.load_config():
            print("\n❌ Cannot proceed without configuration")
            return False

        self.test_dependencies()
        self.test_ffmpeg()
        self.test_audio_devices()
        self.test_file_structure()

        # Server tests
        print_header("Server Tests")
        server_running = self.test_server_connection()

        if server_running:
            self.test_authentication()
            self.test_api_endpoints()
        else:
            print_warn("Skipping server-dependent tests")

        # Model test
        print_header("Model Tests")
        self.test_whisper_model()

        # Summary
        self.print_summary()

        return self.tests_failed == 0


def main():
    """Main entry point"""
    tester = SystemTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}Tests interrupted by user{Colors.END}")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n{Colors.RED}Test failed with error: {e}{Colors.END}")
        import traceback

        traceback.print_exc()
        sys.exit(1)