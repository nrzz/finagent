"""Broker registry with live-mode safety gates."""

from __future__ import annotations

from typing import Any

from finagent.brokers.base import BrokerAdapter, BrokerOrderRequest
from finagent.config import get_settings
from finagent.config.schema import TradingMode
from finagent.trading.paper import get_paper_broker


class PaperBrokerAdapter(BrokerAdapter):
    name = "paper"
    supports_live = False
    display_name = "Local paper"
    secret_names: list[str] = []

    def _configured(self) -> bool:
        return True

    async def get_holdings(self) -> list[dict[str, Any]]:
        return get_paper_broker().positions_snapshot()

    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        order = get_paper_broker().place_order(
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=request.limit_price or request.meta.get("mark_price") or "0",
            order_type=request.order_type,
            limit_price=request.limit_price,
            idempotency_key=request.idempotency_key,
            asset_class=request.asset_class,
            force_open_market=True,
            meta=request.meta,
        )
        return order.to_dict()

    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "Paper fills are immediate; cancel not applicable",
            "order_id": order_id,
        }

    async def get_orders(self) -> list[dict[str, Any]]:
        return get_paper_broker().blotter()

    async def healthcheck(self) -> dict[str, Any]:
        return {
            "ok": True,
            "name": self.name,
            "display_name": self.display_name,
            "configured": True,
            "status": "connected",
            "mode": get_settings().trading.mode.value,
        }


class BrokerRegistry:
    def __init__(self) -> None:
        from finagent.brokers.alpaca import AlpacaBroker
        from finagent.brokers.angel import AngelBroker
        from finagent.brokers.zerodha import ZerodhaBroker

        self._adapters: dict[str, BrokerAdapter] = {
            "paper": PaperBrokerAdapter(),
            "zerodha": ZerodhaBroker(),
            "angel": AngelBroker(),
            "alpaca": AlpacaBroker(),
        }
        # Ensure Alpaca exposes secret_names for UI chips
        alpaca = self._adapters["alpaca"]
        if not hasattr(alpaca, "secret_names"):
            alpaca.secret_names = ["ALPACA_API_KEY", "ALPACA_API_SECRET"]
            alpaca.display_name = getattr(alpaca, "display_name", "Alpaca")

    def register(self, adapter: BrokerAdapter) -> None:
        self._adapters[adapter.name] = adapter

    def list_adapters(self) -> list[dict[str, Any]]:
        out = []
        for a in self._adapters.values():
            item: dict[str, Any] = {
                "name": a.name,
                "supports_live": a.supports_live,
            }
            if hasattr(a, "display_name"):
                item["display_name"] = a.display_name
            names = getattr(a, "secret_names", None)
            if names is None and a.name == "alpaca":
                names = ["ALPACA_API_KEY", "ALPACA_API_SECRET"]
            if names:
                item["secret_names"] = list(names)
            if hasattr(a, "_configured"):
                try:
                    item["configured"] = bool(a._configured())  # type: ignore[attr-defined]
                except Exception:
                    item["configured"] = False
            if hasattr(a, "_session_ready"):
                try:
                    item["session"] = bool(a._session_ready())  # type: ignore[attr-defined]
                except Exception:
                    item["session"] = False
            out.append(item)
        return out

    def get(self, name: str | None = None) -> BrokerAdapter:
        settings = get_settings().trading
        if name:
            if name not in self._adapters:
                raise KeyError(name)
            return self._adapters[name]
        if settings.mode == TradingMode.LIVE:
            preferred = (settings.default_broker or "").strip().lower()
            if preferred and preferred in self._adapters:
                adapter = self._adapters[preferred]
                if adapter.supports_live:
                    return adapter
            raise RuntimeError(
                "Live mode needs a default broker in Settings → Trading "
                "(Zerodha, Angel, or Alpaca) that supports live trading"
            )
        # Paper: optional Alpaca paper backend
        if (settings.paper_backend or "local").lower() == "alpaca":
            alpaca = self._adapters.get("alpaca")
            if alpaca is not None and getattr(alpaca, "_configured", lambda: False)():
                return alpaca
        return self._adapters["paper"]

    async def place_order_safe(
        self,
        request: BrokerOrderRequest,
        *,
        confirmed: bool = False,
        broker_name: str | None = None,
    ) -> dict[str, Any]:
        settings = get_settings().trading
        if settings.kill_switch:
            return {"ok": False, "error": "Kill switch enabled — Panic Stop is on"}
        if settings.mode == TradingMode.LIVE:
            name = broker_name or settings.default_broker
            try:
                adapter = self.get(name)
            except (KeyError, RuntimeError) as exc:
                return {"ok": False, "error": str(exc)}
            if not adapter.supports_live:
                return {"ok": False, "error": "Selected broker does not support live trading"}
            # Live orders always require confirmation
            if not confirmed:
                return {"ok": False, "error": "Live orders require explicit confirmation"}
        else:
            # Paper: confirmation gate when Settings requires it (UI/jobs pass confirmed=true)
            if settings.require_order_confirmation and not confirmed:
                return {"ok": False, "error": "Order confirmation required"}
            if (settings.paper_backend or "local").lower() == "alpaca" and (
                broker_name in (None, "alpaca")
            ):
                adapter = self._adapters["alpaca"]
                if not getattr(adapter, "_configured", lambda: False)():
                    adapter = self._adapters["paper"]
            else:
                adapter = self._adapters["paper"]
        try:
            result = await adapter.place_order(request)
        except Exception as exc:
            return {"ok": False, "error": str(exc), "broker": getattr(adapter, "name", "?")}
        return {"ok": True, "order": result, "mode": settings.mode.value, "broker": adapter.name}


_brokers: BrokerRegistry | None = None


def get_broker_registry() -> BrokerRegistry:
    global _brokers
    if _brokers is None:
        _brokers = BrokerRegistry()
    return _brokers


def reset_broker_registry() -> None:
    """Test helper."""
    global _brokers
    _brokers = None
