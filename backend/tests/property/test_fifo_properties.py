"""Property-based FIFO invariants."""

from hypothesis import given, settings
from hypothesis import strategies as st

from finagent.portfolio.money import D
from finagent.portfolio.pnl import apply_buy, apply_sell


@given(
    buy_qty=st.decimals(
        min_value="1", max_value="100", places=2, allow_nan=False, allow_infinity=False
    ),
    buy_px=st.decimals(
        min_value="1", max_value="1000", places=2, allow_nan=False, allow_infinity=False
    ),
    sell_frac=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
    sell_px=st.decimals(
        min_value="1", max_value="1000", places=2, allow_nan=False, allow_infinity=False
    ),
)
@settings(max_examples=50)
def test_fifo_conservation(buy_qty, buy_px, sell_frac, sell_px) -> None:  # type: ignore[no-untyped-def]
    lots = apply_buy([], D(buy_qty), D(buy_px))
    sell_qty = D(buy_qty) * D(str(round(sell_frac, 4)))
    if sell_qty <= 0:
        return
    if sell_qty > D(buy_qty):
        sell_qty = D(buy_qty)
    result = apply_sell(lots, sell_qty, D(sell_px))
    remaining_qty = sum((lot.quantity for lot in result.remaining_lots), D(0))
    assert remaining_qty + sell_qty == D(buy_qty)
