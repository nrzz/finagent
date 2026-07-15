"""Market data adapter interface + quote model."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from cachetools import TTLCache
from tenacity import retry, stop_after_attempt, wait_exponential


@dataclass
class Quote:
    symbol: str
    price: Decimal
    currency: str
    source: str
    as_of: datetime
    change_pct: Decimal | None = None
    bid: Decimal | None = None
    ask: Decimal | None = None
    stale: bool = False
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        age_s = (datetime.now(UTC) - self.as_of.astimezone(UTC)).total_seconds()
        return {
            "symbol": self.symbol,
            "price": str(self.price),
            "currency": self.currency,
            "source": self.source,
            "as_of": self.as_of.isoformat(),
            "age_seconds": int(age_s),
            "stale": self.stale or age_s > 120,
            "change_pct": str(self.change_pct) if self.change_pct is not None else None,
            "bid": str(self.bid) if self.bid is not None else None,
            "ask": str(self.ask) if self.ask is not None else None,
            "meta": self.meta,
        }


class MarketDataAdapter(ABC):
    name: str

    @abstractmethod
    async def get_quote(self, symbol: str) -> Quote:
        raise NotImplementedError

    async def search(self, query: str) -> list[dict[str, str]]:
        return []

    async def get_history(self, symbol: str, period: str = "1mo") -> list[dict[str, Any]]:
        return []

    async def get_option_chain(self, symbol: str) -> dict[str, Any]:
        return {"symbol": symbol, "options": [], "note": "Not supported by this adapter"}


class CachedAdapter(MarketDataAdapter):
    def __init__(self, inner: MarketDataAdapter, ttl_s: int = 30) -> None:
        self.inner = inner
        self.name = inner.name
        self._ttl_s = ttl_s
        self._cache: TTLCache[str, Quote] = TTLCache(maxsize=2048, ttl=ttl_s)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        reraise=True,
    )
    async def get_quote(self, symbol: str) -> Quote:
        key = symbol.upper()
        if key in self._cache:
            q = self._cache[key]
            age = (datetime.now(UTC) - q.as_of.astimezone(UTC)).total_seconds()
            return replace(q, stale=age > min(self._ttl_s, 120))
        quote = await self.inner.get_quote(symbol)
        self._cache[key] = quote
        return quote

    async def search(self, query: str) -> list[dict[str, str]]:
        return await self.inner.search(query)

    async def get_history(self, symbol: str, period: str = "1mo") -> list[dict[str, Any]]:
        return await self.inner.get_history(symbol, period)

    async def get_option_chain(self, symbol: str) -> dict[str, Any]:
        return await self.inner.get_option_chain(symbol)
