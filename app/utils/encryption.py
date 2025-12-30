"""Data encryption utilities for sensitive history data."""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class DataEncryption:
    """Encrypt/decrypt sensitive data using AES-256-GCM"""

    def __init__(self):
        # Get encryption key from environment
        encryption_key = os.getenv("ENCRYPTION_KEY", "")

        if not encryption_key:
            raise ValueError(
                "ENCRYPTION_KEY environment variable is required for data encryption. "
                "Generate one with: openssl rand -base64 32"
            )

        # Derive a 32-byte key using PBKDF2
        # Use a fixed salt for key derivation (not for encryption)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"grosint_history_encryption_salt_v1",  # Fixed salt for key derivation
            iterations=100000,
        )
        self.key = kdf.derive(encryption_key.encode())
        self.aesgcm = AESGCM(self.key)

    def encrypt(self, data: dict[str, Any] | str | list) -> str:
        """
        Encrypt data and return base64-encoded string.

        Args:
            data: Data to encrypt (dict, str, or list)

        Returns:
            Base64-encoded encrypted string
        """
        try:
            # Convert to JSON string
            json_data = json.dumps(data, default=str)

            # Generate a random nonce (12 bytes for GCM)
            nonce = os.urandom(12)

            # Encrypt
            ciphertext = self.aesgcm.encrypt(nonce, json_data.encode("utf-8"), None)

            # Combine nonce + ciphertext and encode
            encrypted = nonce + ciphertext
            return base64.b64encode(encrypted).decode("utf-8")

        except Exception as e:
            logger.error(f"Encryption error: {e}", exc_info=True)
            raise ValueError(f"Failed to encrypt data: {str(e)}") from e

    def decrypt(self, encrypted_data: str) -> dict[str, Any] | str | list:
        """
        Decrypt base64-encoded encrypted data.

        Args:
            encrypted_data: Base64-encoded encrypted string

        Returns:
            Decrypted data (dict, str, or list)
        """
        try:
            # Decode from base64
            encrypted_bytes = base64.b64decode(encrypted_data.encode("utf-8"))

            # Extract nonce (first 12 bytes) and ciphertext
            nonce = encrypted_bytes[:12]
            ciphertext = encrypted_bytes[12:]

            # Decrypt
            decrypted_bytes = self.aesgcm.decrypt(nonce, ciphertext, None)
            json_data = decrypted_bytes.decode("utf-8")

            # Parse JSON
            return json.loads(json_data)

        except Exception as e:
            logger.error(f"Decryption error: {e}", exc_info=True)
            raise ValueError(f"Failed to decrypt data: {str(e)}") from e


# Global encryption instance (lazy initialization)
_encryption_instance: DataEncryption | None = None
_encryption_unavailable: bool = False


def get_encryption() -> DataEncryption | None:
    """
    Get or create encryption instance.

    Returns:
        DataEncryption instance if ENCRYPTION_KEY is available, None otherwise.
    """
    global _encryption_instance, _encryption_unavailable

    # If we've already determined encryption is unavailable, return None
    if _encryption_unavailable:
        return None

    # If instance exists, return it
    if _encryption_instance is not None:
        return _encryption_instance

    # Try to create instance
    try:
        _encryption_instance = DataEncryption()
        return _encryption_instance
    except ValueError:
        # ENCRYPTION_KEY is missing - mark as unavailable and return None
        _encryption_unavailable = True
        logger.warning(
            "ENCRYPTION_KEY not set - encryption/decryption will be skipped. "
            "Set ENCRYPTION_KEY environment variable to enable encryption."
        )
        return None
