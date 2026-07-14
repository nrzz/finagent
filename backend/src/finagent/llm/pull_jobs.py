"""In-process Ollama pull job tracker — progress, cancel, re-attach after refresh."""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from finagent.logging_setup import get_logger

log = get_logger(__name__)


@dataclass
class PullProgress:
    model: str
    phase: str = "starting"  # starting|manifest|downloading|verifying|success|failed|cancelled
    percent: float | None = None
    completed_bytes: int = 0
    total_bytes: int = 0
    speed_bps: float = 0.0
    eta_s: float | None = None
    layer: str | None = None
    status: str = ""
    error: str | None = None
    started_at: float = field(default_factory=time.monotonic)
    updated_at: float = field(default_factory=time.monotonic)

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "phase": self.phase,
            "percent": self.percent,
            "completed_bytes": self.completed_bytes,
            "total_bytes": self.total_bytes,
            "speed_bps": self.speed_bps,
            "eta_s": self.eta_s,
            "layer": self.layer,
            "status": self.status,
            "error": self.error,
            "elapsed_s": round(time.monotonic() - self.started_at, 1),
            "running": self.phase
            not in ("success", "failed", "cancelled"),
        }


@dataclass
class PullJob:
    model: str
    base_url: str
    progress: PullProgress
    cancel: asyncio.Event = field(default_factory=asyncio.Event)
    task: asyncio.Task[None] | None = None
    subscribers: list[asyncio.Queue[dict[str, Any]]] = field(default_factory=list)
    http_task: asyncio.Task[None] | None = None
    _client: httpx.AsyncClient | None = None
    _last_completed: int = 0
    _last_t: float = field(default_factory=time.monotonic)


_jobs: dict[str, PullJob] = {}
_lock = asyncio.Lock()
_ACTIVE_OTHER: str | None = None


def _normalize_base(base_url: str | None) -> str:
    base = (base_url or "http://127.0.0.1:11434").replace("/v1", "").rstrip("/")
    return base


def get_job(model: str) -> PullJob | None:
    return _jobs.get(model)


def active_job() -> PullJob | None:
    for job in _jobs.values():
        if job.progress.phase not in ("success", "failed", "cancelled"):
            return job
    return None


async def subscribe(model: str) -> asyncio.Queue[dict[str, Any]] | None:
    job = _jobs.get(model)
    if not job:
        return None
    q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=64)
    job.subscribers.append(q)
    await q.put(job.progress.to_dict())
    return q


def unsubscribe(model: str, q: asyncio.Queue[dict[str, Any]]) -> None:
    job = _jobs.get(model)
    if not job:
        return
    if q in job.subscribers:
        job.subscribers.remove(q)


async def _broadcast(job: PullJob) -> None:
    payload = job.progress.to_dict()
    dead: list[asyncio.Queue[dict[str, Any]]] = []
    for q in job.subscribers:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            try:
                _ = q.get_nowait()
                q.put_nowait(payload)
            except Exception:
                dead.append(q)
    for q in dead:
        if q in job.subscribers:
            job.subscribers.remove(q)


def _map_phase(status: str) -> str:
    s = (status or "").lower()
    if "manifest" in s:
        return "manifest"
    if "digest" in s or "verif" in s or "sha256" in s:
        return "verifying"
    if "pull" in s or "download" in s or "writing" in s:
        return "downloading"
    if s in ("success", "completed"):
        return "success"
    return "downloading"


async def _run_pull(job: PullJob) -> None:
    progress = job.progress
    url = f"{job.base_url}/api/pull"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3600.0, connect=10.0)) as client:
            job._client = client
            async with client.stream(
                "POST", url, json={"name": job.model, "stream": True}
            ) as resp:
                if resp.status_code >= 400:
                    body = (await resp.aread()).decode("utf-8", errors="replace")[:500]
                    progress.phase = "failed"
                    progress.error = body or f"HTTP {resp.status_code}"
                    await _broadcast(job)
                    return
                async for line in resp.aiter_lines():
                    if job.cancel.is_set():
                        progress.phase = "cancelled"
                        progress.error = "Cancelled by user"
                        await _broadcast(job)
                        return
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if err := data.get("error"):
                        progress.phase = "failed"
                        progress.error = str(err)
                        progress.status = str(err)
                        await _broadcast(job)
                        return
                    status = str(data.get("status") or "")
                    progress.status = status
                    progress.layer = data.get("digest") or progress.layer
                    progress.updated_at = time.monotonic()
                    total = int(data.get("total") or 0)
                    completed = int(data.get("completed") or 0)
                    if total > 0:
                        progress.total_bytes = total
                        progress.completed_bytes = completed
                        progress.percent = round(100.0 * completed / total, 1)
                        now = time.monotonic()
                        dt = max(now - job._last_t, 0.001)
                        dc = completed - job._last_completed
                        if dc >= 0:
                            # EMA-ish speed
                            instant = dc / dt
                            progress.speed_bps = (
                                progress.speed_bps * 0.7 + instant * 0.3
                                if progress.speed_bps
                                else instant
                            )
                            remaining = max(total - completed, 0)
                            if progress.speed_bps > 1:
                                progress.eta_s = remaining / progress.speed_bps
                        job._last_completed = completed
                        job._last_t = now
                        progress.phase = _map_phase(status)
                    else:
                        progress.phase = _map_phase(status) if status else progress.phase
                        progress.percent = None
                    if status.lower() in ("success", "completed") or data.get("done"):
                        progress.phase = "success"
                        progress.percent = 100.0
                        await _broadcast(job)
                        return
                    await _broadcast(job)
            # stream ended without explicit success
            if progress.phase not in ("failed", "cancelled"):
                # verify via tags
                try:
                    tags = await client.get(f"{job.base_url}/api/tags")
                    names = [
                        m.get("name", "")
                        for m in (tags.json().get("models") or [])
                        if m.get("name")
                    ]
                    if any(
                        n == job.model or n.startswith(job.model.split(":")[0])
                        for n in names
                    ):
                        progress.phase = "success"
                        progress.percent = 100.0
                    else:
                        progress.phase = "failed"
                        progress.error = "Pull finished but model not found in Ollama"
                except Exception as exc:
                    progress.phase = "failed"
                    progress.error = str(exc)
                await _broadcast(job)
    except httpx.ConnectError:
        progress.phase = "failed"
        progress.error = (
            "Ollama is offline. Install from https://ollama.com/download and start it."
        )
        await _broadcast(job)
    except Exception as exc:
        if job.cancel.is_set():
            progress.phase = "cancelled"
            progress.error = "Cancelled by user"
        else:
            progress.phase = "failed"
            progress.error = str(exc)
        await _broadcast(job)
        log.info("ollama_pull_failed", model=job.model, error=str(exc))
    finally:
        job._client = None


async def cancel_pull(model: str) -> bool:
    job = _jobs.get(model)
    if not job:
        # Also cancel if this is the active job under a slightly different key
        active = active_job()
        if active and (active.model == model or model in active.model):
            job = active
        else:
            return False
    job.cancel.set()
    if job.task and not job.task.done():
        job.task.cancel()
        try:
            await job.task
        except Exception:
            pass
    job.progress.phase = "cancelled"
    job.progress.error = "Cancelled by user"
    await _broadcast(job)
    return True


async def cancel_active_pull() -> str | None:
    """Cancel whichever pull is running. Returns cancelled model name or None."""
    async with _lock:
        job = active_job()
        if not job:
            return None
        name = job.model
    await cancel_pull(name)
    return name


async def start_or_attach(
    model: str, base_url: str | None = None, *, replace: bool = False
) -> tuple[PullJob, bool]:
    """Start a pull or return existing job. At most one pull runs globally.

    If ``replace`` and another model is installing, cancel it first.
    """
    model = model.strip()
    base = _normalize_base(base_url)
    other: PullJob | None = None
    async with _lock:
        existing = _jobs.get(model)
        if existing and existing.progress.phase not in ("success", "failed", "cancelled"):
            return existing, True
        other = active_job()
        if other and other.model != model:
            if not replace:
                raise RuntimeError(
                    f"Only one install at a time. “{other.model}” is installing — "
                    "cancel it, switch to an installed model, or pass replace=true."
                )
            # Cancel outside lock after releasing — set flag now
            other.cancel.set()
            if other.task and not other.task.done():
                other.task.cancel()
            other.progress.phase = "cancelled"
            other.progress.error = f"Replaced by install of {model}"
    if other and other.model != model and replace:
        await _broadcast(other)
        try:
            if other.task:
                await other.task
        except Exception:
            pass

    async with _lock:
        # Re-check after possible cancel
        existing = _jobs.get(model)
        if existing and existing.progress.phase not in ("success", "failed", "cancelled"):
            return existing, True
        other2 = active_job()
        if other2 and other2.model != model:
            raise RuntimeError(
                f"Only one install at a time. “{other2.model}” is still installing."
            )
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base}/api/tags")
                resp.raise_for_status()
                names = [
                    m.get("name", "")
                    for m in (resp.json().get("models") or [])
                    if m.get("name")
                ]
                if model in names:
                    job = PullJob(
                        model=model,
                        base_url=base,
                        progress=PullProgress(
                            model=model,
                            phase="success",
                            percent=100.0,
                            status="already installed",
                        ),
                    )
                    _jobs[model] = job
                    return job, False
        except httpx.ConnectError as exc:
            raise RuntimeError(
                "Ollama is offline. Install from https://ollama.com/download and start it."
            ) from exc
        except Exception:
            pass

        progress = PullProgress(model=model, phase="starting", status="Starting pull…")
        job = PullJob(model=model, base_url=base, progress=progress)
        _jobs[model] = job
        job.task = asyncio.create_task(_run_pull(job))
        return job, False


def status_payload(model: str | None = None) -> dict[str, Any]:
    if model:
        job = _jobs.get(model)
        if not job:
            active = active_job()
            return {
                "ok": True,
                "active": active.progress.to_dict() if active else None,
                "job": None,
            }
        return {"ok": True, "job": job.progress.to_dict(), "active": job.progress.to_dict()}
    active = active_job()
    return {
        "ok": True,
        "active": active.progress.to_dict() if active else None,
        "jobs": {k: v.progress.to_dict() for k, v in _jobs.items()},
    }
