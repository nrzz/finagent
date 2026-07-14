"""Secrets + calendar + F&O coverage."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from finagent.portfolio.money import D
from finagent.security.secrets import decrypt_secret, encrypt_secret, mask_secret
from finagent.trading.calendars import is_crypto_market, is_market_open, market_open
from finagent.trading.fno import black_scholes_greeks, estimate_margin, is_expired, lot_size


def test_encrypt_roundtrip() -> None:
    token = encrypt_secret("super-secret-key")
    assert decrypt_secret(token) == "super-secret-key"
    assert mask_secret("abcdef") == "**cdef" or mask_secret("abcdef").endswith("cdef")


def test_mask_short() -> None:
    assert mask_secret("ab") == "**"
    assert mask_secret(None) is None


def test_crypto_always_open() -> None:
    assert is_crypto_market("BTC/USDT", "crypto")
    assert is_market_open("CRYPTO", asset_class="crypto") is True
    assert market_open("CRYPTO", asset_class="crypto") is True


def test_nse_weekend_closed() -> None:
    # Sunday in Kolkata
    sunday = datetime(2026, 7, 12, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open("NSE", when=sunday) is False


def test_nse_weekday_session() -> None:
    midday = datetime(2026, 7, 14, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert is_market_open("NSE", when=midday) is True


def test_fno_helpers() -> None:
    assert lot_size("NIFTY") == 25
    assert is_expired(date(2020, 1, 1), date(2026, 1, 1))
    assert estimate_margin(D("100"), 25) > 0
    g = black_scholes_greeks(100, 100, 0.25, 0.05, 0.2, "CE")
    assert 0.4 < g.delta < 0.7
    g2 = black_scholes_greeks(100, 100, 0.25, 0.05, 0.2, "PE")
    assert g2.delta < 0
