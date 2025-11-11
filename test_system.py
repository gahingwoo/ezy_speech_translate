"""
EzySpeechTranslate System Test Script
Tests all components, connections, and SSL certificates
"""

import sys
import os
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


def print_info(message):
    """Print info"""
    print(f"  {Colors.BLUE}ℹ {message}{Colors.END}")


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
        self.admin_url = None
        self.token = None
        self.tests_passed = 0
        self.tests_failed = 0
        self.use_https = False

    def load_config(self):
        """Load configuration"""
        print_test("Loading configuration")
        try:
            with open('config.yaml', 'r') as f:
                self.config = yaml.safe_load(f)

            host = self.config.get('server', {}).get('host', 'localhost')
            if host == '0.0.0.0':
                host = 'localhost'

            main_port = self.config.get('server', {}).get('port', 1915)
            admin_port = self.config.get('admin_server', {}).get('port', 1916)

            # Check if using HTTPS
            self.use_https = os.path.exists('cert.pem') and os.path.exists('key.pem')
            protocol = 'https' if self.use_https else 'http'

            self.base_url = f"{protocol}://{host}:{main_port}"
            self.admin_url = f"{protocol}://{host}:{admin_port}"

            print_pass()
            print_info(f"Main Server: {self.base_url}")
            print_info(f"Admin Server: {self.admin_url}")
            print_info(f"Protocol: {protocol.upper()}")

            self.tests_passed += 1
            return True
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_ssl_certificates(self):
        """Test SSL certificates"""
        print_test("Checking SSL certificates")

        cert_exists = os.path.exists('cert.pem')
        key_exists = os.path.exists('key.pem')

        if cert_exists and key_exists:
            print_pass()

            # Get certificate details
            try:
                import subprocess
                result = subprocess.run(
                    ['openssl', 'x509', '-in', 'cert.pem', '-noout', '-dates'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    for line in result.stdout.strip().split('\n'):
                        print_info(line)

                # Check certificate subject
                result = subprocess.run(
                    ['openssl', 'x509', '-in', 'cert.pem', '-noout', '-subject'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )

                if result.returncode == 0:
                    print_info(result.stdout.strip())

            except FileNotFoundError:
                print_warn("OpenSSL not found - cannot check certificate details")
            except Exception as e:
                print_warn(f"Could not read certificate details: {e}")

            self.tests_passed += 1
            return True

        elif cert_exists or key_exists:
            print_fail("Incomplete certificate files")
            if cert_exists:
                print_info("✓ cert.pem exists")
            else:
                print_info("✗ cert.pem missing")
            if key_exists:
                print_info("✓ key.pem exists")
            else:
                print_info("✗ key.pem missing")

            print_warn("Generate certificates with:")
            print_warn("  openssl req -x509 -newkey rsa:4096 -keyout key.pem \\")
            print_warn("    -out cert.pem -days 365 -nodes")

            self.tests_failed += 1
            return False

        else:
            print_warn("No SSL certificates found (HTTP mode)")
            print_info("Generate certificates with:")
            print_info("  openssl req -x509 -newkey rsa:4096 -keyout key.pem \\")
            print_info("    -out cert.pem -days 365 -nodes")
            print_info("Or run: python setup.py")

            # Not a failure, just a warning
            self.tests_passed += 1
            return True

    def test_dependencies(self):
        """Test required dependencies"""
        print_test("Checking dependencies")

        required_modules = [
            ('flask', 'Flask'),
            ('flask_socketio', 'Flask-SocketIO'),
            ('yaml', 'PyYAML'),
            ('jwt', 'PyJWT'),
            ('eventlet', 'eventlet')
        ]

        missing = []
        found = []

        for module, package in required_modules:
            try:
                __import__(module)
                found.append(package)
            except ImportError:
                missing.append(package)

        if missing:
            print_fail(f"Missing packages: {', '.join(missing)}")
            print_info("Install with: pip install " + ' '.join(missing))
            self.tests_failed += 1
            return False
        else:
            print_pass()
            print_info(f"Found: {', '.join(found)}")
            self.tests_passed += 1
            return True

    def test_audio_devices(self):
        """Test audio device access"""
        print_test("Checking audio devices")

        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]

            if input_devices:
                print_pass()
                print_info(f"Found {len(input_devices)} input device(s)")
                for idx, dev in enumerate(input_devices[:3]):  # Show first 3
                    print_info(f"  [{idx}] {dev['name']}")
                self.tests_passed += 1
                return True
            else:
                print_fail("No input devices found")
                self.tests_failed += 1
                return False
        except ImportError:
            print_warn("sounddevice not installed (optional)")
            print_info("Install with: pip install sounddevice")
            self.tests_passed += 1  # Not critical
            return True
        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_server_connection(self):
        """Test server connection"""
        print_test("Connecting to main server")

        try:
            # Disable SSL verification for self-signed certificates
            response = requests.get(
                f"{self.base_url}/api/health",
                timeout=5,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()
                print_pass()
                print_info(f"Status: {data.get('status')}")
                print_info(f"Clients: {data.get('clients')}")
                print_info(f"Translations: {data.get('translations')}")
                self.tests_passed += 1
                return True
            else:
                print_fail(f"HTTP {response.status_code}")
                self.tests_failed += 1
                return False

        except requests.exceptions.SSLError as e:
            print_fail(f"SSL Error: {str(e)[:50]}...")
            print_warn("Try: pip install --upgrade certifi")
            self.tests_failed += 1
            return False

        except requests.exceptions.ConnectionError:
            print_fail("Server not running")
            print_warn("Start server with: python user_server.py")
            print_info(f"Expected URL: {self.base_url}")
            self.tests_failed += 1
            return False

        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_admin_server_connection(self):
        """Test admin server connection"""
        print_test("Connecting to admin server")

        try:
            response = requests.get(
                f"{self.admin_url}/health",
                timeout=5,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()
                print_pass()
                print_info(f"Service: {data.get('service')}")
                self.tests_passed += 1
                return True
            else:
                print_fail(f"HTTP {response.status_code}")
                self.tests_failed += 1
                return False

        except requests.exceptions.ConnectionError:
            print_fail("Admin server not running")
            print_warn("Start with: python admin_server.py")
            print_info(f"Expected URL: {self.admin_url}")
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
            username = self.config.get('authentication', {}).get('admin_username', 'admin')
            password = self.config.get('authentication', {}).get('admin_password', 'admin')

            response = requests.post(
                f"{self.base_url}/api/login",
                json={'username': username, 'password': password},
                timeout=5,
                verify=False
            )

            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    self.token = data.get('token')
                    print_pass()
                    print_info(f"User: {data.get('username')}")
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
            ('/api/config', 'Config'),
            ('/api/translations', 'Translations'),
        ]

        try:
            all_passed = True
            for endpoint, name in endpoints:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, headers=headers, timeout=5, verify=False)

                if response.status_code not in [200, 201]:
                    print_fail(f"{name} returned {response.status_code}")
                    all_passed = False
                    break

            if all_passed:
                print_pass()
                print_info(f"Tested {len(endpoints)} endpoints")
                self.tests_passed += 1
                return True
            else:
                self.tests_failed += 1
                return False

        except Exception as e:
            print_fail(str(e))
            self.tests_failed += 1
            return False

    def test_file_structure(self):
        """Test file and directory structure"""
        print_test("Checking file structure")

        required_files = [
            'user_server.py',
            'admin_server.py',
            'config.yaml',
            'requirements.txt'
        ]

        required_dirs = [
            'templates',
            'static',
            'logs',
            'exports',
            'data'
        ]

        optional_files = [
            'cert.pem',
            'key.pem',
            'README.md',
            'setup.py'
        ]

        missing_files = [f for f in required_files if not os.path.exists(f)]
        missing_dirs = [d for d in required_dirs if not os.path.exists(d)]

        if missing_files or missing_dirs:
            print_fail()
            if missing_files:
                print_info(f"Missing files: {', '.join(missing_files)}")
            if missing_dirs:
                print_info(f"Missing directories: {', '.join(missing_dirs)}")
            self.tests_failed += 1
            return False
        else:
            print_pass()

            # Check optional files
            found_optional = [f for f in optional_files if os.path.exists(f)]
            if found_optional:
                print_info(f"Optional: {', '.join(found_optional)}")

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

            if self.use_https:
                print(f"\n{Colors.BLUE}Access URLs:{Colors.END}")
                print(f"  Main:  {self.base_url}")
                print(f"  Admin: {self.admin_url}")
                print(f"\n{Colors.YELLOW}Note: You'll see a certificate warning (self-signed cert)")
                print(f"      Click 'Advanced' → 'Proceed to localhost'{Colors.END}")
        else:
            print(f"\n{Colors.RED}{Colors.BOLD}✗ Some tests failed.{Colors.END}")
            print(f"\n{Colors.YELLOW}Please fix the issues and run tests again.{Colors.END}")

    def run_all_tests(self):
        """Run all tests"""
        print_header("EzySpeechTranslate System Test")
        print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Suppress SSL warnings for testing
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        # Configuration and dependencies
        print_header("Configuration & Dependencies")

        if not self.load_config():
            print("\n❌ Cannot proceed without configuration")
            return False

        self.test_ssl_certificates()
        self.test_dependencies()
        self.test_audio_devices()
        self.test_file_structure()

        # Server tests
        print_header("Server Tests")
        main_server_running = self.test_server_connection()
        admin_server_running = self.test_admin_server_connection()

        if main_server_running:
            self.test_authentication()
            self.test_api_endpoints()
        else:
            print_warn("Skipping server-dependent tests")
            print_info("Start server with: python user_server.py")

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