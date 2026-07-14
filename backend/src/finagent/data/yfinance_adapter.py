"""Global stocks/ETFs via yfinance."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from finagent.data.base import MarketDataAdapter, Quote
from finagent.portfolio.money import D


class YFinanceAdapter(MarketDataAdapter):
    name = "yfinance"

    async def get_quote(self, symbol: str) -> Quote:
        import asyncio

        import yfinance as yf

        def _fetch() -> Quote:
            t = yf.Ticker(symbol)
            info = t.fast_info
            price = getattr(info, "last_price", None) or getattr(info, "lastPrice", None)
            if price is None:
                hist = t.history(period="5d")
                if hist.empty:
                    raise ValueError(f"No quote for {symbol}")
                price = float(hist["Close"].iloc[-1])
            currency = getattr(info, "currency", None) or "USD"
            prev = getattr(info, "previous_close", None)
            change = None
            if prev:
                change = D((float(price) - float(prev)) / float(prev) * 100)
            return Quote(
                symbol=symbol.upper(),
                price=D(price),
                currency=str(currency),
                source=self.name,
                as_of=datetime.now(UTC),
                change_pct=change,
            )

        return await asyncio.to_thread(_fetch)

    async def search(self, query: str) -> list[dict[str, str]]:
        # yfinance has no great search; return query as candidate
        return [{"symbol": query.upper(), "name": query.upper(), "source": self.name}]

    async def get_history(self, symbol: str, period: str = "1mo") -> list[dict[str, Any]]:
        import asyncio

        import yfinance as yf

        def _hist() -> list[dict[str, Any]]:
            t = yf.Ticker(symbol)
            df = t.history(period=period)
            out: list[dict[str, Any]] = []
            for idx, row in df.iterrows():
                out.append(
                    {
                        "time": idx.isoformat(),
                        "open": float(row["Open"]),
                        "high": float(row["High"]),
                        "low": float(row["Low"]),
                        "close": float(row["Close"]),
                        "volume": float(row.get("Volume", 0)),
                    }
                )
            return out

        return await asyncio.to_thread(_hist)

    async def get_option_chain(self, symbol: str) -> dict[str, Any]:
        import asyncio

        import yfinance as yf

        def _chain() -> dict[str, Any]:
            t = yf.Ticker(symbol)
            dates = list(t.options or [])
            if not dates:
                return {"symbol": symbol, "expiries": [], "chains": {}}
            expiry = dates[0]
            chain = t.option_chain(expiry)
            def _df(df: Any) -> list[dict[str, Any]]:
                cols = ["contractSymbol", "strike", "lastPrice", "bid", "ask", "impliedVolatility", "volume", "openInterest"]
                present = [c for c in cols if c in df.columns]
                return df[present].head(50).to_dict(orient="records")
            return {
                "symbol": symbol.upper(),
                "source": self.name,
                "as_of": datetime.now(UTC).isoformat(),
                "expiries": dates[:12],
                "selected_expiry": expiry,
                "calls": _df(chain.calls),
                "puts": _df(chain.puts),
            }

        return await asyncio.to_thread(_chain)