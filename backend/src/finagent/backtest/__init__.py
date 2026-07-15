"""Lightweight backtesting helpers (foundations only)."""

from __future__ import annotations


def simulate_dca(prices: list[float], qty_each: float) -> dict[str, float]:
    """Dollar-cost average: buy ``qty_each`` units at each price.

    Returns final_value (last price × total qty), invested (sum price×qty),
    and simple return ((final_value - invested) / invested) or 0 if no invest.
    """
    if not prices or qty_each <= 0:
        return {"final_value": 0.0, "invested": 0.0, "simple_return": 0.0}

    invested = 0.0
    total_qty = 0.0
    for px in prices:
        if px <= 0:
            continue
        invested += px * qty_each
        total_qty += qty_each

    if total_qty <= 0 or invested <= 0:
        return {"final_value": 0.0, "invested": 0.0, "simple_return": 0.0}

    final_value = prices[-1] * total_qty if prices[-1] > 0 else 0.0
    simple_return = (final_value - invested) / invested
    return {
        "final_value": final_value,
        "invested": invested,
        "simple_return": simple_return,
    }
