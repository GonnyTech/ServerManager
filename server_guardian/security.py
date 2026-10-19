"""
Security and Encryption module for Server Guardian.
Provides symmetric local encryption using Fernet (AES-128 in CBC mode with HMAC).
"""

import os
from pathlib import Path
from cryptography.fernet import Fernet

DEFAULT_CONFIG_DIR = Path.home() / ".server-guardian"
KEY_FILE = DEFAULT_CONFIG_DIR / "guardian.key"


def get_config_dir() -> Path:
    """Ensure and return the secure configuration directory."""
    config_dir = Path(os.environ.get("SERVER_GUARDIAN_DIR", str(DEFAULT_CONFIG_DIR)))
    config_dir.mkdir(parents=True, exist_ok=True)
    try:
        # Secure directory permissions on POSIX systems (rwx------)
        config_dir.chmod(0o700)
    except (PermissionError, OSError):
        pass
    return config_dir


def get_or_create_key() -> bytes:
    """
    Retrieve existing encryption key or generate a new one with strict permissions (0600).
    """
    config_dir = get_config_dir()
    key_path = config_dir / "guardian.key"

    if key_path.exists():
        with open(key_path, "rb") as f:
            return f.read().strip()

    # Generate new key
    key = Fernet.generate_key()
    with open(key_path, "wb") as f:
        f.write(key)

    try:
        # Strict file permissions on POSIX (rw-------)
        key_path.chmod(0o600)
    except (PermissionError, OSError):
        pass

    return key


def encrypt_secret(plain_text: str) -> str:
    """
    Encrypt a plain text string and return a base64 encoded token string.
    """
    if not plain_text:
        return ""
    key = get_or_create_key()
    f = Fernet(key)
    return f.encrypt(plain_text.encode("utf-8")).decode("utf-8")


def decrypt_secret(cipher_text: str) -> str:
    """
    Decrypt a cipher text token string and return original plain text.
    """
    if not cipher_text:
        return ""
    key = get_or_create_key()
    f = Fernet(key)
    try:
        return f.decrypt(cipher_text.encode("utf-8")).decode("utf-8")
    except Exception as e:
        raise ValueError(f"Failed to decrypt secret: {e}") from e
