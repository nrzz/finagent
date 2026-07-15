"""Backtesting API stubs (DCA foundation)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from finagent.api.auth import get_current_user
from finagent.backtest import simulate_dca
from finagent.data.registry import get_market_registry
from finagent.db.models import User

router = APIRouter(prefix="/api", tags=["backtest"])


class DcaIn(BaseModel):
    symbol: str = Field(min_length=1, max_length=64)
    period: str = "6mo"
    qty_each: float = Field(default=1.0, gt=0, le=1_000_000)


@router.get("/backtest/dca")
async def dca_get(
    symbol: str,
    period: str = "6mo",
    qty_each: float = 1.0,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    return await _run_dca(symbol, period, qty_each)


@router.post("/backtest/dca")
async def dca_post(body: DcaIn, user: User = Depends(get_current_user)) -> dict[str, Any]:
    return await _run_dca(body.symbol, body.period, body.qty_each)


async def _run_dca(symbol: str, period: str, qty_each: float) -> dict[str, Any]:
    if qty_each <= 0:
        raise HTTPException(status_code=400, detail="qty_each must be positive")
    try:
        candles = await get_market_registry().get_history(symbol, period)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    prices = [float(c["close"]) for c in candles if c.get("close") is not None]
    result = simulate_dca(prices, qty_each)
    return {
        "symbol": symbol,
        "period": period,
        "qty_each": qty_each,
        "bars": len(prices),
        **result,
        "disclaimer": "Educational stub — not a full backtester. Not financial advice.",
    }
