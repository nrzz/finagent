"""Settings + setup wizard + multi-LLM profile API."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from finagent.api.auth import get_current_user
from finagent.config import get_settings, set_settings
from finagent.config.schema import AppSettings, LLMProfile
from finagent.db import get_db
from finagent.db.models import AuditLog, SecretRow, SettingsRow, User
from finagent.llm import get_llm_router
from finagent.llm.catalog import get_catalog, get_provider
from finagent.security import encrypt_secret, mask_secret
from finagent.security.store import cache_secret

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _profile_is_ollama(profile: LLMProfile) -> bool:
    prov = getattr(profile.provider, "value", profile.provider)
    return str(prov) == "ollama"


async def _exclusive_ollama_for_profile(profile: LLMProfile) -> dict[str, Any] | None:
    """Unload other Ollama models from RAM so only this profile's model stays loaded."""
    from finagent.llm.ollama_runtime import ensure_exclusive_model

    try:
        return await ensure_exclusive_model(
            profile.model,
            profile.base_url or "http://127.0.0.1:11434",
            warm=False,
        )
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


class SettingsUpdate(BaseModel):
    settings: dict[str, Any]
    reauth_password: str | None = None


class SecretUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    value: str = Field(min_length=1)
    reauth_password: str | None = None


class WizardComplete(BaseModel):
    settings: dict[str, Any]


class ProfileIn(BaseModel):
    id: str | None = None
    name: str = "My LLM"
    provider: str = "demo"
    model: str = "demo"
    base_url: str | None = None
    api_key_name: str | None = None
    api_key_value: str | None = None  # optional inline key → stored as secret
    tool_mode: str = "auto"
    timeout_s: int = 120
    max_context_tokens: int = 8192
    temperature: float = 0.2
    enabled: bool = True
    make_active: bool = False
    make_fallback: bool = False
    reauth_password: str | None = None


class ProbeIn(BaseModel):
    provider: str
    base_url: str | None = None
    api_key_name: str | None = None


class PullIn(BaseModel):
    model: str
    base_url: str | None = None
    replace: bool = False  # cancel other in-flight install first (only one at a time)


class ActivateIn(BaseModel):
    profile_id: str
    role: str = "active"  # active | fallback | chat | analysis


async def _load_or_create_settings_row(db: AsyncSession) -> SettingsRow:
    result = await db.execute(select(SettingsRow).limit(1))
    row = result.scalar_one_or_none()
    if row is None:
        row = SettingsRow(payload=get_settings().model_dump(mode="json"))
        db.add(row)
        await db.flush()
    return row


async def sync_settings_from_db(db: AsyncSession) -> AppSettings:
    row = await _load_or_create_settings_row(db)
    settings = AppSettings.model_validate(row.payload or {})
    settings.llm.ensure_profiles()
    settings.llm.sync_legacy_from_active()
    set_settings(settings)
    return settings


async def _persist(db: AsyncSession, settings: AppSettings, user: User, action: str) -> AppSettings:
    settings.llm.ensure_profiles()
    settings.llm.sync_legacy_from_active()
    row = await _load_or_create_settings_row(db)
    row.payload = settings.model_dump(mode="json")
    db.add(AuditLog(actor=user.username, action=action, detail={}))
    await db.commit()
    set_settings(settings)
    get_llm_router().refresh()
    return settings


@router.get("")
async def get_all_settings(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = await sync_settings_from_db(db)
    secrets = (await db.execute(select(SecretRow))).scalars().all()
    return {
        "settings": settings.public_dict(),
        "secrets": [{"name": s.name, "masked": mask_secret(s.name + "****")} for s in secrets],
        "catalog": get_catalog(),
        "user": user.username,
    }


def _apply_legacy_llm_patch(settings: AppSettings, llm_patch: dict[str, Any]) -> None:
    """When UI/tests send provider/model without profiles[], update the active profile."""
    settings.llm.ensure_profiles()
    if llm_patch.get("profiles"):
        return
    legacy_keys = ("provider", "model", "base_url", "tool_mode", "timeout_s", "max_context_tokens", "temperature")
    if not any(k in llm_patch for k in legacy_keys):
        return
    active = settings.llm.get_profile(settings.llm.active_profile_id)
    data = active.model_dump(mode="json")
    for k in legacy_keys:
        if k in llm_patch:
            data[k] = llm_patch[k]
    if "api_key_ref" in llm_patch:
        data["api_key_name"] = llm_patch["api_key_ref"]
    updated = LLMProfile.model_validate(data)
    settings.llm.profiles = [updated if p.id == active.id else p for p in settings.llm.profiles]
    # Switching the main LLM via legacy fields should use Active for chat/analysis
    settings.llm.active_profile_id = active.id
    if any(k in llm_patch for k in ("provider", "model")):
        settings.llm.chat_profile_id = None
        settings.llm.analysis_profile_id = None
    settings.llm.sync_legacy_from_active()


@router.put("")
async def update_settings(
    body: SettingsUpdate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    current = await sync_settings_from_db(db)
    merged = {**current.model_dump(mode="json"), **body.settings}
    for key in ("llm", "markets", "trading", "appearance"):
        if key in body.settings and isinstance(body.settings[key], dict):
            base = current.model_dump(mode="json").get(key, {})
            patch = body.settings[key]
            # Keep existing profiles unless explicitly replaced
            if key == "llm" and "profiles" not in patch:
                merged[key] = {**base, **{k: v for k, v in patch.items() if k != "profiles"}}
            else:
                merged[key] = {**base, **patch}
    try:
        new_settings = AppSettings.model_validate(merged)
        new_settings.llm.ensure_profiles()
        if isinstance(body.settings.get("llm"), dict):
            _apply_legacy_llm_patch(new_settings, body.settings["llm"])
        new_settings.llm.sync_legacy_from_active()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sensitive = False
    if (
        new_settings.trading.mode != current.trading.mode
        or new_settings.trading.kill_switch != current.trading.kill_switch
        or new_settings.trading.require_order_confirmation
        != current.trading.require_order_confirmation
    ):
        sensitive = True
    # Live mode: confirmation cannot be turned off without step-up (already in sensitive)
    if (
        new_settings.trading.mode.value == "live"
        and not new_settings.trading.require_order_confirmation
    ):
        # Force confirmation on for live unless they explicitly re-authed to disable
        if not body.reauth_password:
            new_settings.trading.require_order_confirmation = True
    if sensitive:
        if not body.reauth_password:
            raise HTTPException(
                status_code=403,
                detail="Re-authentication required for trading mode / confirmation changes",
            )
        from finagent.api.auth import verify_password

        if not verify_password(body.reauth_password, user.password_hash):
            raise HTTPException(status_code=403, detail="Re-authentication failed")

    await _persist(db, new_settings, user, "settings_update")
    return {"ok": True, "settings": new_settings.public_dict()}


@router.post("/wizard/complete")
async def complete_wizard(
    body: WizardComplete,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not body.settings.get("risk_acknowledged"):
        raise HTTPException(
            status_code=400,
            detail="You must acknowledge the risk disclaimer before launching FinAgent",
        )
    from datetime import datetime, timezone

    current = await sync_settings_from_db(db)
    merged = {**current.model_dump(mode="json"), **body.settings, "setup_complete": True}
    for key in ("llm", "markets", "trading", "appearance"):
        if key in body.settings and isinstance(body.settings[key], dict):
            merged[key] = {**current.model_dump(mode="json").get(key, {}), **body.settings[key]}
    # Wizard must never silently enable live trading
    trading_patch = body.settings.get("trading") or {}
    if isinstance(trading_patch, dict) and str(trading_patch.get("mode", "")).lower() == "live":
        raise HTTPException(
            status_code=403,
            detail="Live trading cannot be enabled from the setup wizard. Use Settings with password re-auth after launch.",
        )
    if "trading" in merged and isinstance(merged["trading"], dict):
        merged["trading"]["mode"] = "paper"
    new_settings = AppSettings.model_validate(merged)
    new_settings.setup_complete = True
    new_settings.risk_acknowledged = True
    new_settings.risk_acknowledged_at = datetime.now(timezone.utc).isoformat()
    from finagent.config.schema import TradingMode

    new_settings.trading.mode = TradingMode.PAPER
    new_settings.llm.ensure_profiles()
    # If wizard sent legacy llm fields without profiles, rebuild profile from them
    if body.settings.get("llm") and not (body.settings.get("llm") or {}).get("profiles"):
        llm = body.settings["llm"]
        pid = uuid4().hex[:12]
        new_settings.llm.profiles = [
            LLMProfile(
                id=pid,
                name=str(llm.get("provider", "demo")).title(),
                provider=llm.get("provider", "demo"),
                model=llm.get("model", "demo"),
                base_url=llm.get("base_url"),
                tool_mode=llm.get("tool_mode", "auto"),
            )
        ]
        new_settings.llm.active_profile_id = pid
    new_settings.llm.sync_legacy_from_active()
    await _persist(db, new_settings, user, "wizard_complete")
    return {"ok": True, "settings": new_settings.public_dict()}


@router.get("/llm/catalog")
async def llm_catalog(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"providers": get_catalog()}


@router.get("/llm/profiles")
async def list_profiles(
    user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    settings = await sync_settings_from_db(db)
    llm = settings.llm
    return {
        "profiles": [p.model_dump(mode="json") for p in llm.profiles],
        "active_profile_id": llm.active_profile_id,
        "fallback_profile_id": llm.fallback_profile_id,
        "chat_profile_id": llm.chat_profile_id,
        "analysis_profile_id": llm.analysis_profile_id,
    }


@router.post("/llm/profiles")
async def upsert_profile(
    body: ProfileIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = await sync_settings_from_db(db)
    meta = get_provider(body.provider)
    if body.base_url:
        from finagent.security.url_safety import assert_llm_base_url

        try:
            assert_llm_base_url(body.base_url, provider=body.provider)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    secret_name = body.api_key_name
    if body.api_key_value:
        if not body.reauth_password:
            raise HTTPException(
                status_code=403, detail="Re-authentication required to store API keys"
            )
        from finagent.api.auth import verify_password

        if not verify_password(body.reauth_password, user.password_hash):
            raise HTTPException(status_code=403, detail="Re-authentication failed")
        secret_name = secret_name or (meta or {}).get("secret_name") or f"{body.provider.upper()}_API_KEY"
        cipher = encrypt_secret(body.api_key_value)
        existing = await db.execute(select(SecretRow).where(SecretRow.name == secret_name))
        row = existing.scalar_one_or_none()
        if row:
            row.ciphertext = cipher
        else:
            db.add(SecretRow(name=secret_name, ciphertext=cipher))
        cache_secret(secret_name, body.api_key_value)

    pid = body.id or uuid4().hex[:12]
    profile = LLMProfile(
        id=pid,
        name=body.name,
        provider=body.provider,
        model=body.model,
        base_url=body.base_url
        if body.base_url is not None
        else (meta or {}).get("default_base_url"),
        api_key_name=secret_name,
        tool_mode=body.tool_mode,
        timeout_s=body.timeout_s,
        max_context_tokens=body.max_context_tokens,
        temperature=body.temperature,
        enabled=body.enabled,
    )
    replaced = False
    new_profiles: list[LLMProfile] = []
    for p in settings.llm.profiles:
        if p.id == pid:
            new_profiles.append(profile)
            replaced = True
        else:
            new_profiles.append(p)
    if not replaced:
        new_profiles.append(profile)
    settings.llm.profiles = new_profiles
    if body.make_active or not settings.llm.active_profile_id:
        settings.llm.active_profile_id = pid
    if body.make_fallback:
        settings.llm.fallback_profile_id = pid
    settings.llm.sync_legacy_from_active()
    await _persist(db, settings, user, "llm_profile_upsert")
    exclusive = None
    if body.make_active and _profile_is_ollama(profile):
        exclusive = await _exclusive_ollama_for_profile(profile)
    return {
        "ok": True,
        "profile": profile.model_dump(mode="json"),
        "settings": settings.public_dict(),
        "ollama_exclusive": exclusive,
    }


@router.delete("/llm/profiles/{profile_id}")
async def delete_profile(
    profile_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = await sync_settings_from_db(db)
    if len(settings.llm.profiles) <= 1:
        raise HTTPException(status_code=400, detail="Keep at least one LLM profile")
    settings.llm.profiles = [p for p in settings.llm.profiles if p.id != profile_id]
    if settings.llm.active_profile_id == profile_id:
        settings.llm.active_profile_id = settings.llm.profiles[0].id
    if settings.llm.fallback_profile_id == profile_id:
        settings.llm.fallback_profile_id = None
    if settings.llm.chat_profile_id == profile_id:
        settings.llm.chat_profile_id = None
    if settings.llm.analysis_profile_id == profile_id:
        settings.llm.analysis_profile_id = None
    settings.llm.sync_legacy_from_active()
    await _persist(db, settings, user, "llm_profile_delete")
    return {"ok": True, "settings": settings.public_dict()}


@router.post("/llm/activate")
async def activate_profile(
    body: ActivateIn,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = await sync_settings_from_db(db)
    ids = {p.id for p in settings.llm.profiles}
    if body.profile_id not in ids:
        raise HTTPException(status_code=404, detail="Profile not found")
    if body.role == "active":
        settings.llm.active_profile_id = body.profile_id
    elif body.role == "fallback":
        settings.llm.fallback_profile_id = body.profile_id
    elif body.role == "chat":
        settings.llm.chat_profile_id = body.profile_id
    elif body.role == "analysis":
        settings.llm.analysis_profile_id = body.profile_id
    else:
        raise HTTPException(status_code=400, detail="role must be active|fallback|chat|analysis")
    settings.llm.sync_legacy_from_active()
    await _persist(db, settings, user, "llm_activate")
    exclusive = None
    if body.role == "active":
        profile = next(p for p in settings.llm.profiles if p.id == body.profile_id)
        if _profile_is_ollama(profile):
            exclusive = await _exclusive_ollama_for_profile(profile)
    return {"ok": True, "settings": settings.public_dict(), "ollama_exclusive": exclusive}


@router.post("/llm/test")
async def test_llm(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await get_llm_router().test_connection()


@router.post("/llm/test/{profile_id}")
async def test_llm_profile(profile_id: str, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await get_llm_router().test_profile(profile_id)


@router.post("/llm/probe")
async def probe_llm(body: ProbeIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await get_llm_router().probe_provider(body.provider, body.base_url, body.api_key_name)


@router.post("/llm/models")
async def list_llm_models(body: ProbeIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    models = await get_llm_router().list_models(body.provider, body.base_url, body.api_key_name)
    return {"models": models}


@router.post("/llm/ollama/pull")
async def pull_ollama(body: PullIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Blocking pull (scripts). Prefer /pull/stream for UI progress."""
    from finagent.llm import pull_jobs

    try:
        job, _ = await pull_jobs.start_or_attach(body.model, body.base_url)
        if job.progress.phase == "success" and job.progress.status == "already installed":
            return {"ok": True, "model": body.model, "already_installed": True}
        if job.task:
            await job.task
        if job.progress.phase == "success":
            return {"ok": True, "model": body.model}
        return {
            "ok": False,
            "error": job.progress.error or "Pull failed",
            "hint": "Is Ollama running? Install from https://ollama.com/download then retry.",
        }
    except RuntimeError as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/llm/ollama/pull/status")
async def pull_status(
    model: str | None = None, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    from finagent.llm import pull_jobs

    return pull_jobs.status_payload(model)


@router.post("/llm/ollama/pull/cancel")
async def pull_cancel(body: PullIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    from finagent.llm import pull_jobs

    if not body.model or body.model == "*":
        cancelled = await pull_jobs.cancel_active_pull()
        return {"ok": bool(cancelled), "model": cancelled}
    ok = await pull_jobs.cancel_pull(body.model)
    return {"ok": ok, "model": body.model}


@router.post("/llm/ollama/pull/stream")
async def pull_stream(body: PullIn, user: User = Depends(get_current_user)) -> StreamingResponse:
    """SSE progress for Ollama model install (percent / bytes / ETA). Only one pull at a time."""
    from finagent.llm import pull_jobs

    try:
        job, attached = await pull_jobs.start_or_attach(
            body.model, body.base_url, replace=body.replace
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    queue = await pull_jobs.subscribe(body.model)
    if queue is None:
        raise HTTPException(status_code=500, detail="Failed to subscribe to pull job")

    async def event_gen():  # type: ignore[no-untyped-def]
        try:
            # Immediate snapshot
            yield f"data: {json.dumps({**job.progress.to_dict(), 'attached': attached})}\n\n"
            if job.progress.phase == "success":
                yield f"data: {json.dumps(job.progress.to_dict())}\n\n"
                return
            while True:
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=5.0)
                except TimeoutError:
                    # heartbeat
                    yield f"data: {json.dumps({**job.progress.to_dict(), 'heartbeat': True})}\n\n"
                    if job.progress.phase in ("success", "failed", "cancelled"):
                        break
                    continue
                yield f"data: {json.dumps(payload)}\n\n"
                if payload.get("phase") in ("success", "failed", "cancelled"):
                    break
        finally:
            pull_jobs.unsubscribe(body.model, queue)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/llm/ollama/models")
async def ollama_models(user: User = Depends(get_current_user)) -> dict[str, Any]:
    models = await get_llm_router().list_ollama_models()
    from finagent.llm.ollama_runtime import list_loaded_models

    loaded = await list_loaded_models("http://127.0.0.1:11434")
    return {
        "models": models,
        "loaded": loaded,
        "catalog": get_provider("ollama"),
    }


class ExclusiveIn(BaseModel):
    model: str
    base_url: str | None = None
    warm: bool = False


@router.get("/llm/ollama/ps")
async def ollama_ps(
    base_url: str | None = None, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Models currently loaded in Ollama RAM/VRAM."""
    from finagent.llm.ollama_runtime import list_loaded_models

    loaded = await list_loaded_models(base_url)
    return {"ok": True, "loaded": loaded}


@router.post("/llm/ollama/exclusive")
async def ollama_exclusive(
    body: ExclusiveIn, user: User = Depends(get_current_user)
) -> dict[str, Any]:
    """Unload every other Ollama model so only ``model`` can stay in memory."""
    from finagent.llm.ollama_runtime import ensure_exclusive_model

    return await ensure_exclusive_model(body.model, body.base_url, warm=body.warm)


@router.put("/secrets")
async def upsert_secret(
    body: SecretUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    if not body.reauth_password:
        raise HTTPException(
            status_code=403, detail="Re-authentication required to store API secrets"
        )
    from finagent.api.auth import verify_password

    if not verify_password(body.reauth_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Re-authentication failed")
    result = await db.execute(select(SecretRow).where(SecretRow.name == body.name))
    row = result.scalar_one_or_none()
    cipher = encrypt_secret(body.value)
    if row:
        row.ciphertext = cipher
    else:
        db.add(SecretRow(name=body.name, ciphertext=cipher))
    cache_secret(body.name, body.value)
    db.add(AuditLog(actor=user.username, action="secret_upsert", detail={"name": body.name}))
    await db.commit()
    return {"ok": True, "name": body.name, "masked": mask_secret(body.value)}


@router.get("/export")
async def export_settings(user: User = Depends(get_current_user)) -> dict[str, Any]:
    return {"settings": get_settings().public_dict(), "note": "Secrets are not exported"}


@router.get("/backup")
async def download_backup(user: User = Depends(get_current_user)) -> FileResponse:
    """Download SQLite DB snapshot (secrets remain ciphertext — keep FINAGENT_SECRET_KEY)."""
    from finagent.config import get_env

    env = get_env()
    db_path = Path(env.data_dir) / "finagent.db"
    # Resolve from database_url if needed
    url = env.database_url
    if "sqlite" in url and "///" in url:
        raw = url.split("///", 1)[-1]
        candidate = Path(raw)
        if candidate.exists():
            db_path = candidate
    if not db_path.exists():
        raise HTTPException(status_code=404, detail=f"Database not found at {db_path}")
    return FileResponse(
        path=str(db_path),
        filename="finagent-backup.db",
        media_type="application/octet-stream",
    )


@router.post("/backup/restore")
async def restore_backup(
    user: User = Depends(get_current_user),
    file: UploadFile = File(...),
) -> dict[str, Any]:
    """Replace SQLite DB with uploaded backup. Restart FinAgent after restore."""
    from finagent.config import get_env

    if not file.filename or not file.filename.endswith(".db"):
        raise HTTPException(status_code=400, detail="Upload a .db backup file")
    data = await file.read()
    if len(data) > 200 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Backup too large (>200MB)")
    if len(data) < 100:
        raise HTTPException(status_code=400, detail="File too small to be a valid SQLite DB")
    env = get_env()
    db_path = Path(env.data_dir) / "finagent.db"
    url = env.database_url
    if "sqlite" in url and "///" in url:
        candidate = Path(url.split("///", 1)[-1])
        if candidate.parent.exists():
            db_path = candidate
    db_path.parent.mkdir(parents=True, exist_ok=True)
    bak = db_path.with_suffix(".db.pre-restore")
    if db_path.exists():
        bak.write_bytes(db_path.read_bytes())
    db_path.write_bytes(data)
    return {
        "ok": True,
        "path": str(db_path),
        "previous_backup": str(bak) if bak.exists() else None,
        "note": "Restart FinAgent to load the restored database. Keep the same FINAGENT_SECRET_KEY.",
    }
