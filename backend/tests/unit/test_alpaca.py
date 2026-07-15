"""Alpaca broker unit tests (no app boot / no insecure-secrets flag required)."""

from __future__ import annotations

import pytest

from finagent.brokers.alpaca import AlpacaBroker
from finagent.brokers.base import BrokerOrderRequest


def _patch_secrets(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    monkeypatch.setattr(
        "finagent.brokers.alpaca.resolve_api_key",
        lambda name: values.get(name or ""),
    )


@pytest.mark.asyncio
async def test_healthcheck_not_configured_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(monkeypatch, {})
    out = await AlpacaBroker().healthcheck()
    assert out["configured"] is False
    assert out["status"] == "not_configured"
    assert out["ok"] is True


@pytest.mark.asyncio
async def test_place_order_raises_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(monkeypatch, {})
    with pytest.raises(RuntimeError, match="ALPACA_API_KEY"):
        await AlpacaBroker().place_order(
            BrokerOrderRequest(symbol="AAPL", side="buy", quantity="1")
        )
