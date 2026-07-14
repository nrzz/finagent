"""Market symbol routing tests."""

from finagent.data.registry import MarketDataRegistry


def test_bare_us_ticker_routes_to_yfinance() -> None:
    reg = MarketDataRegistry()
    assert reg._pick("AAPL").name == "yfinance"
    assert reg._pick("MSFT").name == "yfinance"


def test_india_suffix_routes_to_india() -> None:
    reg = MarketDataRegistry()
    assert reg._pick("RELIANCE.NS").name == "india"
    assert reg._pick("TCS.BO").name == "india"


def test_crypto_pair_routes_to_ccxt() -> None:
    reg = MarketDataRegistry()
    assert reg._pick("BTC/USDT").name == "ccxt"
