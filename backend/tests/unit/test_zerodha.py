"""Zerodha broker unit tests (httpx mocked — no app boot)."""

from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl

import httpx
import pytest

from finagent.brokers.base import BrokerOrderRequest
from finagent.brokers.zerodha import ZerodhaBroker
from finagent.config import get_settings, set_settings
from finagent.config.schema import TradingMode


def _patch_secrets(monkeypatch: pytest.MonkeyPatch, values: dict[str, str]) -> None:
    monkeypatch.setattr(
        "finagent.brokers.zerodha.resolve_api_key",
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
async def test_healthcheck_connected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ZERODHA_API_KEY": "k",
            "ZERODHA_API_SECRET": "s",
            "ZERODHA_ACCESS_TOKEN": "t",
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert "/user/profile" in str(request.url)
        return httpx.Response(
            200,
            json={"status": "success", "data": {"user_name": "Trader"}},
        )

    _patch_httpx(monkeypatch, handler)
    out = await ZerodhaBroker().healthcheck()
    assert out["status"] == "connected"
    assert out["ok"] is True
    assert out["user_name"] == "Trader"


@pytest.mark.asyncio
async def test_exchange_request_token_success(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {"ZERODHA_API_KEY": "k", "ZERODHA_API_SECRET": "s"},
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert "/session/token" in str(request.url)
        return httpx.Response(
            200,
            json={
                "status": "success",
                "data": {"access_token": "acc-123", "user_id": "AB1234"},
            },
        )

    _patch_httpx(monkeypatch, handler)
    out = await ZerodhaBroker().exchange_request_token("req-token")
    assert out["access_token"] == "acc-123"
    assert out["user"] == "AB1234"


@pytest.mark.asyncio
async def test_exchange_request_token_sends_the_kite_checksum_not_the_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kite Connect v3 signs POST /session/token with SHA-256(api_key + request_token + secret).

    Zerodha's API dictates that checksum (a request signature, not password storage), and the
    API secret itself must never be sent.
    """
    _patch_secrets(monkeypatch, {"ZERODHA_API_KEY": "key123", "ZERODHA_API_SECRET": "hush456"})
    sent: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["body"] = request.content.decode()
        return httpx.Response(
            200, json={"status": "success", "data": {"access_token": "acc", "user_id": "AB1"}}
        )

    _patch_httpx(monkeypatch, handler)
    await ZerodhaBroker().exchange_request_token("req789")
    assert dict(parse_qsl(sent["body"])) == {
        "api_key": "key123",
        "request_token": "req789",
        "checksum": hashlib.sha256(b"key123req789hush456").hexdigest(),
    }
    assert "hush456" not in sent["body"]


@pytest.mark.asyncio
async def test_place_order_refused_in_paper_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ZERODHA_API_KEY": "k",
            "ZERODHA_API_SECRET": "s",
            "ZERODHA_ACCESS_TOKEN": "t",
        },
    )
    s = get_settings().model_copy(deep=True)
    s.trading.mode = TradingMode.PAPER
    set_settings(s)
    with pytest.raises(RuntimeError, match="Live mode"):
        await ZerodhaBroker().place_order(
            BrokerOrderRequest(symbol="RELIANCE", side="buy", quantity="1")
        )


@pytest.mark.asyncio
async def test_get_holdings_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ZERODHA_API_KEY": "k",
            "ZERODHA_API_SECRET": "s",
            "ZERODHA_ACCESS_TOKEN": "t",
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"status": "error", "message": "Incorrect `api_key` or `access_token`."},
        )

    _patch_httpx(monkeypatch, handler)
    with pytest.raises(RuntimeError, match="needs_login"):
        await ZerodhaBroker().get_holdings()


@pytest.mark.asyncio
async def test_healthcheck_needs_login_on_token_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_secrets(
        monkeypatch,
        {
            "ZERODHA_API_KEY": "k",
            "ZERODHA_API_SECRET": "s",
            "ZERODHA_ACCESS_TOKEN": "t",
        },
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            403,
            json={"status": "error", "message": "Token is invalid or has expired."},
        )

    _patch_httpx(monkeypatch, handler)
    out = await ZerodhaBroker().healthcheck()
    assert out["ok"] is False
    assert out["status"] == "needs_login"
