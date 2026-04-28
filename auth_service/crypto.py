from __future__ import annotations

import logging

from cryptography.fernet import Fernet

from auth_service.config import get_auth_settings

logger = logging.getLogger(__name__)

_cipher: Fernet | None = None


def _get_cipher() -> Fernet | None:
    global _cipher
    if _cipher is not None:
        return _cipher

    key = (get_auth_settings().REFRESH_TOKEN_ENCRYPTION_KEY or "").strip()
    if key:
        try:
            _cipher = Fernet(key.encode())
        except Exception as e:
            raise RuntimeError("Invalid REFRESH_TOKEN_ENCRYPTION_KEY") from e
    if not key:
        logger.warning("REFRESH_TOKEN_ENCRYPTION_KEY not set; refresh token encryption disabled.")
        _cipher = None
        return None

    try:
        _cipher = Fernet(key.encode())
    except Exception as e:
        logger.error("Invalid REFRESH_TOKEN_ENCRYPTION_KEY: %s", e)
        _cipher = None
    return _cipher


def encrypt_token(token: str) -> str | None:
    c = _get_cipher()
    if not c or not token:
        return None
    return c.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str | None:
    c = _get_cipher()
    if not c or not encrypted_token:
        return None
    try:
        return c.decrypt(encrypted_token.encode()).decode()
    except Exception as e:
        logger.warning("Failed to decrypt refresh token: %s", e)
        return None
