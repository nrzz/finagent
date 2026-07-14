"""Ensure only one Ollama model stays loaded in RAM/VRAM."""

from __future__ import annotations

from typing import Any

import httpx

from finagent.logging_setup import get_logger

log = get_logger(__name__)


def _base(url: str | None) -> str:
    return (url or "http://127.0.0.1:11434").replace("/v1", "").rstrip("/")


def _names_match(a: str, b: str) -> bool:
    a, b = a.strip(), b.strip()
    if a == b:
        return True
    # tag aliases: qwen2.5:7b vs qwen2.5:7b-instruct
    if a.split(":")[0] == b.split(":")[0] and (a.startswith(b) or b.startswith(a)):
        return True
    return False


async def list_loaded_models(base_url: str | None = None) -> list[dict[str, Any]]:
    """Return models currently loaded in Ollama memory (GET /api/ps)."""
    base = _base(base_url)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(f"{base}/api/ps")
            resp.raise_for_status()
            models = resp.json().get("models") or []
            out = []
            for m in models:
                name = m.get("name") or m.get("model") or ""
                if not name:
                    continue
                out.append(
                    {
                        "name": name,
                        "size_vram": m.get("size_vram") or m.get("size"),
                        "expires_at": m.get("expires_at"),
                    }
                )
            return out
    except Exception as exc:
        log.info("ollama_ps_failed", error=str(exc))
        return []


async def unload_model(model: str, base_url: str | None = None) -> bool:
    """Unload a model from Ollama RAM (keep_alive=0)."""
    base = _base(base_url)
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Official unload: generate/chat with keep_alive 0
            resp = await client.post(
                f"{base}/api/generate",
                json={"model": model, "keep_alive": 0, "prompt": "", "stream": False},
            )
            if resp.status_code >= 400:
                resp = await client.post(
                    f"{base}/api/chat",
                    json={
                        "model": model,
                        "messages": [],
                        "keep_alive": 0,
                        "stream": False,
                    },
                )
            ok = resp.status_code < 400
            log.info("ollama_unload", model=model, ok=ok, status=resp.status_code)
            return ok
    except Exception as exc:
        log.info("ollama_unload_failed", model=model, error=str(exc))
        return False


async def ensure_exclusive_model(
    model: str,
    base_url: str | None = None,
    *,
    warm: bool = False,
    keep_alive: str | int = "30m",
) -> dict[str, Any]:
    """Unload every loaded Ollama model except ``model`` (frees RAM/VRAM).

    If ``warm``, briefly touch the active model so it is the only one resident.
    """
    model = model.strip()
    loaded = await list_loaded_models(base_url)
    unloaded: list[str] = []
    for entry in loaded:
        name = entry["name"]
        if _names_match(name, model):
            continue
        if await unload_model(name, base_url):
            unloaded.append(name)

    warmed = False
    if warm and model:
        base = _base(base_url)
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{base}/api/generate",
                    json={
                        "model": model,
                        "prompt": " ",
                        "stream": False,
                        "keep_alive": keep_alive,
                        "options": {"num_predict": 1},
                    },
                )
                warmed = resp.status_code < 400
        except Exception as exc:
            log.info("ollama_warm_failed", model=model, error=str(exc))

    still = await list_loaded_models(base_url)
    return {
        "ok": True,
        "active": model,
        "unloaded": unloaded,
        "warmed": warmed,
        "loaded_now": [m["name"] for m in still],
        "message": (
            f"Exclusive: {model}. Unloaded {len(unloaded)} other model(s) from RAM."
            if unloaded
            else f"Exclusive: {model}. No other models were loaded."
        ),
    }
