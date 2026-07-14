"""Extra paper / money edge cases for coverage."""

from finagent.portfolio.money import D, format_money, quantize_qty, round_to_tick
from finagent.trading.orders import Order, OrderSide, OrderStatus, OrderType
from finagent.trading.paper import PaperBroker, get_paper_broker


def test_western_format() -> None:
    assert "," in format_money(D("1234.5"), "USD", "western")


def test_quantize_qty() -> None:
    assert quantize_qty(D("1.123456789")) == D("1.12345679")


def test_round_crypto_tick() -> None:
    assert round_to_tick(D("1.234"), "crypto") >= D(0)


def test_partial_fill_then_complete() -> None:
    o = Order(
        idempotency_key="p1",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=D(10),
        order_type=OrderType.MARKET,
    )
    o.transition(OrderStatus.OPEN)
    o.apply_fill(D(4), D(10))
    assert o.status == OrderStatus.PARTIALLY_FILLED
    o.apply_fill(D(6), D(12))
    assert o.status == OrderStatus.FILLED
    assert o.avg_fill_price is not None


def test_limit_rests_open() -> None:
    broker = PaperBroker()
    broker.reset(D(1_000_000))
    o = broker.place_order(
        symbol="AAPL",
        side="buy",
        quantity="1",
        price="100",
        order_type="limit",
        limit_price="90",
        force_open_market=True,
    )
    assert o.status == OrderStatus.OPEN


def test_sell_and_singleton() -> None:
    b = get_paper_broker()
    b.reset(D(1_000_000))
    b.place_order(symbol="X", side="buy", quantity="5", price="10", force_open_market=True)
    o = b.place_order(symbol="X", side="sell", quantity="2", price="12", force_open_market=True)
    assert o.status == OrderStatus.FILLED
    snap = b.positions_snapshot({"X": D(12)})
    assert any(p["symbol"] == "X" for p in snap)
    assert len(b.blotter()) >= 2
