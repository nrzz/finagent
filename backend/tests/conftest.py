"""Pytest defaults for FinAgent."""

from __future__ import annotations

import os

import pytest

# Allow placeholder secrets in unit/e2e tests
os.environ.setdefault("FINAGENT_ALLOW_INSECURE_SECRETS", "1")


@pytest.fixture(autouse=True)
def _reset_trading_safety():
    """Keep paper unit tests isolated from e2e settings mutations."""
    try:
        from finagent.config import get_settings, set_settings
        from finagent.config.schema import TradingMode

        s = get_settings().model_copy(deep=True)
        s.trading.kill_switch = False
        s.trading.mode = TradingMode.PAPER
        set_settings(s)
    except Exception:
        pass
    yield
