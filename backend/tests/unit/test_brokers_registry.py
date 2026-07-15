"""Registry routing and security helpers."""

from __future__ import annotations

import pytest

from finagent.brokers.registry import BrokerRegistry, reset_broker_registry
from finagent.config.schema import AppSettings, TradingMode
from finagent.security.url_safety import assert_webhook_url, is_safe_webhook_url


def test_webhook_blocks_metadata():
    ok, reason = is_safe_webhook_url("http://169.254.169.254/latest")
    assert not ok


def test_webhook_allows_telegram_https():
    assert_webhook_url("https://api.telegram.org/")


def test_live_requires_default_broker(monkeypatch):
    reset_broker_registry()
    settings = AppSettings()
    settings.trading.mode = TradingMode.LIVE
    settings.trading.default_broker = "alpaca"
    monkeypatch.setattr("finagent.brokers.registry.get_settings", lambda: settings)
    reg = BrokerRegistry()
    adapter = reg.get(None)
    assert adapter.name == "alpaca"


@pytest.mark.asyncio
async def test_kill_switch_blocks_order(monkeypatch):
    reset_broker_registry()
    settings = AppSettings()
    settings.trading.kill_switch = True
    monkeypatch.setattr("finagent.brokers.registry.get_settings", lambda: settings)
    from finagent.brokers.base import BrokerOrderRequest

    reg = BrokerRegistry()
    out = await reg.place_order_safe(
        BrokerOrderRequest(symbol="AAPL", side="buy", quantity="1"),
        confirmed=True,
    )
    assert out["ok"] is False
    assert "Kill" in out["error"]
