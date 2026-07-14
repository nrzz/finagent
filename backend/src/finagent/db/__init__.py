"""Database engine and session helpers."""

from __future__ import annotations

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


async def init_db() -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session
