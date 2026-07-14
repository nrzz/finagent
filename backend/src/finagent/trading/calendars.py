"""Exchange calendar helpers (market hours / holidays)."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

# Lightweight calendars without hard dependency failures if exchange_calendars missing.
CRYPTO_ALWAYS_OPEN = True

_MARKET_HOURS = {
    "NSE": ("Asia/Kolkata", 9, 15, 15, 30),  # 09:15–15:30
    "BSE": ("Asia/Kolkata", 9, 15, 15, 30),
    "NYSE": ("America/New_York", 9, 30, 16, 0),
    "NASDAQ": ("America/New_York", 9, 30, 16, 0),
}


def is_crypto_market(symbol: str | None = None, asset_class: str | None = None) -> bool:
    if asset_class == "crypto":
        return True
    if symbol and (
        "/" in symbol or symbol.upper().endswith("USDT") or symbol.upper().endswith("-USD")
    ):
        return True
    return False


def is_market_open(
    exchange: str = "NSE",
    when: datetime | None = None,
    asset_class: str = "equity",
) -> bool:
    if asset_class == "crypto" or exchange.upper() == "CRYPTO":
        return CRYPTO_ALWAYS_OPEN
    when = when or datetime.now(UTC)
    key = exchange.upper()
    if key not in _MARKET_HOURS:
        # Fallback: weekdays 24h for unknown exchanges (conservative open during weekday)
        local = when.astimezone(UTC)
        return local.weekday() < 5
    tz_name, h1, m1, h2, m2 = _MARKET_HOURS[key]
    local = when.astimezone(ZoneInfo(tz_name))
    if local.weekday() >= 5:
        return False
    open_t = local.replace(hour=h1, minute=m1, second=0, microsecond=0)
    close_t = local.replace(hour=h2, minute=m2, second=0, microsecond=0)
    return open_t <= local <= close_t


def try_exchange_calendar(exchange: str, when: datetime | None = None) -> bool | None:
    """Optional richer calendar via exchange_calendars; returns None if unavailable."""
    try:
        import exchange_calendars as xcals
    except ImportError:
        return None
    mapping = {"NSE": "XNSE", "BSE": "XBOM", "NYSE": "XNYS", "NASDAQ": "XNAS"}
    code = mapping.get(exchange.upper())
    if not code:
        return None
    try:
        cal = xcals.get_calendar(code)
        when = when or datetime.now(UTC)
        return bool(cal.is_open_on_minute(when.astimezone(UTC).replace(tzinfo=None)))
    except Exception:
        return None


def market_open(
    exchange: str = "NSE", when: datetime | None = None, asset_class: str = "equity"
) -> bool:
    rich = try_exchange_calendar(exchange, when)
    if rich is not None:
        return rich
    return is_market_open(exchange, when, asset_class)
