"""Pytest defaults for FinAgent."""

from __future__ import annotations

import os

# Allow placeholder secrets in unit/e2e tests
os.environ.setdefault("FINAGENT_ALLOW_INSECURE_SECRETS", "1")
