# Broker plugins

Implement `BrokerAdapter` (`backend/src/finagent/brokers/base.py`):

```python
class MyBroker(BrokerAdapter):
    name = "mybroker"
    supports_live = True

    async def get_holdings(self): ...
    async def place_order(self, request): ...
    async def cancel_order(self, order_id): ...
```

Register:

```python
from finagent.brokers import get_broker_registry
get_broker_registry().register(MyBroker())
```

## Safety gates (enforced by `BrokerRegistry.place_order_safe`)

1. `trading.kill_switch` must be false
2. Live mode only if `trading.mode == live`
3. Live adapters only (`supports_live`)
4. `confirmed=True` when `require_order_confirmation` is set

Paper mode always routes to the built-in paper broker.
