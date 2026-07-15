# Broker plugins

Implement `BrokerAdapter` (`backend/src/finagent/brokers/base.py`):

```python
class MyBroker(BrokerAdapter):
    name = "mybroker"
    supports_live = True
    display_name = "My Broker"
    secret_names = ["MY_API_KEY", "MY_API_SECRET"]

    async def healthcheck(self): ...
    async def get_holdings(self): ...
    async def place_order(self, request): ...
    async def cancel_order(self, order_id): ...
```

Register in `BrokerRegistry.__init__` (`backend/src/finagent/brokers/registry.py`).

## Built-in adapters

| Broker | Module | Notes |
|--------|--------|-------|
| paper | `registry.PaperBrokerAdapter` | Default practice book |
| zerodha | `brokers/zerodha.py` | Kite Connect — login URL + request_token exchange |
| angel | `brokers/angel.py` | SmartAPI — TOTP login |
| alpaca | `brokers/alpaca.py` | Paper + live HTTP API |

## Safety gates (enforced by `BrokerRegistry.place_order_safe`)

1. `trading.kill_switch` must be false (Panic Stop sets it true)
2. Live mode only if `trading.mode == live`
3. Live uses **only** `trading.default_broker`
4. Live always requires `confirmed=True`
5. Paper confirmation follows `require_order_confirmation`
6. Optional `paper_backend=alpaca` routes paper orders to Alpaca paper API

## Beginner UI

**Settings → Brokers** guided Connect wizards store secrets with password re-auth and offer **Test connection** / **Sync holdings**.
