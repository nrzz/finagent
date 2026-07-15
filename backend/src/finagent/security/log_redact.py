"""Scrub secrets from structured log event dicts."""

from __future__ import annotations

from typing import Any

_SENSITIVE_KEYS = {
    "password",
    "reauth_password",
    "token",
    "access_token",
    "api_key",
    "api_secret",
    "authorization",
    "secret",
    "ciphertext",
    "value",
    "bot_token",
    "smtp_password",
    "hmac",
}


def redact_event(_: Any, __: Any, event_dict: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in event_dict.items():
        lk = str(k).lower()
        if lk in _SENSITIVE_KEYS or any(
            s in lk for s in ("password", "secret", "token", "authorization")
        ):
            out[k] = "***"
        elif isinstance(v, dict):
            out[k] = redact_event(None, None, v)
        else:
            out[k] = v
    return out
