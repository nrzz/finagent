"""Order lifecycle state machine with idempotency."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from finagent.portfolio.money import D, quantize


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"


class OrderStatus(StrEnum):
    PENDING = "pending"
    OPEN = "open"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


_ALLOWED: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.OPEN, OrderStatus.REJECTED, OrderStatus.CANCELLED},
    OrderStatus.OPEN: {
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.FILLED,
        OrderStatus.CANCELLED,
        OrderStatus.REJECTED,
    },
    OrderStatus.PARTIALLY_FILLED: {OrderStatus.FILLED, OrderStatus.CANCELLED},
    OrderStatus.FILLED: set(),
    OrderStatus.CANCELLED: set(),
    OrderStatus.REJECTED: set(),
}


@dataclass
class Order:
    idempotency_key: str
    symbol: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType = OrderType.MARKET
    limit_price: Decimal | None = None
    filled_quantity: Decimal = field(default_factory=lambda: D(0))
    avg_fill_price: Decimal | None = None
    status: OrderStatus = OrderStatus.PENDING
    asset_class: str = "equity"
    mode: str = "paper"
    meta: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition(self, new_status: OrderStatus) -> None:
        allowed = _ALLOWED[self.status]
        if new_status not in allowed:
            raise ValueError(f"Invalid transition {self.status} → {new_status}")
        self.status = new_status
        self.updated_at = datetime.now(UTC)

    def apply_fill(self, qty: Decimal, price: Decimal) -> None:
        if qty <= 0:
            raise ValueError("Fill quantity must be positive")
        remaining = self.quantity - self.filled_quantity
        if qty > remaining:
            raise ValueError("Fill exceeds remaining quantity")
        prev = self.filled_quantity
        new_filled = prev + qty
        if self.avg_fill_price is None or prev == 0:
            self.avg_fill_price = price
        else:
            self.avg_fill_price = quantize(
                ((self.avg_fill_price * prev) + (price * qty)) / new_filled, 8
            )
        self.filled_quantity = new_filled
        if self.status == OrderStatus.PENDING:
            self.transition(OrderStatus.OPEN)
        if new_filled == self.quantity:
            if self.status in {OrderStatus.OPEN, OrderStatus.PARTIALLY_FILLED, OrderStatus.PENDING}:
                if self.status == OrderStatus.PENDING:
                    self.transition(OrderStatus.OPEN)
                if self.status == OrderStatus.OPEN or self.status == OrderStatus.PARTIALLY_FILLED:
                    self.transition(OrderStatus.FILLED)
        elif self.status == OrderStatus.OPEN:
            self.transition(OrderStatus.PARTIALLY_FILLED)
        self.updated_at = datetime.now(UTC)

    def to_dict(self) -> dict[str, Any]:
        display_price = self.avg_fill_price if self.avg_fill_price is not None else self.limit_price
        return {
            "idempotency_key": self.idempotency_key,
            "symbol": self.symbol,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "price": str(display_price) if display_price is not None else None,
            "limit_price": str(self.limit_price) if self.limit_price is not None else None,
            "filled_quantity": str(self.filled_quantity),
            "avg_fill_price": str(self.avg_fill_price) if self.avg_fill_price is not None else None,
            "status": self.status.value,
            "asset_class": self.asset_class,
            "mode": self.mode,
            "meta": self.meta,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
