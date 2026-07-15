"""Decimal money helpers — never use float for prices/quantities/P&L."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation, getcontext

getcontext().prec = 28

Money = Decimal


def D(value: str | int | float | Decimal) -> Decimal:
    """Parse to Decimal safely (floats go through str to avoid binary artifacts)."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, float):
        return Decimal(str(value))
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid decimal value: {value!r}") from exc


def quantize(value: Decimal, places: int = 2) -> Decimal:
    q = Decimal(10) ** -places
    return value.quantize(q, rounding=ROUND_HALF_UP)


def quantize_qty(value: Decimal, places: int = 8) -> Decimal:
    return quantize(value, places)


def format_money(value: Decimal, currency: str = "INR", number_format: str = "indian") -> str:
    q = quantize(value, 2)
    s = _indian_group(f"{q:.2f}") if number_format == "indian" else f"{q:,.2f}"
    return f"{currency} {s}"


def _indian_group(amount: str) -> str:
    neg = amount.startswith("-")
    if neg:
        amount = amount[1:]
    if "." in amount:
        whole, frac = amount.split(".", 1)
    else:
        whole, frac = amount, "00"
    if len(whole) <= 3:
        grouped = whole
    else:
        last3 = whole[-3:]
        rest = whole[:-3]
        parts: list[str] = []
        while rest:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        grouped = ",".join([*parts, last3])
    out = f"{grouped}.{frac}"
    return f"-{out}" if neg else out


TICK_SIZES: dict[str, Decimal] = {
    "equity": D("0.05"),
    "crypto": D("0.00000001"),
    "option": D("0.05"),
    "mutual_fund": D("0.0001"),
}


def round_to_tick(price: Decimal, asset_class: str = "equity") -> Decimal:
    tick = TICK_SIZES.get(asset_class, D("0.01"))
    if tick <= 0:
        return price
    return (price / tick).to_integral_value(rounding=ROUND_HALF_UP) * tick
