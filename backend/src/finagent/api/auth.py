"""Auth: setup bootstrap + JWT sessions."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finagent.config import get_env, get_settings
from finagent.db import get_db
from finagent.db.models import AuditLog, SettingsRow, User

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)
ALGORITHM = "HS256"
TOKEN_HOURS = 12

# Simple in-memory login rate limit: username/ip → failures
_login_failures: dict[str, list[float]] = {}
_LOGIN_WINDOW_S = 300.0
_LOGIN_MAX = 8


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    setup_complete: bool


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return pwd_context.verify(password, password_hash)


def needs_rehash(password_hash: str) -> bool:
    return pwd_context.needs_update(password_hash)


def _rate_limit_key(username: str) -> str:
    return username.strip().lower()


def _check_login_rate(username: str) -> None:
    import time

    key = _rate_limit_key(username)
    now = time.monotonic()
    window = [t for t in _login_failures.get(key, []) if now - t < _LOGIN_WINDOW_S]
    _login_failures[key] = window
    if len(window) >= _LOGIN_MAX:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in a few minutes.",
        )


def _record_login_failure(username: str) -> None:
    import time

    key = _rate_limit_key(username)
    _login_failures.setdefault(key, []).append(time.monotonic())


def _clear_login_failures(username: str) -> None:
    _login_failures.pop(_rate_limit_key(username), None)


def create_token(username: str) -> str:
    payload = {
        "sub": username,
        "exp": datetime.now(UTC) + timedelta(hours=TOKEN_HOURS),
        "iat": datetime.now(UTC),
    }
    return jwt.encode(payload, get_env().jwt_secret, algorithm=ALGORITHM)


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        data = jwt.decode(creds.credentials, get_env().jwt_secret, algorithms=[ALGORITHM])
        username = data.get("sub")
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    if creds is None:
        return None
    try:
        return await get_current_user(creds, db)
    except HTTPException:
        return None


@router.get("/status")
async def auth_status(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    result = await db.execute(select(User))
    users = result.scalars().all()
    settings = get_settings()
    return {
        "needs_setup": len(users) == 0 or not settings.setup_complete,
        "user_count": len(users),
        "setup_complete": settings.setup_complete,
    }


@router.post("/setup", response_model=TokenResponse)
async def setup(body: SetupRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    existing = await db.execute(select(User))
    if existing.scalars().first():
        raise HTTPException(status_code=400, detail="Setup already completed")
    user = User(username=body.username, password_hash=hash_password(body.password), is_admin=True)
    db.add(user)
    settings = get_settings()
    # Keep setup_complete False until wizard finishes LLM step; mark partially ready
    row = SettingsRow(payload=settings.model_dump(mode="json"))
    db.add(row)
    db.add(AuditLog(actor=body.username, action="setup_admin", detail={"username": body.username}))
    await db.commit()
    token = create_token(body.username)
    return TokenResponse(
        access_token=token,
        username=body.username,
        setup_complete=settings.setup_complete,
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    _check_login_rate(body.username)
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password_hash):
        _record_login_failure(body.username)
        db.add(
            AuditLog(
                actor=body.username or "unknown",
                action="login_failed",
                detail={},
            )
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    _clear_login_failures(body.username)
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    db.add(AuditLog(actor=user.username, action="login_ok", detail={}))
    await db.commit()
    return TokenResponse(
        access_token=create_token(user.username),
        username=user.username,
        setup_complete=get_settings().setup_complete,
    )


@router.get("/me")
async def me(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {
        "username": user.username,
        "is_admin": user.is_admin,
        "setup_complete": get_settings().setup_complete,
    }
