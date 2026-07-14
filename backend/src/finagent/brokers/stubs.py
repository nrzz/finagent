"""Reference live-broker stubs — keys configurable, execution gated until live mode."""

from __future__ import annotations

from typing import Any

from finagent.brokers.base import BrokerAdapter, BrokerOrderRequest
from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import TradingMode


class GatedLiveStub(BrokerAdapter):
    """Configured stub: accepts credentials in secrets, refuses orders unless live mode."""

    name = "stub"
    supports_live = True
    secret_names: list[str] = []
    display_name: str = "Stub"

    def __init__(self, name: str, display_name: str, secret_names: list[str]) -> None:
        self.name = name
        self.display_name = display_name
        self.secret_names = secret_names

    def _configured(self) -> bool:
        return any(resolve_api_key(n) for n in self.secret_names)

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "ok": True,
            "name": self.name,
            "display_name": self.display_name,
            "configured": self._configured(),
            "mode": get_settings().trading.mode.value,
            "status": (
                "ready_for_live"
                if self._configured() and get_settings().trading.mode == TradingMode.LIVE
                else "paper_only_until_live_enabled"
            ),
        }

    async def get_holdings(self) -> list[dict[str, Any]]:
        return []

    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        settings = get_settings().trading
        if settings.mode != TradingMode.LIVE:
            raise RuntimeError(
                f"{self.display_name} is configured for later use, but FinAgent is in paper mode. "
                "Enable Live in Settings (re-auth) to send real orders — not financial advice."
            )
        if settings.kill_switch:
            raise RuntimeError("Kill switch enabled")
        if not self._configured():
            raise RuntimeError(f"Missing API keys for {self.display_name}")
        raise RuntimeError(
            f"{self.display_name} live execution is a stub in this release — "
            "implement BrokerAdapter for production. Orders stay on paper."
        )

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "Stub broker — cancel not available", "order_id": order_id}


def build_reference_stubs() -> list[GatedLiveStub]:
    return [
        GatedLiveStub(
            "zerodha",
            "Zerodha Kite",
            ["ZERODHA_API_KEY", "ZERODHA_API_SECRET", "ZERODHA_ACCESS_TOKEN"],
        ),
        GatedLiveStub(
            "angel",
            "Angel One",
            ["ANGEL_API_KEY", "ANGEL_CLIENT_ID", "ANGEL_PIN", "ANGEL_TOTP_SECRET"],
        ),
        GatedLiveStub(
            "alpaca",
            "Alpaca",
            ["ALPACA_API_KEY", "ALPACA_API_SECRET"],
        ),
    ]
