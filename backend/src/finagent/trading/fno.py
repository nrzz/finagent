"""F&O helpers: lot sizes, expiry, simplified greeks."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from finagent.portfolio.money import D, quantize

# Illustrative NSE lot sizes — configurable / overridable in production feeds.
DEFAULT_LOTS: dict[str, int] = {
    "NIFTY": 25,
    "BANKNIFTY": 15,
    "FINNIFTY": 25,
    "MIDCPNIFTY": 50,
    "SENSEX": 10,
}


@dataclass
class OptionContract:
    underlying: str
    expiry: date
    strike: Decimal
    option_type: str  # CE | PE
    lot_size: int
    premium: Decimal | None = None


def lot_size(underlying: str) -> int:
    return DEFAULT_LOTS.get(underlying.upper(), 1)


def is_expired(expiry: date, today: date | None = None) -> bool:
    today = today or date.today()
    return expiry < today


def estimate_margin(
    premium: Decimal, lot: int, quantity_lots: int = 1, multiplier: Decimal = D("1")
) -> Decimal:
    """Rough margin estimate for paper trading (not a substitute for exchange SPAN)."""
    notional = premium * D(lot) * D(quantity_lots) * multiplier
    return quantize(notional * D("0.20"))  # 20% illustrative


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


@dataclass
class Greeks:
    delta: float
    gamma: float
    theta: float
    vega: float
    iv: float


def black_scholes_greeks(
    spot: float,
    strike: float,
    t_years: float,
    rate: float,
    iv: float,
    option_type: str = "CE",
) -> Greeks:
    """Black-Scholes greeks for paper analysis."""
    if t_years <= 0 or iv <= 0 or spot <= 0 or strike <= 0:
        return Greeks(delta=0.0, gamma=0.0, theta=0.0, vega=0.0, iv=iv)
    sqrt_t = math.sqrt(t_years)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * sqrt_t)
    d2 = d1 - iv * sqrt_t
    pdf = _norm_pdf(d1)
    if option_type.upper() in {"CE", "CALL", "C"}:
        delta = _norm_cdf(d1)
        theta = (
            -(spot * pdf * iv) / (2 * sqrt_t)
            - rate * strike * math.exp(-rate * t_years) * _norm_cdf(d2)
        ) / 365.0
    else:
        delta = _norm_cdf(d1) - 1.0
        theta = (
            -(spot * pdf * iv) / (2 * sqrt_t)
            + rate * strike * math.exp(-rate * t_years) * _norm_cdf(-d2)
        ) / 365.0
    gamma = pdf / (spot * iv * sqrt_t)
    vega = spot * pdf * sqrt_t / 100.0
    return Greeks(delta=delta, gamma=gamma, theta=theta, vega=vega, iv=iv)
