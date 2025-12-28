import os
import yaml
import json
import hashlib
import base64
from cryptography.fernet import Fernet, InvalidToken
import socket
import getpass
from pathlib import Path


class MachineBoundEncryption:
    """Simple Key Decryption Utility"""
    
    @staticmethod
    def get_machine_derived_key():
        """Generates decryption key based on machine features (hostname and username)."""
        
        machine_id = f"{socket.gethostname()}{getpass.getuser()}"
        key_hash = hashlib.sha256(machine_id.encode()).digest()
        return base64.urlsafe_b64encode(key_hash)
    
    @staticmethod
    def decrypt_xor(ciphertext: str) -> str:
        """Decrypts the ciphertext."""
        try:
            key = MachineBoundEncryption.get_machine_derived_key()
            encrypted_bytes = base64.b64decode(ciphertext.encode())
            decrypted_bytes = []
            
            for i, byte in enumerate(encrypted_bytes):
                key_char = key[i % len(key)]
                decrypted_bytes.append(byte ^ key_char)
            
            return bytes(decrypted_bytes).decode()
        except:
            return None


class FernetSecrets:
    """Handles Fernet-based secrets encryption/decryption and migration from legacy XOR."""

    @staticmethod
    def load_key(key_path: Path):
        try:
            return key_path.read_bytes()
        except Exception:
            return None

    @staticmethod
    def decrypt_with_fernet(token: str, key: bytes):
        try:
            f = Fernet(key)
            return f.decrypt(token.encode()).decode()
        except (InvalidToken, Exception):
            return None

    @staticmethod
    def encrypt_with_fernet(value: str, key: bytes):
        f = Fernet(key)
        return f.encrypt(value.encode()).decode()


class SecureConfig:
    """Secure Configuration Loader - Loads config and injects decrypted secrets."""
    
    def __init__(self, config_path='config/config.yaml', secrets_path=None):
        self.config_path = Path(config_path)
        # Default secrets file lives beside config.yaml unless overridden
        if secrets_path is None:
            # Use `secrets.key` (JSON) as the canonical secrets file (contains Fernet key + tokens)
            self.secrets_key_path = self.config_path.parent / 'secrets.key'
        else:
            self.secrets_key_path = Path(secrets_path)
        self.data = {}
        self._load_config()
        self._load_secrets()
    
    def _load_config(self):
        """Loads the YAML configuration."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.data = yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"Error: Configuration file not found at {self.config_path}")
            self.data = {}
    
    def _load_secrets(self):
        """Loads and decrypts secrets from the machine-bound file."""
        # New flow: secrets are stored in `secrets.key` as JSON containing Fernet key and tokens.
        key_path = self.secrets_key_path

        # If old secrets.enc exists, attempt migration into secrets.key then remove it
        old_secrets_path = self.config_path.parent / 'secrets.enc'
        if old_secrets_path.exists() and not key_path.exists():
            try:
                with open(old_secrets_path, 'r') as f:
                    old_enc = json.load(f)

                # Try legacy XOR decryption
                admin_pw = MachineBoundEncryption.decrypt_xor(old_enc.get('admin_password', ''))
                jwt_s = MachineBoundEncryption.decrypt_xor(old_enc.get('jwt_secret', ''))
                server_k = MachineBoundEncryption.decrypt_xor(old_enc.get('server_secret_key', ''))

                if admin_pw or jwt_s or server_k:
                    # Create Fernet key and encrypted tokens
                    new_key = Fernet.generate_key()
                    f = Fernet(new_key)
                    new_data = {
                        'fernet_key': new_key.decode(),
                        'admin_password': f.encrypt(admin_pw.encode()).decode() if admin_pw else '',
                        'jwt_secret': f.encrypt(jwt_s.encode()).decode() if jwt_s else '',
                        'server_secret_key': f.encrypt(server_k.encode()).decode() if server_k else ''
                    }
                    try:
                        key_path.write_text(json.dumps(new_data, indent=2))
                        try:
                            os.chmod(key_path, 0o600)
                        except Exception:
                            pass
                        # Remove old secrets.enc
                        try:
                            old_secrets_path.unlink()
                        except Exception:
                            pass
                        print("Info: Migrated legacy secrets.enc into secrets.key and removed secrets.enc")
                    except Exception as e:
                        print(f"Warning: Failed writing secrets.key during migration: {e}")

            except Exception:
                # If migration fails, continue and attempt to load secrets.key below
                pass

        if not key_path.exists():
            print(f"Warning: secrets.key not found at {key_path}, using defaults from config.yaml")
            return
        
        try:
            # Load secrets.key JSON format: {fernet_key, admin_password, jwt_secret, server_secret_key}
            try:
                raw = json.loads(key_path.read_text())
            except Exception as e:
                print(f"Warning: Failed to read secrets.key: {e}")
                return

            fernet_key = raw.get('fernet_key')
            if not fernet_key:
                print("Warning: secrets.key missing 'fernet_key' entry; using defaults from config.yaml")
                return

            key_bytes = fernet_key.encode()
            f = Fernet(key_bytes)

            def safe_decrypt(field):
                token = raw.get(field, '')
                if not token:
                    return None
                try:
                    return f.decrypt(token.encode()).decode()
                except Exception:
                    return None

            admin_password = safe_decrypt('admin_password')
            jwt_secret = safe_decrypt('jwt_secret')
            server_secret_key = safe_decrypt('server_secret_key')

            # Inject into config
            if admin_password and 'authentication' in self.data:
                self.data['authentication']['admin_password'] = admin_password

            if jwt_secret and 'authentication' in self.data:
                self.data['authentication']['jwt_secret'] = jwt_secret

            if server_secret_key and 'server' in self.data:
                self.data['server']['secret_key'] = server_secret_key
            
        except Exception as e:
            print(f"Warning: Failed to load secrets: {e}")
    
    def get(self, *keys, default=None):
        """Safely retrieves a configuration value using nested keys."""
        val = self.data
        for key in keys:
            if isinstance(val, dict):
                val = val.get(key)
                if val is None:
                    return default
            else:
                return default
        return val if val is not None else default