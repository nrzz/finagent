"""FinAgent FastAPI application."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from finagent import __version__
from finagent.api import auth, chat, market
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
    start_scheduler()
    log.info("finagent_started", version=__version__)
    yield
    shutdown_scheduler()


def create_app() -> FastAPI:
    # Ensure .env exists before reading settings (first-run friendliness)
    ensure_runtime_env(_project_root())
    setup_logging(get_env().log_level)
    app = FastAPI(
        title="FinAgent",
        description=(
            "Self-hosted AI finance agent — stocks, mutual funds, F&O, crypto. "
            "Not financial advice."
        ),
        version=__version__,
        lifespan=lifespan,
    )

    origins = get_env().cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if origins == "*" else [o.strip() for o in origins.split(",")],
        allow_credentials=True,
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

    @app.get("/api/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__, "telemetry": "none"}

    frontend_dist = _project_root() / "frontend" / "dist"
    if frontend_dist.exists():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa(full_path: str) -> FileResponse:
            if full_path.startswith("api"):
                raise HTTPException(status_code=404, detail="Not found")
            candidate = frontend_dist / full_path
            if full_path and candidate.exists() and candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(frontend_dist / "index.html")

    return app


app = create_app()


def run() -> None:
    env = get_env()
    uvicorn.run("finagent.main:app", host=env.host, port=env.port, reload=False)


if __name__ == "__main__":
    run()
