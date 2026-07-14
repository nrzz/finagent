"""Start FinAgent for Playwright smoke (fresh data dir)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT.parent / "frontend" / ".playwright-data"
if DATA.exists():
    shutil.rmtree(DATA, ignore_errors=True)
DATA.mkdir(parents=True, exist_ok=True)

os.environ["FINAGENT_DATA_DIR"] = str(DATA)
os.environ["FINAGENT_DATABASE_URL"] = "sqlite+aiosqlite:///playwright.db"
os.environ["FINAGENT_SECRET_KEY"] = "playwright-secret-key-for-fernet-32c"
os.environ["FINAGENT_JWT_SECRET"] = "playwright-jwt-secret-please-change-32"
os.environ["PYTHONPATH"] = str(ROOT / "src")

sys.path.insert(0, str(ROOT / "src"))

import uvicorn

if __name__ == "__main__":
    uvicorn.run("finagent.main:app", host="127.0.0.1", port=8000, reload=False)
