"""PnL / FIFO / XIRR tests."""

from datetime import date

from finagent.portfolio.money import D
from finagent.portfolio.pnl import (
    allocation_weights,
    apply_buy,
    apply_sell,
    apply_split,
    avg_cost,
    unrealized_pnl,
    xirr,
)


def test_fifo_realized() -> None:
    lots = apply_buy([], D(10), D(100))
    lots = apply_buy(lots, D(10), D(120))
    result = apply_sell(lots, D(15), D(130))
    # 10*(130-100) + 5*(130-120) = 300 + 50 = 350
    assert result.realized_pnl == D("350.00")
    assert avg_cost(result.remaining_lots) == D("120")


def test_unrealized() -> None:
    lots = apply_buy([], D(2), D(50))
    assert unrealized_pnl(lots, D(60)) == D("20.00")


def test_split() -> None:
    lots = apply_buy([], D(10), D(100))
    split = apply_split(lots, D(2), D(1))
    assert split[0].quantity == D("20.00000000")
    assert split[0].cost == D("50.00000000")


def test_allocation() -> None:
    w = allocation_weights({"a": D(70), "b": D(30)})
    assert w["a"] == D("70.00")


def test_xirr_simple() -> None:
    flows = [
        (date(2020, 1, 1), D(-1000)),
        (date(2021, 1, 1), D(1100)),
    ]
    rate = xirr(flows)
    assert rate is not None
    assert D("9") < rate < D("11")
