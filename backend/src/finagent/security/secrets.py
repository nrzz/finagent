"""Secret encryption helpers (Fernet)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from finagent.config import get_env


def _fernet() -> Fernet:
    raw = get_env().secret_key.encode("utf-8")
    # Accept either a valid Fernet key or derive one from an arbitrary secret.
    try:
        return Fernet(
            raw if len(raw) == 44 else base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        )
    except Exception:
        return Fernet(base64.urlsafe_b64encode(hashlib.sha256(raw).digest()))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt secret — check FINAGENT_SECRET_KEY") from exc


def mask_secret(value: str | None, visible: int = 4) -> str | None:
    if not value:
        return None
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]
