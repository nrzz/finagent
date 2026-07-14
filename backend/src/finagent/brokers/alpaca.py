"""Alpaca paper (and gated live) broker adapter."""

from __future__ import annotations

from typing import Any

import httpx

from finagent.brokers.base import BrokerAdapter, BrokerOrderRequest
from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import TradingMode
from finagent.logging_setup import get_logger

log = get_logger(__name__)

PAPER_BASE = "https://paper-api.alpaca.markets"
LIVE_BASE = "https://api.alpaca.markets"


class AlpacaBroker(BrokerAdapter):
    name = "alpaca"
    supports_live = True
    display_name = "Alpaca"

    def _keys(self) -> tuple[str | None, str | None]:
        return resolve_api_key("ALPACA_API_KEY"), resolve_api_key("ALPACA_API_SECRET")

    def _configured(self) -> bool:
        k, s = self._keys()
        return bool(k and s)

    def _base(self) -> str:
        # Paper endpoint unless live mode explicitly enabled
        if get_settings().trading.mode == TradingMode.LIVE:
            return LIVE_BASE
        return PAPER_BASE

    def _headers(self) -> dict[str, str]:
        key, secret = self._keys()
        return {
            "APCA-API-KEY-ID": key or "",
            "APCA-API-SECRET-KEY": secret or "",
            "Content-Type": "application/json",
        }

    async def healthcheck(self) -> dict[str, Any]:
        configured = self._configured()
        out: dict[str, Any] = {
            "ok": True,
            "name": self.name,
            "display_name": self.display_name,
            "configured": configured,
            "mode": get_settings().trading.mode.value,
            "endpoint": self._base(),
            "status": "not_configured",
        }
        if not configured:
            return out
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self._base()}/v2/account", headers=self._headers())
                if resp.status_code >= 400:
                    out["status"] = f"error:{resp.status_code}"
                    out["ok"] = False
                    return out
                data = resp.json()
                out["status"] = "connected"
                out["account_status"] = data.get("status")
                out["buying_power"] = data.get("buying_power")
                out["equity"] = data.get("equity")
                out["paper"] = self._base() == PAPER_BASE
        except Exception as exc:
            out["ok"] = False
            out["status"] = f"error:{exc}"
        return out

    async def get_holdings(self) -> list[dict[str, Any]]:
        if not self._configured():
            return []
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{self._base()}/v2/positions", headers=self._headers())
            resp.raise_for_status()
            rows = resp.json()
            return [
                {
                    "symbol": r.get("symbol"),
                    "qty": r.get("qty"),
                    "avg_entry_price": r.get("avg_entry_price"),
                    "market_value": r.get("market_value"),
                    "unrealized_pl": r.get("unrealized_pl"),
                }
                for r in rows
            ]

    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        settings = get_settings().trading
        if settings.kill_switch:
            raise RuntimeError("Kill switch enabled")
        if not self._configured():
            raise RuntimeError("Missing ALPACA_API_KEY / ALPACA_API_SECRET")
        # Paper mode uses Alpaca paper API; live requires live mode + confirmation at registry
        if settings.mode == TradingMode.LIVE and self._base() != LIVE_BASE:
            raise RuntimeError("Live mode required for live Alpaca endpoint")
        if settings.mode != TradingMode.LIVE and self._base() != PAPER_BASE:
            raise RuntimeError("Internal endpoint mismatch")
        body = {
            "symbol": request.symbol.upper().replace(".US", ""),
            "qty": str(request.quantity),
            "side": request.side.lower(),
            "type": (request.order_type or "market").lower(),
            "time_in_force": "day",
        }
        if request.limit_price and body["type"] == "limit":
            body["limit_price"] = str(request.limit_price)
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{self._base()}/v2/orders", headers=self._headers(), json=body
            )
            if resp.status_code >= 400:
                raise RuntimeError(resp.text[:500])
            data = resp.json()
            log.info("alpaca_order", id=data.get("id"), symbol=request.symbol, paper=self._base() == PAPER_BASE)
            return {
                "broker": "alpaca",
                "paper": self._base() == PAPER_BASE,
                "id": data.get("id"),
                "status": data.get("status"),
                "symbol": data.get("symbol"),
                "qty": data.get("qty"),
                "side": data.get("side"),
                "raw": data,
            }

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        if not self._configured():
            return {"ok": False, "error": "Not configured"}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.delete(
                f"{self._base()}/v2/orders/{order_id}", headers=self._headers()
            )
            return {"ok": resp.status_code < 400, "status_code": resp.status_code}
