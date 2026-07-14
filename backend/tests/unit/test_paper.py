"""Paper trading + order state machine tests."""

from finagent.portfolio.money import D
from finagent.trading.orders import Order, OrderSide, OrderStatus
from finagent.trading.paper import PaperBroker


def test_order_fill_lifecycle() -> None:
    o = Order(idempotency_key="k1", symbol="AAPL", side=OrderSide.BUY, quantity=D(10))
    o.transition(OrderStatus.OPEN)
    o.apply_fill(D(10), D(100))
    assert o.status == OrderStatus.FILLED
    assert o.avg_fill_price == D(100)


def test_idempotent_orders() -> None:
    broker = PaperBroker()
    broker.reset(D(1_000_000))
    a = broker.place_order(
        symbol="RELIANCE",
        side="buy",
        quantity="1",
        price="2500",
        idempotency_key="same",
        force_open_market=True,
    )
    b = broker.place_order(
        symbol="RELIANCE",
        side="buy",
        quantity="1",
        price="2500",
        idempotency_key="same",
        force_open_market=True,
    )
    assert a.idempotency_key == b.idempotency_key
    assert a.status == OrderStatus.FILLED


def test_insufficient_cash() -> None:
    broker = PaperBroker()
    broker.reset(D(100))
    o = broker.place_order(
        symbol="AAPL", side="buy", quantity="10", price="50", force_open_market=True
    )
    assert o.status == OrderStatus.REJECTED


def test_kill_switch(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from finagent.config import get_settings, set_settings

    s = get_settings().model_copy(deep=True)
    s.trading.kill_switch = True
    set_settings(s)
    broker = PaperBroker()
    broker.reset(D(1_000_000))
    o = broker.place_order(
        symbol="AAPL", side="buy", quantity="1", price="10", force_open_market=True
    )
    assert o.status == OrderStatus.REJECTED
    s.trading.kill_switch = False
    set_settings(s)
