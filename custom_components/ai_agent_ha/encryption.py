"""Encryption at rest for sensitive data in AI Agent HA integration.

This module provides encryption utilities for API keys, conversation history,
and other sensitive data stored in Home Assistant storage.
"""

import base64
import logging
import os
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

_LOGGER = logging.getLogger(__name__)

# Environment variable for custom encryption key
ENV_ENCRYPTION_KEY = "AI_AGENT_HA_ENCRYPTION_KEY"


class EncryptionManager:
    """Manages encryption and decryption of sensitive data."""

    def __init__(self, hass, encryption_key: Optional[str] = None):
        """Initialize the encryption manager.

        Args:
            hass: Home Assistant instance.
            encryption_key: Optional encryption key. If not provided,
                          will use environment variable or generate one.
        """
        self.hass = hass
        self._fernet = None
        self._encryption_key = encryption_key

    def _get_encryption_key(self) -> bytes:
        """Get the encryption key.

        Returns:
            Encryption key as bytes.
        """
        if self._encryption_key:
            key_bytes = self._encryption_key.encode()
        else:
            key_bytes = os.environ.get(ENV_ENCRYPTION_KEY, "").encode()

        if not key_bytes:
            # Generate a key and log a warning
            _LOGGER.warning(
                "No encryption key provided for AI Agent HA. "
                "Set %s environment variable for encrypted storage.",
                ENV_ENCRYPTION_KEY,
            )
            # Use a default key (NOT SECURE - just for functionality)
            key_bytes = b"default-dev-key-do-not-use-in-production-12"

        # Derive a proper 32-byte key using PBKDF2
        salt = b"ai_agent_ha_salt"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(key_bytes))
        return key

    def _get_fernet(self) -> Fernet:
        """Get or create Fernet encryption instance."""
        if self._fernet is None:
            key = self._get_encryption_key()
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt(self, data: str) -> str:
        """Encrypt a string.

        Args:
            data: Plain text string to encrypt.

        Returns:
            Encrypted string as base64.
        """
        try:
            fernet = self._get_fernet()
            encrypted = fernet.encrypt(data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            _LOGGER.error("Encryption failed: %s", e)
            return None

    def decrypt(self, encrypted_data: str) -> Optional[str]:
        """Decrypt an encrypted string.

        Args:
            encrypted_data: Encrypted base64 string.

        Returns:
            Decrypted string or None if decryption failed.
        """
        try:
            fernet = self._get_fernet()
            decoded = base64.urlsafe_b64decode(encrypted_data)
            decrypted = fernet.decrypt(decoded)
            return decrypted.decode()
        except InvalidToken:
            _LOGGER.error("Decryption failed - invalid token or wrong key")
            return None
        except Exception as e:
            _LOGGER.error("Decryption failed: %s", e)
            return None

    def encrypt_dict(self, data: Dict[str, Any]) -> Optional[str]:
        """Encrypt a dictionary as JSON.

        Args:
            data: Dictionary to encrypt.

        Returns:
            Encrypted string or None.
        """
        import json
        try:
            json_str = json.dumps(data)
            return self.encrypt(json_str)
        except Exception as e:
            _LOGGER.error("Failed to encrypt dictionary: %s", e)
            return None

    def decrypt_dict(self, encrypted_data: str) -> Optional[Dict[str, Any]]:
        """Decrypt an encrypted JSON dictionary.

        Args:
            encrypted_data: Encrypted base64 string.

        Returns:
            Decrypted dictionary or None.
        """
        import json
        try:
            json_str = self.decrypt(encrypted_data)
            if json_str:
                return json.loads(json_str)
            return None
        except Exception as e:
            _LOGGER.error("Failed to decrypt dictionary: %s", e)
            return None

    def mask_key(self, key: str, visible_chars: int = 4) -> str:
        """Mask an API key for safe display.

        Args:
            key: The API key to mask.
            visible_chars: Number of characters to show at the start.

        Returns:
            Masked key string.
        """
        if not key or len(key) <= visible_chars:
            return "***"
        return key[:visible_chars] + "*" * (len(key) - visible_chars)

    def is_encrypted(self, data: str) -> bool:
        """Check if data appears to be encrypted.

        Args:
            data: Data to check.

        Returns:
            True if data appears to be encrypted.
        """
        try:
            base64.urlsafe_b64decode(data)
            # Try to decrypt - if it works, it's encrypted
            return self.decrypt(data) is not None
        except Exception:
            return False

    async def migrate_to_encrypted_storage(self, storage_key: str, data: Dict):
        """Migrate existing unencrypted data to encrypted storage.

        Args:
            storage_key: Storage key for the data.
            data: Unencrypted data dictionary.
        """
        try:
            encrypted_data = {}
            for key, value in data.items():
                if isinstance(value, dict):
                    # Encrypt sensitive fields
                    encrypted_value = {}
                    for k, v in value.items():
                        if k in ("api_key", "token", "secret", "password"):
                            encrypted_value[k] = self.encrypt(str(v)) if v else None
                        else:
                            encrypted_value[k] = v
                    encrypted_data[key] = encrypted_value
                else:
                    encrypted_data[key] = value

            _LOGGER.info("Migrated data to encrypted storage for key: %s", storage_key)
            return encrypted_data
        except Exception as e:
            _LOGGER.error("Failed to migrate to encrypted storage: %s", e)
            return data

    def get_encryption_status(self) -> Dict[str, Any]:
        """Get the current encryption status.

        Returns:
            Dictionary with encryption status information.
        """
        has_key = bool(self._encryption_key)
        env_key = bool(os.environ.get(ENV_ENCRYPTION_KEY))

        return {
            "encryption_enabled": True,
            "custom_key_configured": has_key,
            "env_key_configured": env_key,
            "algorithm": "Fernet (AES-128-CBC)",
            "key_length": "128-bit",
            "recommendation": (
                "Set AI_AGENT_HA_ENCRYPTION_KEY environment variable for secure storage"
                if not (has_key or env_key)
                else "Encryption is properly configured"
            ),
        }
