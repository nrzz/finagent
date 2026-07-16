"""Unit tests for batch quotes, symbol parsing, and history interval."""

from __future__ import annotations

import inspect
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from finagent.api.market import history, parse_symbols
from finagent.data.registry import MarketDataRegistry


def test_parse_symbols_splits_and_strips() -> None:
    assert parse_symbols("AAPL, MSFT, ,BTC/USDT") == ["AAPL", "MSFT", "BTC/USDT"]


def test_parse_symbols_caps_at_max() -> None:
    raw = ",".join(f"S{i}" for i in range(50))
    out = parse_symbols(raw, max_symbols=40)
    assert len(out) == 40
    assert out[0] == "S0"
    assert out[-1] == "S39"


@pytest.mark.asyncio
async def test_get_quotes_parallel_success_and_error() -> None:
    reg = MarketDataRegistry.__new__(MarketDataRegistry)
    ok = MagicMock()
    ok.to_dict.return_value = {"symbol": "AAPL", "price": "1"}
    reg.get_quote = AsyncMock(side_effect=[ok, RuntimeError("boom")])  # type: ignore[method-assign]

    out = await reg.get_quotes(["AAPL", "BAD"])
    assert out[0] == {"symbol": "AAPL", "price": "1"}
    assert out[1] == {"symbol": "BAD", "error": "boom"}


def test_history_endpoint_accepts_interval() -> None:
    sig = inspect.signature(history)
    assert "interval" in sig.parameters
    assert sig.parameters["interval"].default == "1d"


@pytest.mark.asyncio
async def test_history_passes_interval_to_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    mock_reg = MagicMock()
    mock_reg.get_history = AsyncMock(return_value=[{"time": "t", "close": 1.0}])

    monkeypatch.setattr("finagent.api.market.get_market_registry", lambda: mock_reg)

    user = MagicMock()
    result: dict[str, Any] = await history(symbol="AAPL", period="5d", interval="1h", user=user)
    mock_reg.get_history.assert_awaited_once_with("AAPL", "5d", "1h")
    assert result["interval"] == "1h"
    assert result["candles"]
    assert "note" not in result
