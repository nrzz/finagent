"""Secret encryption helpers (Fernet + Argon2id KEK derivation)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from finagent.config import get_env

_INSECURE_DEFAULTS = {
    "dev-insecure-fernet-key-replace=======",
    "dev-insecure-jwt-secret-change-me",
}


def assert_secure_keys() -> None:
    """Refuse to start with placeholder secrets outside explicit allow."""
    env = get_env()
    if env.secret_key in _INSECURE_DEFAULTS or env.jwt_secret in _INSECURE_DEFAULTS:
        allow = (getattr(env, "allow_insecure_secrets", False) is True) or (
            __import__("os").environ.get("FINAGENT_ALLOW_INSECURE_SECRETS", "").lower()
            in ("1", "true", "yes")
        )
        if not allow:
            raise RuntimeError(
                "FINAGENT_SECRET_KEY / FINAGENT_JWT_SECRET are insecure defaults. "
                "Run bootstrap or set strong secrets. For local tests only: "
                "FINAGENT_ALLOW_INSECURE_SECRETS=1"
            )


def _derive_fernet_key(material: bytes) -> bytes:
    """Derive a Fernet key via Argon2id (preferred) or SHA-256 fallback."""
    try:
        from argon2.low_level import Type, hash_secret_raw

        raw = hash_secret_raw(
            secret=material,
            salt=b"finagent-secret-v2xxxx",  # 16+ bytes
            time_cost=3,
            memory_cost=64 * 1024,
            parallelism=4,
            hash_len=32,
            type=Type.ID,
        )
        return base64.urlsafe_b64encode(raw)
    except Exception:
        return base64.urlsafe_b64encode(hashlib.sha256(material).digest())


def _fernet() -> Fernet:
    raw = get_env().secret_key.encode("utf-8")
    # Accept either a valid Fernet key or derive one from an arbitrary secret.
    if len(raw) == 44:
        try:
            return Fernet(raw)
        except Exception:
            pass
    return Fernet(_derive_fernet_key(raw))


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
