"""Broker adapter plugin interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class BrokerOrderRequest(BaseModel):
    symbol: str
    side: str
    quantity: str
    order_type: str = "market"
    limit_price: str | None = None
    idempotency_key: str | None = None
    asset_class: str = "equity"
    meta: dict[str, Any] = Field(default_factory=dict)


class BrokerAdapter(ABC):
    """Implement this to add a live broker/exchange.

    Safety: live adapters must refuse orders unless:
    - settings.trading.mode == live
    - kill_switch is False
    - require_order_confirmation has been satisfied by the API layer
    """

    name: str
    supports_live: bool = False

    @abstractmethod
    async def get_holdings(self) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    async def place_order(self, request: BrokerOrderRequest) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    async def cancel_order(self, order_id: str) -> dict[str, Any]:
        raise NotImplementedError

    async def get_orders(self) -> list[dict[str, Any]]:
        return []

    async def healthcheck(self) -> dict[str, Any]:
        return {"ok": True, "name": self.name}
