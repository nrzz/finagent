"""Step-up password re-authentication helpers."""

from __future__ import annotations

from fastapi import HTTPException

from finagent.api.auth import verify_password
from finagent.db.models import User


def require_reauth(
    user: User, password: str | None, *, detail: str = "Re-authentication required"
) -> None:
    if not password:
        raise HTTPException(status_code=403, detail=detail)
    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=403, detail="Re-authentication failed")
