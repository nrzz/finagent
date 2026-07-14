"""Persist / restore paper broker state to SQLite."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from finagent.db.models import Holding, OrderRow, PaperState
from finagent.logging_setup import get_logger
from finagent.portfolio.money import D
from finagent.portfolio.pnl import Lot
from finagent.trading.orders import Order, OrderSide, OrderStatus, OrderType
from finagent.trading.paper import PaperAccount, PaperBroker, get_paper_broker

log = get_logger(__name__)

PAPER_ACCOUNT = "paper"


async def load_paper_from_db(session: AsyncSession) -> None:
    broker = get_paper_broker()
    state = (await session.execute(select(PaperState).where(PaperState.id == 1))).scalar_one_or_none()
    if state:
        broker.account.cash = D(state.cash)
        broker.account.currency = state.currency
        broker.account.realized_pnl = D(state.realized_pnl)
        broker.account.daily_realized = D(state.daily_realized)
    else:
        session.add(
            PaperState(
                id=1,
                cash=str(broker.account.cash),
                currency=broker.account.currency,
                realized_pnl=str(broker.account.realized_pnl),
                daily_realized=str(broker.account.daily_realized),
            )
        )
        await session.commit()

    holdings = (
        await session.execute(select(Holding).where(Holding.account == PAPER_ACCOUNT))
    ).scalars().all()
    positions: dict[str, list[Lot]] = {}
    for h in holdings:
        qty = D(h.quantity)
        if qty == 0:
            continue
        acquired = None
        if getattr(h, "acquired", None):
            try:
                acquired = date.fromisoformat(h.acquired)
            except ValueError:
                acquired = None
        positions.setdefault(h.symbol.upper(), []).append(
            Lot(quantity=qty, cost=D(h.avg_cost), acquired=acquired)
        )
    if holdings:
        broker.account.positions = positions

    orders = (await session.execute(select(OrderRow).where(OrderRow.mode == "paper"))).scalars().all()
    broker.account.orders = {}
    for row in orders:
        order = Order(
            idempotency_key=row.idempotency_key,
            symbol=row.symbol,
            side=OrderSide(row.side.lower()),
            quantity=D(row.quantity),
            order_type=OrderType((row.order_type or "market").lower()),
            limit_price=D(row.limit_price) if row.limit_price else None,
            filled_quantity=D(row.filled_quantity or "0"),
            avg_fill_price=D(row.avg_fill_price) if row.avg_fill_price else None,
            status=OrderStatus(row.status),
            asset_class=row.asset_class or "equity",
            mode="paper",
            meta=dict(row.meta or {}),
        )
        broker.account.orders[order.idempotency_key] = order
    log.info(
        "paper_loaded",
        positions=len(broker.account.positions),
        orders=len(broker.account.orders),
        cash=str(broker.account.cash),
    )


async def save_paper_to_db(session: AsyncSession, broker: PaperBroker | None = None) -> None:
    broker = broker or get_paper_broker()
    state = (await session.execute(select(PaperState).where(PaperState.id == 1))).scalar_one_or_none()
    if state is None:
        state = PaperState(id=1)
        session.add(state)
    state.cash = str(broker.account.cash)
    state.currency = broker.account.currency
    state.realized_pnl = str(broker.account.realized_pnl)
    state.daily_realized = str(broker.account.daily_realized)

    await session.execute(delete(Holding).where(Holding.account == PAPER_ACCOUNT))
    for sym, lots in broker.account.positions.items():
        asset_class = "option" if "|" in sym else "equity"
        for order in broker.account.orders.values():
            if order.symbol == sym and order.asset_class:
                asset_class = order.asset_class
                break
        for lot in lots:
            if lot.quantity == 0:
                continue
            session.add(
                Holding(
                    symbol=sym,
                    asset_class=asset_class,
                    quantity=str(lot.quantity),
                    avg_cost=str(lot.cost),
                    currency=broker.account.currency,
                    account=PAPER_ACCOUNT,
                    acquired=lot.acquired.isoformat() if lot.acquired else None,
                )
            )

    for order in broker.account.orders.values():
        existing = (
            await session.execute(
                select(OrderRow).where(OrderRow.idempotency_key == order.idempotency_key)
            )
        ).scalar_one_or_none()
        payload = {
            "symbol": order.symbol,
            "side": order.side.value,
            "order_type": order.order_type.value,
            "quantity": str(order.quantity),
            "limit_price": str(order.limit_price) if order.limit_price is not None else None,
            "filled_quantity": str(order.filled_quantity),
            "avg_fill_price": str(order.avg_fill_price) if order.avg_fill_price is not None else None,
            "status": order.status.value,
            "asset_class": order.asset_class,
            "mode": "paper",
            "meta": order.meta,
        }
        if existing:
            for k, v in payload.items():
                setattr(existing, k, v)
        else:
            session.add(OrderRow(idempotency_key=order.idempotency_key, **payload))

    await session.commit()


async def persist_paper_after_order(session: AsyncSession) -> None:
    await save_paper_to_db(session)
