"""Config schema tests."""

from finagent.config.schema import AppSettings, TradingMode


def test_defaults() -> None:
    s = AppSettings()
    assert s.llm.provider.value == "demo"
    assert s.trading.mode == TradingMode.PAPER
    assert s.setup_complete is False


def test_validate_risk() -> None:
    s = AppSettings.model_validate(
        {
            "trading": {
                "risk": {"max_position_pct": 5, "max_daily_loss_pct": 2, "max_order_value": 50000}
            }
        }
    )
    assert s.trading.risk.max_position_pct == 5


def test_public_dict() -> None:
    d = AppSettings().public_dict()
    assert "llm" in d
    assert "trading" in d
