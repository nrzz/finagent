"""Zerodha Kite Connect broker adapter."""

from __future__ import annotations

import hashlib
from typing import Any, NoReturn

import httpx

from finagent.brokers.base import BrokerAdapter, BrokerOrderRequest
from finagent.config import get_settings, resolve_api_key
from finagent.config.schema import TradingMode
from finagent.logging_setup import get_logger

log = get_logger(__name__)

KITE_API = "https://api.kite.trade"
KITE_LOGIN = "https://kite.zerodha.com/connect/login"


def _is_session_expiry(status_code: int | None, message: str | None) -> bool:
    """Detect Kite 403 / token errors as expired session needing re-login."""
    if status_code == 403:
        return True
    return "token" in (message or "").lower()


class ZerodhaBroker(BrokerAdapter):
    name = "zerodha"
    supports_live = True
    display_name = "Zerodha Kite"
    secret_names = ["ZERODHA_API_KEY", "ZERODHA_API_SECRET", "ZERODHA_ACCESS_TOKEN"]

    def _api_key(self) -> str | None:
        return resolve_api_key("ZERODHA_API_KEY")

    def _api_secret(self) -> str | None:
        return resolve_api_key("ZERODHA_API_SECRET")

    def _access_token(self) -> str | None:
        return resolve_api_key("ZERODHA_ACCESS_TOKEN")

    def _configured(self) -> bool:
        return bool(self._api_key() and self._api_secret())

    def _session_ready(self) -> bool:
        return bool(self._configured() and self._access_token())

    def login_url(self) -> str:
        key = self._api_key() or ""
        return f"{KITE_LOGIN}?v=3&api_key={key}"

    def _headers(self) -> dict[str, str]:
        key = self._api_key() or ""
        token = self._access_token() or ""
        return {
            "X-Kite-Version": "3",
            "Authorization": f"token {key}:{token}",
        }

    def _raise_api_error(self, status_code: int, message: str) -> NoReturn:
        if _is_session_expiry(status_code, message):
            raise RuntimeError(f"needs_login: session expired ({message})")
        raise RuntimeError(message)

    async def exchange_request_token(self, request_token: str) -> dict[str, Any]:
        key = self._api_key()
        secret = self._api_secret()
        if not key or not secret:
            raise RuntimeError("Save ZERODHA_API_KEY and ZERODHA_API_SECRET first")
        checksum = hashlib.sha256(f"{key}{request_token}{secret}".encode()).hexdigest()
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{KITE_API}/session/token",
                data={
                    "api_key": key,
                    "request_token": request_token,
                    "checksum": checksum,
                },
            )
            data = resp.json()
            if resp.status_code >= 400 or data.get("status") == "error":
                raise RuntimeError(data.get("message") or resp.text[:300])
            access = (data.get("data") or {}).get("access_token")
            if not access:
                raise RuntimeError("No access_token in Kite response")
            return {"access_token": access, "user": (data.get("data") or {}).get("user_id")}

    async def healthcheck(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "ok": True,
            "name": self.name,
            "display_name": self.display_name,
            "configured": self._configured(),
            "session": self._session_ready(),
            "mode": get_settings().trading.mode.value,
            "login_url": self.login_url() if self._api_key() else None,
            "status": "not_configured",
        }
        if not self._configured():
            return out
        if not self._session_ready():
            out["status"] = "needs_login"
            return out
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{KITE_API}/user/profile", headers=self._headers())
                data = resp.json()
                if resp.status_code >= 400 or data.get("status") == "error":
                    msg = str(data.get("message") or resp.status_code)
                    out["ok"] = False
                    if _is_session_expiry(resp.status_code, msg):
                        out["status"] = "needs_login"
                    else:
                        out["status"] = f"error:{msg}"
                    return out
                out["status"] = "connected"
                out["user_name"] = (data.get("data") or {}).get("user_name")
        except Exception as exc:
            out["ok"] = False
            msg = str(exc)
            if _is_session_expiry(None, msg):
                out["status"] = "needs_login"
            else:
                out["status"] = f"error:{exc}"
        return out

    async def get_holdings(self) -> list[dict[str, Any]]:
        if not self._session_ready():
            return []
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(f"{KITE_API}/portfolio/holdings", headers=self._headers())
            data = resp.json()
            if resp.status_code >= 400 or data.get("status") == "error":
                msg = str(data.get("message") or resp.text[:300] or resp.status_code)
                self._raise_api_error(resp.status_code, msg)
            rows = data.get("data") or []
            return [
                {
                    "symbol": r.get("tradingsymbol"),
                    "qty": r.get("quantity"),
                    "avg_entry_price": r.get("average_price"),
                    "exchange": r.get("exchange"),
                    "source": "zerodha",
                }
                for r in rows
            ]

    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        settings = get_settings().trading
        if settings.mode != TradingMode.LIVE:
            raise RuntimeError("Zerodha only places orders in Live mode")
        if settings.kill_switch:
            raise RuntimeError("Kill switch enabled")
        if not self._session_ready():
            raise RuntimeError("Zerodha session missing — complete Login with Kite in Settings")
        meta = request.meta or {}
        product = meta.get("product") or settings.india_default_product or "CNC"
        exchange = meta.get("exchange") or "NSE"
        variety = meta.get("variety") or "regular"
        order_type = (request.order_type or "market").upper()
        if order_type == "MARKET":
            order_type = "MARKET"
        elif order_type == "LIMIT":
            order_type = "LIMIT"
        elif order_type in ("SL", "STOP", "STOPLOSS"):
            order_type = "SL"
        body = {
            "tradingsymbol": request.symbol.upper().replace(".NS", "").replace(".BO", ""),
            "exchange": exchange,
            "transaction_type": request.side.upper(),
            "quantity": str(int(float(request.quantity))),
            "order_type": order_type,
            "product": product,
            "validity": "DAY",
        }
        if request.limit_price and order_type in ("LIMIT", "SL"):
            body["price"] = str(request.limit_price)
        if meta.get("trigger_price"):
            body["trigger_price"] = str(meta["trigger_price"])
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{KITE_API}/orders/{variety}",
                headers=self._headers(),
                data=body,
            )
            data = resp.json()
            if resp.status_code >= 400 or data.get("status") == "error":
                msg = str(data.get("message") or resp.text[:500] or resp.status_code)
                self._raise_api_error(resp.status_code, msg)
            oid = (data.get("data") or {}).get("order_id")
            log.info("zerodha_order", order_id=oid, symbol=request.symbol)
            return {
                "broker": "zerodha",
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
        variety = "regular"
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.delete(
                f"{KITE_API}/orders/{variety}/{order_id}",
                headers=self._headers(),
            )
            data = resp.json()
            ok = resp.status_code < 400 and data.get("status") != "error"
            return {"ok": ok, "raw": data}
