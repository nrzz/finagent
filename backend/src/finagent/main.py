"""FinAgent FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from finagent import __version__
from finagent.api import auth, backtest, chat, market
from finagent.api import settings as settings_api
from finagent.bootstrap import ensure_runtime_env
from finagent.config import ensure_data_dir, get_env, load_yaml_overlay, set_settings
from finagent.db import init_db
from finagent.logging_setup import get_logger, setup_logging
from finagent.scheduler import shutdown_scheduler, start_scheduler
from finagent.security.store import load_secrets_from_db

log = get_logger(__name__)


def _project_root() -> Path:
    # backend/src/finagent/main.py -> repo root
    return Path(__file__).resolve().parents[3]


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    root = _project_root()
    ensure_runtime_env(root)
    ensure_data_dir()
    await init_db()
    yaml_path = root / "config" / "config.yaml"
    overlay = load_yaml_overlay(yaml_path)
    if overlay:
        set_settings(overlay)
        log.info("loaded_yaml_config", path=str(yaml_path))
    from finagent.api.settings import sync_settings_from_db
    from finagent.db import get_session_factory

    async with get_session_factory()() as session:
        await sync_settings_from_db(session)
    loaded = await load_secrets_from_db()
    log.info("secrets_cached", count=loaded)
    from finagent.trading.persist import load_paper_from_db

    async with get_session_factory()() as session:
        await load_paper_from_db(session)
    start_scheduler()
    from finagent.scheduler import reload_jobs_from_db

    await reload_jobs_from_db()
    log.info("finagent_started", version=__version__)
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    # Ensure .env exists before reading settings (first-run friendliness)
    ensure_runtime_env(_project_root())
    setup_logging(get_env().log_level)
    from finagent.security.secrets import assert_secure_keys

    try:
        assert_secure_keys()
    except RuntimeError:
        # Allow pytest / CI with env flag; otherwise fail closed
        import os

        if os.environ.get("FINAGENT_ALLOW_INSECURE_SECRETS", "").lower() not in (
            "1",
            "true",
            "yes",
        ):
            raise

    app = FastAPI(
        title="FinAgent",
        description=(
            "Self-hosted AI finance agent — stocks, mutual funds, F&O, crypto. "
            "Not financial advice."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    origins = get_env().cors_origins.strip()
    # Refuse credentials + wildcard; tighten * when binding beyond localhost docs
    if origins == "*":
        allow_origins = ["*"]
        allow_credentials = False
    else:
        allow_origins = [o.strip() for o in origins.split(",") if o.strip()]
        allow_credentials = True
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=allow_credentials,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(ValueError)
    async def _value_error(_request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    app.include_router(auth.router)
    app.include_router(settings_api.router)
    app.include_router(chat.router)
    app.include_router(market.router)
    app.include_router(backtest.router)

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "telemetry": "none"}

    @app.get("/api/health/ready")
    async def ready() -> dict[str, Any]:
        from sqlalchemy import text

        from finagent.db import get_session_factory
        from finagent.scheduler.jobs import get_scheduler

        checks: dict[str, str] = {}
        try:
            async with get_session_factory()() as session:
                await session.execute(text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:
            checks["database"] = f"error: {exc}"
        try:
            sched = get_scheduler()
            checks["scheduler"] = "ok" if sched and sched.running else "stopped"
        except Exception as exc:
            checks["scheduler"] = f"error: {exc}"
        ok = checks.get("database") == "ok" and checks.get("scheduler") == "ok"
        payload = {
            "status": "ready" if ok else "degraded",
            "version": __version__,
            "checks": checks,
        }
        if not ok:
            return JSONResponse(status_code=503, content=payload)
        return payload

    frontend_dist = _project_root() / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str) -> FileResponse:
            if full_path.startswith("api"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = frontend_dist / full_path
            if full_path and candidate.exists() and candidate.is_file():
                # Hashed assets may be cached; HTML/SW must stay fresh after rebuilds
                headers = {}
                if full_path.endswith((".js", ".css", ".woff2", ".png", ".svg", ".webp")):
                    headers["Cache-Control"] = "public, max-age=31536000, immutable"
                else:
                    headers["Cache-Control"] = "no-cache"
                return FileResponse(candidate, headers=headers)
            return FileResponse(
                frontend_dist / "index.html",
                headers={"Cache-Control": "no-cache"},
            )

    return app


app = create_app()


def run() -> None:
    env = get_env()
    uvicorn.run("finagent.main:app", host=env.host, port=env.port, reload=False)


if __name__ == "__main__":
    run()
