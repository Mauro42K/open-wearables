"""Encryption helpers for downstream API keys."""

from base64 import urlsafe_b64encode
from hashlib import sha256

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class CryptoError(Exception):
    """Raised when encryption or decryption fails."""


class CryptoService:
    """Encrypt and decrypt ow-api keys."""

    def __init__(self) -> None:
        self._fernet = Fernet(self._derive_fernet_key(settings.encryption_key.get_secret_value()))

    @staticmethod
    def _derive_fernet_key(raw_key: str) -> bytes:
        digest = sha256(raw_key.encode("utf-8")).digest()
        return urlsafe_b64encode(digest)

    def encrypt_api_key(self, plain_api_key: str) -> str:
        """Encrypt an ow-api key."""
        try:
            return self._fernet.encrypt(plain_api_key.encode("utf-8")).decode("utf-8")
        except Exception as exc:  # noqa: BLE001
            raise CryptoError from exc

    def decrypt_api_key(self, encrypted_api_key: str) -> str:
        """Decrypt an ow-api key."""
        try:
            return self._fernet.decrypt(encrypted_api_key.encode("utf-8")).decode("utf-8")
        except (InvalidToken, ValueError) as exc:
            raise CryptoError from exc

    @staticmethod
    def mask_api_key(plain_api_key: str) -> str:
        """Return a masked representation suitable for UI responses."""
        if len(plain_api_key) <= 7:
            return "****"
        prefix = plain_api_key[:3]
        return f"{prefix}****{plain_api_key[-4:]}"


crypto_service = CryptoService()
