"""P&L, FIFO lots, XIRR, allocation helpers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from finagent.portfolio.money import D, quantize


@dataclass
class Lot:
    quantity: Decimal
    cost: Decimal
    acquired: date | None = None


@dataclass
class FifoResult:
    remaining_lots: list[Lot] = field(default_factory=list)
    realized_pnl: Decimal = field(default_factory=lambda: D(0))
    cost_basis_sold: Decimal = field(default_factory=lambda: D(0))


def apply_buy(
    lots: list[Lot], quantity: Decimal, price: Decimal, acquired: date | None = None
) -> list[Lot]:
    lots = list(lots)
    lots.append(Lot(quantity=quantity, cost=price, acquired=acquired))
    return lots


def apply_sell(lots: list[Lot], quantity: Decimal, price: Decimal) -> FifoResult:
    remaining = quantity
    realized = D(0)
    cost_sold = D(0)
    out: list[Lot] = []
    for lot in lots:
        if remaining <= 0:
            out.append(lot)
            continue
        take = min(lot.quantity, remaining)
        cost_sold += take * lot.cost
        realized += take * (price - lot.cost)
        leftover = lot.quantity - take
        remaining -= take
        if leftover > 0:
            out.append(Lot(quantity=leftover, cost=lot.cost, acquired=lot.acquired))
    if remaining > 0:
        raise ValueError("Insufficient quantity to sell")
    return FifoResult(
        remaining_lots=out, realized_pnl=quantize(realized), cost_basis_sold=quantize(cost_sold)
    )


def unrealized_pnl(lots: list[Lot], mark: Decimal) -> Decimal:
    return quantize(sum((lot.quantity * (mark - lot.cost) for lot in lots), D(0)))


def avg_cost(lots: list[Lot]) -> Decimal:
    qty = sum((lot.quantity for lot in lots), D(0))
    if qty == 0:
        return D(0)
    total = sum((lot.quantity * lot.cost for lot in lots), D(0))
    return quantize(total / qty, 8)


def market_value(lots: list[Lot], mark: Decimal) -> Decimal:
    qty = sum((lot.quantity for lot in lots), D(0))
    return quantize(qty * mark)


def allocation_weights(values: dict[str, Decimal]) -> dict[str, Decimal]:
    total = sum(values.values(), D(0))
    if total == 0:
        return {k: D(0) for k in values}
    return {k: quantize((v / total) * D(100), 2) for k, v in values.items()}


def xirr(cashflows: list[tuple[date, Decimal]], guess: float = 0.1) -> Decimal | None:
    """Newton-Raphson XIRR. cashflows: (date, amount) with negatives = investments."""
    if len(cashflows) < 2:
        return None
    amounts = [(d, float(a)) for d, a in cashflows]
    if not any(a > 0 for _, a in amounts) or not any(a < 0 for _, a in amounts):
        return None
    t0 = amounts[0][0]

    def npv(rate: float) -> float:
        return sum(a / ((1 + rate) ** ((d - t0).days / 365.0)) for d, a in amounts)

    def d_npv(rate: float) -> float:
        return sum(
            -((d - t0).days / 365.0) * a / ((1 + rate) ** (((d - t0).days / 365.0) + 1))
            for d, a in amounts
        )

    rate = guess
    for _ in range(64):
        f = npv(rate)
        df = d_npv(rate)
        if abs(df) < 1e-12:
            return None
        new_rate = rate - f / df
        if abs(new_rate - rate) < 1e-8:
            return quantize(D(new_rate) * D(100), 4)
        rate = new_rate
        if rate <= -0.9999:
            return None
    return None


def apply_split(lots: list[Lot], ratio_num: Decimal, ratio_den: Decimal) -> list[Lot]:
    """Apply stock split (e.g. 2-for-1 => num=2, den=1)."""
    if ratio_den == 0:
        raise ValueError("Invalid split ratio")
    factor = ratio_num / ratio_den
    return [
        Lot(
            quantity=quantize(lot.quantity * factor, 8),
            cost=quantize(lot.cost / factor, 8),
            acquired=lot.acquired,
        )
        for lot in lots
    ]
