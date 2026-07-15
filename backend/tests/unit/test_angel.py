"""Angel One broker unit tests (httpx mocked — no app boot)."""

from __future__ import annotations

import httpx
import pytest

from finagent.brokers.angel import AngelBroker
from finagent.brokers.base import BrokerOrderRequest
from finagent.config import get_settings, set_settings
from finagent.config.schema import TradingMode


def _patch_secrets(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    monkeypatch.setattr(
        "finagent.brokers.angel.resolve_api_key",
        lambda name: values.get(name or ""),
    )


def _patch_httpx(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    transport = httpx.MockTransport(handler)
    original = httpx.AsyncClient

    def factory(*args, **kwargs):
        kwargs["transport"] = transport
        return original(*args, **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", factory)


@pytest.mark.asyncio
async def test_place_order_requires_symbol_token(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ANGEL_API_KEY": "k",
            "ANGEL_CLIENT_ID": "C1",
            "ANGEL_PIN": "1234",
            "ANGEL_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
            "ANGEL_JWT_TOKEN": "jwt",
        },
    )
    s = get_settings().model_copy(deep=True)
    s.trading.mode = TradingMode.LIVE
    s.trading.kill_switch = False
    set_settings(s)
    with pytest.raises(RuntimeError, match="symbol_token"):
        await AngelBroker().place_order(
            BrokerOrderRequest(symbol="RELIANCE", side="buy", quantity="1", meta={})
        )


@pytest.mark.asyncio
async def test_login_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ANGEL_API_KEY": "k",
            "ANGEL_CLIENT_ID": "C1",
            "ANGEL_PIN": "1234",
            "ANGEL_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
        },
    )
    monkeypatch.setattr(
        AngelBroker,
        "_totp_now",
        lambda self: "123456",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "loginByPassword" in str(request.url)
        return httpx.Response(
            200,
            json={
                "status": True,
                "data": {"jwtToken": "jwt-abc", "feedToken": "feed-xyz"},
            },
        )

    _patch_httpx(monkeypatch, handler)
    out = await AngelBroker().login()
    assert out["jwt_token"] == "jwt-abc"
    assert out["feed_token"] == "feed-xyz"
    assert out["client_code"] == "C1"


@pytest.mark.asyncio
async def test_get_holdings_raises_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ANGEL_API_KEY": "k",
            "ANGEL_CLIENT_ID": "C1",
            "ANGEL_PIN": "1234",
            "ANGEL_TOTP_SECRET": "JBSWY3DPEHPK3PXP",
            "ANGEL_JWT_TOKEN": "jwt",
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": False, "message": "Invalid session"},
        )

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="Invalid session"):
        await AngelBroker().get_holdings()
