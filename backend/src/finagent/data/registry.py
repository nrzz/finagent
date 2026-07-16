"""Market data registry — routes symbols to enabled adapters."""

from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Any

from finagent.config import get_settings
from finagent.data.base import CachedAdapter, MarketDataAdapter, Quote
from finagent.data.ccxt_adapter import CCXTAdapter
from finagent.data.india_adapter import IndiaAdapter
from finagent.data.yfinance_adapter import YFinanceAdapter


class MarketDataRegistry:
    def __init__(self) -> None:
        self._fingerprint: str | None = None
        self._rebuild()

    @staticmethod
    def _markets_fingerprint() -> str:
        dump = get_settings().markets.model_dump(mode="json")
        raw = json.dumps(dump, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode()).hexdigest()

    def _rebuild(self) -> None:
        settings = get_settings().markets
        ttl = settings.quote_cache_ttl_s
        self.adapters: dict[str, MarketDataAdapter] = {}
        if settings.stocks_global:
            self.adapters["yfinance"] = CachedAdapter(YFinanceAdapter(), ttl)
        if settings.india:
            self.adapters["india"] = CachedAdapter(IndiaAdapter(), ttl)
        if settings.crypto.enabled:
            ex = settings.crypto.exchanges[0] if settings.crypto.exchanges else "binance"
            self.adapters["ccxt"] = CachedAdapter(CCXTAdapter(ex), ttl)
        self._fingerprint = self._markets_fingerprint()

    def refresh(self) -> None:
        self._rebuild()

    def _ensure_fresh(self) -> None:
        if self._fingerprint != self._markets_fingerprint():
            self._rebuild()

    def _pick(self, symbol: str) -> MarketDataAdapter:
        self._ensure_fresh()
        s = symbol.upper()
        if s.startswith("MF:") or s.isdigit():
            if "india" not in self.adapters:
                raise RuntimeError("India markets disabled")
            return self.adapters["india"]
        if "/" in s or s.endswith("USDT") or "-USD" in s:
            if "ccxt" not in self.adapters:
                raise RuntimeError("Crypto markets disabled")
            return self.adapters["ccxt"]
        if s.endswith(".NS") or s.endswith(".BO"):
            if "india" in self.adapters:
                return self.adapters["india"]
            if "yfinance" in self.adapters:
                return self.adapters["yfinance"]
        # Bare US/global tickers (AAPL, MSFT) → yfinance; India needs .NS/.BO suffix
        if "yfinance" in self.adapters:
            return self.adapters["yfinance"]
        if "india" in self.adapters:
            return self.adapters["india"]
        if self.adapters:
            return next(iter(self.adapters.values()))
        raise RuntimeError("No market data adapters enabled")

    async def get_quote(self, symbol: str) -> Quote:
        return await self._pick(symbol).get_quote(symbol)

    async def search(self, query: str) -> list[dict[str, str]]:
        self._ensure_fresh()
        results: list[dict[str, str]] = []
        for adapter in self.adapters.values():
            try:
                results.extend(await adapter.search(query))
            except Exception:
                continue
        # dedupe by symbol
        seen: set[str] = set()
        out: list[dict[str, str]] = []
        for r in results:
            if r["symbol"] in seen:
                continue
            seen.add(r["symbol"])
            out.append(r)
        return out[:30]

    async def get_history(
        self, symbol: str, period: str = "1mo", interval: str = "1d"
    ) -> list[dict[str, Any]]:
        return await self._pick(symbol).get_history(symbol, period, interval)

    async def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        async def _one(sym: str) -> dict[str, Any]:
            try:
                q = await self.get_quote(sym)
                return q.to_dict()
            except Exception as exc:
                return {"symbol": sym, "error": str(exc)}

        if not symbols:
            return []
        return list(await asyncio.gather(*[_one(s) for s in symbols]))

    async def get_option_chain(self, symbol: str) -> dict[str, Any]:
        return await self._pick(symbol).get_option_chain(symbol)


_registry: MarketDataRegistry | None = None


def get_market_registry() -> MarketDataRegistry:
    global _registry
    if _registry is None:
        _registry = MarketDataRegistry()
    return _registry
