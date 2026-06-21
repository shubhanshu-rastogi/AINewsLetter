"""Symmetric encryption for secrets stored at rest (UI-managed config).

A Fernet key is derived from ``SECRET_KEY`` so encrypted values are portable
across restarts as long as the secret is stable. Used by the runtime-config
service to encrypt API keys/tokens before persisting them to the database.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings

_ENC_PREFIX = "enc::"
# Stable fallback so development without SECRET_KEY still works; production
# requires a real SECRET_KEY (enforced by config.validate_for_environment).
_DEV_SECRET = "dev-insecure-secret-key-change-me"


def _fernet() -> Fernet:
    secret = (settings.SECRET_KEY or _DEV_SECRET).encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def encrypt(plaintext: str) -> str:
    """Return an encrypted, prefixed token for ``plaintext``."""
    token = _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")
    return f"{_ENC_PREFIX}{token}"


def decrypt(value: str) -> str:
    """Decrypt a value produced by :func:`encrypt`.

    Plain (non-prefixed) values are returned unchanged so the store tolerates
    pre-existing plaintext. Returns an empty string if the token can't be
    decrypted (e.g. SECRET_KEY changed).
    """
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    token = value[len(_ENC_PREFIX) :]
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""


def is_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(_ENC_PREFIX)
