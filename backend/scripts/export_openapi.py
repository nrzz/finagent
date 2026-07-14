#!/usr/bin/env python3
"""Export OpenAPI schema for TypeScript client generation."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Isolate from user data while importing app
_tmp = Path(__file__).resolve().parent / "_openapi_tmp"
_tmp.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("FINAGENT_DATA_DIR", str(_tmp))
os.environ.setdefault("FINAGENT_DATABASE_URL", "sqlite+aiosqlite:///openapi.db")
os.environ.setdefault("FINAGENT_SECRET_KEY", "openapi-export-secret-key-32chars!!")
os.environ.setdefault("FINAGENT_JWT_SECRET", "openapi-export-jwt-secret-key-32ch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from finagent.config import get_env  # noqa: E402

get_env.cache_clear()

from finagent.main import app  # noqa: E402

OUT = ROOT.parent / "frontend" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(schema, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
