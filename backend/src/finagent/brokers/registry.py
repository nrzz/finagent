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


class BrokerRegistry:
    def __init__(self) -> None:
        self._adapters: dict[str, BrokerAdapter] = {"paper": PaperBrokerAdapter()}
        from finagent.brokers.stubs import build_reference_stubs

        for stub in build_reference_stubs():
            self._adapters[stub.name] = stub
        from finagent.brokers.alpaca import AlpacaBroker

        self._adapters["alpaca"] = AlpacaBroker()

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
                item["display_name"] = getattr(a, "display_name")
            if hasattr(a, "secret_names"):
                item["secret_names"] = getattr(a, "secret_names")
            if hasattr(a, "_configured"):
                try:
                    item["configured"] = bool(a._configured())  # type: ignore[attr-defined]
                except Exception:
                    item["configured"] = False
            out.append(item)
        return out

    def get(self, name: str | None = None) -> BrokerAdapter:
        settings = get_settings().trading
        if name:
            if name not in self._adapters:
                raise KeyError(name)
            return self._adapters[name]
        if settings.mode == TradingMode.LIVE:
            # Prefer first live adapter if any; else refuse
            for adapter in self._adapters.values():
                if adapter.supports_live:
                    return adapter
            raise RuntimeError("Live mode enabled but no live broker plugin registered")
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
            return {"ok": False, "error": "Kill switch enabled"}
        adapter = self.get(broker_name)
        if settings.mode == TradingMode.LIVE:
            if not adapter.supports_live:
                return {"ok": False, "error": "Selected broker does not support live trading"}
            # Live orders always require confirmation (cannot be silently skipped)
            if not confirmed:
                return {"ok": False, "error": "Live orders require explicit confirmation"}
        else:
            # Force paper adapter in paper mode
            adapter = self._adapters["paper"]
        result = await adapter.place_order(request)
        return {"ok": True, "order": result, "mode": settings.mode.value, "broker": adapter.name}


_brokers: BrokerRegistry | None = None


def get_broker_registry() -> BrokerRegistry:
    global _brokers
    if _brokers is None:
        _brokers = BrokerRegistry()
    return _brokers
