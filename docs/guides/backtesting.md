# Backtesting (foundation)

Educational stub only — not a full strategy workspace.

## DCA simulator

Pure function in `finagent.backtest`:

```python
from finagent.backtest import simulate_dca

simulate_dca(prices=[10.0, 20.0, 30.0], qty_each=1.0)
# → final_value, invested, simple_return
```

Buys a fixed quantity at each bar’s price; marks final value at the last price.

## HTTP stub

Authenticated endpoints:

- `GET /api/backtest/dca?symbol=AAPL&period=6mo&qty_each=1`
- `POST /api/backtest/dca` with JSON `{ "symbol", "period", "qty_each" }`

Fetches market history via the existing registry, runs `simulate_dca` on close prices, returns bars + metrics + disclaimer.

## What’s next (roadmap)

- Multi-asset portfolios, fees/slippage, strategy YAML
- UI workspace and walk-forward / report export

Not financial advice.
