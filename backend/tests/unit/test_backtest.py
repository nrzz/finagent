"""Unit tests for DCA backtest foundation."""

from finagent.backtest import simulate_dca


def test_simulate_dca_basic() -> None:
    # Buy 1 unit at 10, 20, 30 → invested 60, final at 30 = 90, return 0.5
    out = simulate_dca([10.0, 20.0, 30.0], qty_each=1.0)
    assert out["invested"] == 60.0
    assert out["final_value"] == 90.0
    assert abs(out["simple_return"] - 0.5) < 1e-9


def test_simulate_dca_qty() -> None:
    out = simulate_dca([100.0, 100.0], qty_each=2.0)
    assert out["invested"] == 400.0
    assert out["final_value"] == 400.0
    assert out["simple_return"] == 0.0


def test_simulate_dca_empty() -> None:
    assert simulate_dca([], 1.0) == {
        "final_value": 0.0,
        "invested": 0.0,
        "simple_return": 0.0,
    }
    assert simulate_dca([10.0], 0.0)["invested"] == 0.0


def test_simulate_dca_skips_non_positive() -> None:
    out = simulate_dca([0.0, -5.0, 10.0], qty_each=1.0)
    assert out["invested"] == 10.0
    assert out["final_value"] == 10.0
