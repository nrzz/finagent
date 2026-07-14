"""India markets: NSE-style quotes via yfinance (.NS) + AMFI mutual fund NAVs."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from finagent.data.base import MarketDataAdapter, Quote
from finagent.data.yfinance_adapter import YFinanceAdapter
from finagent.portfolio.money import D


class IndiaAdapter(MarketDataAdapter):
    name = "india"

    def __init__(self) -> None:
        self._yf = YFinanceAdapter()

    def _normalize(self, symbol: str) -> str:
        s = symbol.upper().strip()
        if s.endswith(".NS") or s.endswith(".BO") or s.isdigit():
            return s
        # Mutual fund scheme codes are numeric — leave as-is for AMFI
        return f"{s}.NS"

    async def get_quote(self, symbol: str) -> Quote:
        s = symbol.strip()
        if s.isdigit() or s.upper().startswith("MF:"):
            code = s.split(":")[-1]
            return await self.get_mf_nav(code)
        q = await self._yf.get_quote(self._normalize(s))
        q.source = self.name
        if q.currency in {"INR", "N/A", None}:
            q.currency = "INR"
        return q

    async def get_mf_nav(self, scheme_code: str) -> Quote:
        """Fetch NAV from mfapi.in (AMFI-backed public API)."""
        url = f"https://api.mfapi.in/mf/{scheme_code}"
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
        meta = data.get("meta", {})
        history = data.get("data") or []
        if not history:
            raise ValueError(f"No NAV for scheme {scheme_code}")
        latest = history[0]
        nav = D(latest["nav"])
        as_of = datetime.strptime(latest["date"], "%d-%m-%Y").replace(tzinfo=UTC)
        return Quote(
            symbol=f"MF:{scheme_code}",
            price=nav,
            currency="INR",
            source="amfi/mfapi",
            as_of=as_of,
            meta={"scheme_name": meta.get("scheme_name"), "fund_house": meta.get("fund_house")},
        )

    async def search(self, query: str) -> list[dict[str, str]]:
        # Mutual fund search
        if not query:
            return []
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"https://api.mfapi.in/mf/search?q={query}")
                if resp.status_code == 200:
                    rows = resp.json()
                    return [
                        {
                            "symbol": f"MF:{r.get('schemeCode')}",
                            "name": r.get("schemeName", ""),
                            "source": "amfi/mfapi",
                        }
                        for r in rows[:20]
                    ]
        except Exception:
            pass
        return [{"symbol": self._normalize(query), "name": query, "source": self.name}]

    async def get_history(self, symbol: str, period: str = "1mo") -> list[dict[str, Any]]:
        if symbol.strip().isdigit() or symbol.upper().startswith("MF:"):
            return []
        return await self._yf.get_history(self._normalize(symbol), period)

    async def get_option_chain(self, symbol: str) -> dict[str, Any]:
        # Best-effort via yfinance for index options when available
        sym = self._normalize(symbol.replace("^", ""))
        chain = await self._yf.get_option_chain(sym)
        chain["source"] = self.name
        chain["note"] = "NSE option chain via available data feed; verify lot sizes before trading"
        return chain