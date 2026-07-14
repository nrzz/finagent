"""Runtime secret resolution (env + encrypted DB cache)."""

from __future__ import annotations

import os

_SECRET_CACHE: dict[str, str] = {}


def cache_secret(name: str, value: str) -> None:
    _SECRET_CACHE[name] = value


def clear_secret_cache() -> None:
    _SECRET_CACHE.clear()


def get_secret(name: str | None) -> str | None:
    if not name:
        return None
    if name in _SECRET_CACHE:
        return _SECRET_CACHE[name]
    env = os.environ.get(name) or os.environ.get(name.upper())
    if env:
        return env
    return None


async def load_secrets_from_db() -> int:
    """Decrypt DB secrets into memory cache. Called on startup."""
    from sqlalchemy import select

    from finagent.db import get_session_factory
    from finagent.db.models import SecretRow
    from finagent.security.secrets import decrypt_secret

    count = 0
    factory = get_session_factory()
    async with factory() as session:
        rows = (await session.execute(select(SecretRow))).scalars().all()
        for row in rows:
            try:
                cache_secret(row.name, decrypt_secret(row.ciphertext))
                count += 1
            except Exception:
                continue
    return count
