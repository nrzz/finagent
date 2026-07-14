"""In-memory paper trading engine with risk checks."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from finagent.config import get_settings
from finagent.config.schema import TradingMode
from finagent.portfolio.money import D, quantize
from finagent.portfolio.pnl import Lot, apply_buy, apply_sell, avg_cost, unrealized_pnl
from finagent.trading.calendars import market_open
from finagent.trading.orders import Order, OrderSide, OrderStatus, OrderType


@dataclass
class PaperAccount:
    cash: Decimal
    currency: str = "INR"
    positions: dict[str, list[Lot]] = field(default_factory=dict)
    orders: dict[str, Order] = field(default_factory=dict)
    realized_pnl: Decimal = field(default_factory=lambda: D(0))
    daily_realized: Decimal = field(default_factory=lambda: D(0))


class PaperBroker:
    def __init__(self) -> None:
        settings = get_settings()
        self.account = PaperAccount(
            cash=D(settings.trading.paper_starting_cash),
            currency=settings.trading.paper_currency,
        )

    def reset(self, cash: Decimal | None = None) -> None:
        settings = get_settings()
        self.account = PaperAccount(
            cash=cash if cash is not None else D(settings.trading.paper_starting_cash),
            currency=settings.trading.paper_currency,
        )

    def _risk_check(self, order: Order, mark: Decimal) -> str | None:
        settings = get_settings().trading
        if settings.kill_switch:
            return "Kill switch is enabled — trading halted"
        if settings.mode != TradingMode.PAPER and settings.mode != TradingMode.LIVE:
            return "Unknown trading mode"
        # Live is handled by live brokers; paper engine only runs paper.
        notional = order.quantity * mark
        if notional > D(settings.risk.max_order_value):
            return f"Order value {notional} exceeds max_order_value {settings.risk.max_order_value}"
        equity = self.equity({order.symbol: mark})
        if equity > 0:
            pct = (notional / equity) * D(100)
            if pct > D(settings.risk.max_position_pct):
                return f"Position size {pct}% exceeds max_position_pct {settings.risk.max_position_pct}%"
        if self.account.daily_realized < 0:
            loss_pct = (abs(self.account.daily_realized) / max(equity, D(1))) * D(100)
            if loss_pct >= D(settings.risk.max_daily_loss_pct):
                return "Daily loss limit reached"
        return None

    def equity(self, marks: dict[str, Decimal]) -> Decimal:
        total = self.account.cash
        for sym, lots in self.account.positions.items():
            mark = marks.get(sym, avg_cost(lots))
            total += sum((lot.quantity * mark for lot in lots), D(0))
        return quantize(total)

    def place_order(
        self,
        *,
        symbol: str,
        side: str,
        quantity: str | Decimal,
        price: str | Decimal,
        order_type: str = "market",
        limit_price: str | Decimal | None = None,
        idempotency_key: str | None = None,
        asset_class: str = "equity",
        exchange: str = "NSE",
        force_open_market: bool = False,
        meta: dict[str, Any] | None = None,
    ) -> Order:
        key = idempotency_key or str(uuid.uuid4())
        if key in self.account.orders:
            return self.account.orders[key]

        order = Order(
            idempotency_key=key,
            symbol=symbol.upper(),
            side=OrderSide(side.lower()),
            quantity=D(quantity),
            order_type=OrderType(order_type.lower()),
            limit_price=D(limit_price) if limit_price is not None else None,
            asset_class=asset_class,
            mode="paper",
            meta=meta or {},
        )

        if not force_open_market and not market_open(exchange, asset_class=asset_class):
            if asset_class != "crypto":
                order.transition(OrderStatus.REJECTED)
                order.meta["reject_reason"] = "Market closed"
                self.account.orders[key] = order
                return order

        mark = D(price)
        reason = self._risk_check(order, mark)
        if reason:
            order.transition(OrderStatus.REJECTED)
            order.meta["reject_reason"] = reason
            self.account.orders[key] = order
            return order

        if order.order_type == OrderType.LIMIT and order.limit_price is not None:
            if order.side == OrderSide.BUY and mark > order.limit_price:
                order.transition(OrderStatus.OPEN)
                self.account.orders[key] = order
                return order
            if order.side == OrderSide.SELL and mark < order.limit_price:
                order.transition(OrderStatus.OPEN)
                self.account.orders[key] = order
                return order

        return self._fill(order, mark)

    def _fill(self, order: Order, price: Decimal) -> Order:
        notional = order.quantity * price
        lots = self.account.positions.get(order.symbol, [])
        if order.side == OrderSide.BUY:
            if notional > self.account.cash:
                order.transition(OrderStatus.REJECTED)
                order.meta["reject_reason"] = "Insufficient cash"
                self.account.orders[order.idempotency_key] = order
                return order
            self.account.cash -= notional
            self.account.positions[order.symbol] = apply_buy(lots, order.quantity, price)
        else:
            try:
                result = apply_sell(lots, order.quantity, price)
            except ValueError as exc:
                order.transition(OrderStatus.REJECTED)
                order.meta["reject_reason"] = str(exc)
                self.account.orders[order.idempotency_key] = order
                return order
            self.account.cash += notional
            self.account.positions[order.symbol] = result.remaining_lots
            self.account.realized_pnl += result.realized_pnl
            self.account.daily_realized += result.realized_pnl

        order.transition(OrderStatus.OPEN)
        order.apply_fill(order.quantity, price)
        self.account.orders[order.idempotency_key] = order
        return order

    def positions_snapshot(self, marks: dict[str, Decimal] | None = None) -> list[dict[str, Any]]:
        marks = marks or {}
        out: list[dict[str, Any]] = []
        for sym, lots in self.account.positions.items():
            qty = sum((lot.quantity for lot in lots), D(0))
            if qty == 0:
                continue
            mark = marks.get(sym, avg_cost(lots))
            out.append(
                {
                    "symbol": sym,
                    "quantity": str(qty),
                    "avg_cost": str(avg_cost(lots)),
                    "mark": str(mark),
                    "unrealized_pnl": str(unrealized_pnl(lots, mark)),
                    "market_value": str(quantize(qty * mark)),
                }
            )
        return out

    def blotter(self) -> list[dict[str, Any]]:
        return [
            o.to_dict()
            for o in sorted(self.account.orders.values(), key=lambda x: x.created_at, reverse=True)
        ]


_paper: PaperBroker | None = None


def get_paper_broker() -> PaperBroker:
    global _paper
    if _paper is None:
        _paper = PaperBroker()
    return _paper
