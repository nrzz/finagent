"""Settings + setup wizard + multi-LLM profile API."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
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


class ProbeIn(BaseModel):
    provider: str
    base_url: str | None = None
    api_key_name: str | None = None


class PullIn(BaseModel):
    model: str
    base_url: str | None = None


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
    ):
        sensitive = True
    if sensitive:
        if not body.reauth_password:
            raise HTTPException(
                status_code=403, detail="Re-authentication required for trading mode changes"
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
    new_settings = AppSettings.model_validate(merged)
    new_settings.setup_complete = True
    new_settings.risk_acknowledged = True
    new_settings.risk_acknowledged_at = datetime.now(timezone.utc).isoformat()
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
    secret_name = body.api_key_name
    if body.api_key_value:
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
    return {"ok": True, "profile": profile.model_dump(mode="json"), "settings": settings.public_dict()}


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
    return {"ok": True, "settings": settings.public_dict()}


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
    return await get_llm_router().pull_ollama_model(body.model, body.base_url)


@router.get("/llm/ollama/models")
async def ollama_models(user: User = Depends(get_current_user)) -> dict[str, Any]:
    models = await get_llm_router().list_ollama_models()
    return {"models": models, "catalog": get_provider("ollama")}


@router.put("/secrets")
async def upsert_secret(
    body: SecretUpsert,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
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
