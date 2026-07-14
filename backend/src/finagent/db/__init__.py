"""Database engine and session helpers."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from finagent.config import ensure_data_dir, get_env
from finagent.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def _resolve_database_url() -> str:
    env = get_env()
    data_dir = ensure_data_dir().resolve()
    url = env.database_url
    if url.startswith("sqlite+aiosqlite:///"):
        raw = url.removeprefix("sqlite+aiosqlite:///")
        # Absolute Windows paths look like /D:/... after three slashes — keep as-is if absolute.
        path = Path(raw)
        if not path.is_absolute():
            path = data_dir / path.name
        path.parent.mkdir(parents=True, exist_ok=True)
        # SQLAlchemy wants four slashes for absolute paths on Unix; on Windows use absolute URI.
        return f"sqlite+aiosqlite:///{path.as_posix()}"
    return url


def get_engine():
    global _engine, _session_factory
    if _engine is None:
        url = _resolve_database_url()
        _engine = create_async_engine(url, echo=False, future=True)
        _session_factory = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _session_factory is not None
    return _session_factory


def _alembic_config():
    from alembic.config import Config

    # .../backend/src/finagent/db/__init__.py -> parents[3] = backend
    backend_root = Path(__file__).resolve().parents[3]
    cfg = Config(str(backend_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(backend_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", _resolve_database_url())
    return cfg


def run_migrations() -> None:
    """Apply Alembic migrations (sync)."""
    from alembic import command

    command.upgrade(_alembic_config(), "head")


async def init_db() -> None:
    """Run Alembic upgrade; ensure metadata tables exist as safety net."""
    try:
        await asyncio.to_thread(run_migrations)
    except Exception:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        # Safety net for tables added before a new migration is written
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
