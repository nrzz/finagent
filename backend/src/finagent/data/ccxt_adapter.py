"""Crypto quotes via ccxt."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from finagent.data.base import MarketDataAdapter, Quote
from finagent.portfolio.money import D


class CCXTAdapter(MarketDataAdapter):
    name = "ccxt"

    def __init__(self, exchange_id: str = "binance") -> None:
        self.exchange_id = exchange_id

    def _exchange(self) -> Any:
        import ccxt

        if not hasattr(ccxt, self.exchange_id):
            raise ValueError(f"Unknown exchange: {self.exchange_id}")
        klass = getattr(ccxt, self.exchange_id)
        return klass({"enableRateLimit": True})

    def _normalize(self, symbol: str) -> str:
        s = symbol.upper().replace("-", "/")
        if "/" not in s:
            if s.endswith("USDT"):
                return f"{s[:-4]}/USDT"
            return f"{s}/USDT"
        return s

    async def get_quote(self, symbol: str) -> Quote:
        import asyncio

        pair = self._normalize(symbol)

        def _fetch() -> Quote:
            ex = self._exchange()
            ticker = ex.fetch_ticker(pair)
            last = ticker.get("last") or ticker.get("close")
            if last is None:
                raise ValueError(f"No crypto quote for {pair}")
            return Quote(
                symbol=pair,
                price=D(last),
                currency=pair.split("/")[-1],
                source=f"ccxt:{self.exchange_id}",
                as_of=datetime.now(UTC),
                bid=D(ticker["bid"]) if ticker.get("bid") else None,
                ask=D(ticker["ask"]) if ticker.get("ask") else None,
                change_pct=D(ticker["percentage"])
                if ticker.get("percentage") is not None
                else None,
                meta={"exchange": self.exchange_id},
            )

        return await asyncio.to_thread(_fetch)

    async def search(self, query: str) -> list[dict[str, str]]:
        return [
            {"symbol": self._normalize(query), "name": self._normalize(query), "source": self.name}
        ]

    _INTERVAL_MAP = {"1d": "1d", "1h": "1h", "15m": "15m", "5m": "5m"}

    async def get_history(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> list[dict[str, Any]]:
        import asyncio
        from datetime import timedelta

        pair = self._normalize(symbol)
        timeframe = self._INTERVAL_MAP.get(interval, "1d")
        days = {"1d": 1, "5d": 5, "1mo": 30, "3mo": 90, "1y": 365}.get(period, 30)
        bars_per_day = {"1d": 1, "1h": 24, "15m": 96, "5m": 288}.get(timeframe, 1)
        limit = min(max(days * bars_per_day, 1), 1000)

        def _ohlcv() -> list[dict[str, Any]]:
            ex = self._exchange()
            since = int((datetime.now(UTC) - timedelta(days=days)).timestamp() * 1000)
            rows = ex.fetch_ohlcv(pair, timeframe=timeframe, since=since, limit=limit)
            return [
                {
                    "time": datetime.fromtimestamp(r[0] / 1000, tz=UTC).isoformat(),
                    "open": r[1],
                    "high": r[2],
                    "low": r[3],
                    "close": r[4],
                    "volume": r[5],
                }
                for r in rows
            ]

        return await asyncio.to_thread(_ohlcv)
