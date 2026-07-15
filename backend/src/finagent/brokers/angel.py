"""Angel One SmartAPI broker adapter."""

from __future__ import annotations

from typing import Any

import httpx

from finagent.brokers.base import BrokerAdapter, BrokerOrderRequest
from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import TradingMode
from finagent.logging_setup import get_logger

log = get_logger(__name__)

SMART_BASE = "https://apiconnect.angelone.in"


class AngelBroker(BrokerAdapter):
    name = "angel"
    supports_live = True
    display_name = "Angel One"
    secret_names = [
        "ANGEL_API_KEY",
        "ANGEL_CLIENT_ID",
        "ANGEL_PIN",
        "ANGEL_TOTP_SECRET",
        "ANGEL_JWT_TOKEN",
        "ANGEL_FEED_TOKEN",
    ]

    def _api_key(self) -> str | None:
        return resolve_api_key("ANGEL_API_KEY")

    def _client_id(self) -> str | None:
        return resolve_api_key("ANGEL_CLIENT_ID")

    def _pin(self) -> str | None:
        return resolve_api_key("ANGEL_PIN")

    def _totp_secret(self) -> str | None:
        return resolve_api_key("ANGEL_TOTP_SECRET")

    def _jwt(self) -> str | None:
        return resolve_api_key("ANGEL_JWT_TOKEN")

    def _configured(self) -> bool:
        return bool(self._api_key() and self._client_id() and self._pin() and self._totp_secret())

    def _session_ready(self) -> bool:
        return bool(self._configured() and self._jwt())

    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-UserType": "USER",
            "X-SourceID": "WEB",
            "X-ClientLocalIP": "127.0.0.1",
            "X-ClientPublicIP": "127.0.0.1",
            "X-MACAddress": "00:00:00:00:00:00",
            "X-PrivateKey": self._api_key() or "",
            "Authorization": f"Bearer {self._jwt() or ''}",
        }

    def _totp_now(self) -> str:
        secret = self._totp_secret()
        if not secret:
            raise RuntimeError("Missing ANGEL_TOTP_SECRET")
        try:
            import pyotp

            return pyotp.TOTP(secret).now()
        except ImportError as exc:
            raise RuntimeError("pyotp required for Angel login — pip install pyotp") from exc

    async def login(self) -> dict[str, Any]:
        if not self._configured():
            raise RuntimeError("Save Angel API key, client id, PIN, and TOTP secret first")
        body = {
            "clientcode": self._client_id(),
            "password": self._pin(),
            "totp": self._totp_now(),
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SMART_BASE}/rest/auth/angelbroking/user/v1/loginByPassword",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "X-UserType": "USER",
                    "X-SourceID": "WEB",
                    "X-ClientLocalIP": "127.0.0.1",
                    "X-ClientPublicIP": "127.0.0.1",
                    "X-MACAddress": "00:00:00:00:00:00",
                    "X-PrivateKey": self._api_key() or "",
                },
                json=body,
            )
            data = resp.json()
            if not data.get("status"):
                raise RuntimeError(data.get("message") or resp.text[:300])
            payload = data.get("data") or {}
            jwt = payload.get("jwtToken")
            feed = payload.get("feedToken")
            if not jwt:
                raise RuntimeError("No jwtToken in Angel login response")
            return {"jwt_token": jwt, "feed_token": feed, "client_code": self._client_id()}

    async def healthcheck(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": True,
            "name": self.name,
            "display_name": self.display_name,
            "configured": self._configured(),
            "session": self._session_ready(),
            "mode": get_settings().trading.mode.value,
            "status": "not_configured",
        }
        if not self._configured():
            return out
        if not self._session_ready():
            out["status"] = "needs_login"
            return out
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{SMART_BASE}/rest/secure/angelbroking/user/v1/getProfile",
                    headers=self._headers(),
                )
                data = resp.json()
                if not data.get("status"):
                    out["ok"] = False
                    out["status"] = f"error:{data.get('message')}"
                    return out
                out["status"] = "connected"
                out["name_on_account"] = (data.get("data") or {}).get("name")
        except Exception as exc:
            out["ok"] = False
            out["status"] = f"error:{exc}"
        return out

    async def get_holdings(self) -> list[dict[str, Any]]:
        if not self._session_ready():
            return []
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(
                f"{SMART_BASE}/rest/secure/angelbroking/portfolio/v1/getHolding",
                headers=self._headers(),
            )
            data = resp.json()
            if resp.status_code >= 400 or not data.get("status"):
                raise RuntimeError(
                    data.get("message") or resp.text[:300] or f"HTTP {resp.status_code}"
                )
            rows = data.get("data") or []
            return [
                {
                    "symbol": r.get("tradingsymbol") or r.get("symboltoken"),
                    "qty": r.get("quantity"),
                    "avg_entry_price": r.get("averageprice"),
                    "source": "angel",
                }
                for r in rows
            ]

    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        settings = get_settings().trading
        if settings.mode != TradingMode.LIVE:
            raise RuntimeError("Angel only places orders in Live mode")
        if settings.kill_switch:
            raise RuntimeError("Kill switch enabled")
        if not self._session_ready():
            raise RuntimeError("Angel session missing — click Login in Settings")
        product = (request.meta or {}).get("product") or settings.india_default_product or "CNC"
        exchange = (request.meta or {}).get("exchange") or "NSE"
        ordertype = (request.order_type or "MARKET").upper()
        if ordertype == "LIMIT":
            ordertype = "LIMIT"
        elif ordertype in ("SL", "STOP"):
            ordertype = "STOPLOSS_LIMIT"
        else:
            ordertype = "MARKET"
        body = {
            "variety": "NORMAL",
            "tradingsymbol": request.symbol.upper().replace(".NS", "").replace(".BO", ""),
            "symboltoken": str((request.meta or {}).get("symbol_token") or ""),
            "transactiontype": request.side.upper(),
            "exchange": exchange,
            "ordertype": ordertype,
            "producttype": "DELIVERY"
            if product == "CNC"
            else ("INTRADAY" if product == "MIS" else "CARRYFORWARD"),
            "duration": "DAY",
            "price": str(request.limit_price or "0"),
            "quantity": str(int(float(request.quantity))),
        }
        if not body["symboltoken"]:
            raise RuntimeError("Angel orders need meta.symbol_token (instrument token)")
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{SMART_BASE}/rest/secure/angelbroking/order/v1/placeOrder",
                headers=self._headers(),
                json=body,
            )
            data = resp.json()
            if not data.get("status"):
                raise RuntimeError(data.get("message") or resp.text[:500])
            oid = (data.get("data") or {}).get("orderid")
            log.info("angel_order", order_id=oid, symbol=request.symbol)
            return {
                "broker": "angel",
                "paper": False,
                "id": oid,
                "status": "submitted",
                "symbol": request.symbol,
                "qty": request.quantity,
                "side": request.side,
                "raw": data.get("data"),
            }

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        if not self._session_ready():
            return {"ok": False, "error": "Not logged in"}
        body = {"variety": "NORMAL", "orderid": order_id}
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{SMART_BASE}/rest/secure/angelbroking/order/v1/cancelOrder",
                headers=self._headers(),
                json=body,
            )
            data = resp.json()
            return {"ok": bool(data.get("status")), "raw": data}
