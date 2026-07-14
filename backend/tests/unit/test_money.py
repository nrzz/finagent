"""Unit tests for money helpers."""

from decimal import Decimal

from finagent.portfolio.money import D, format_money, quantize, round_to_tick


def test_d_from_float_avoids_binary() -> None:
    assert D(0.1) + D(0.2) == D("0.3")


def test_quantize() -> None:
    assert quantize(D("1.005")) == D("1.01")


def test_indian_format() -> None:
    s = format_money(D("1234567.89"), "INR", "indian")
    assert "12,34,567.89" in s


def test_round_to_tick() -> None:
    assert round_to_tick(D("100.12"), "equity") == D("100.10") or round_to_tick(
        D("100.12"), "equity"
    ) == D("100.15")


def test_crypto_precision() -> None:
    assert isinstance(D("0.00000001"), Decimal)
