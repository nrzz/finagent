# Contributing to FinAgent

Thanks for helping build a trustworthy self-hosted finance agent.

## Development setup

```bash
# Backend
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .\.venv\Scripts\activate
pip install -e ".[dev]"
pre-commit install

# Frontend
cd frontend
npm install
```

## Checks before PR

```bash
cd backend
ruff check src tests
ruff format --check src tests
mypy src/finagent
pytest --cov=finagent --cov-fail-under=70

cd frontend
npm run typecheck
npm run test
npm run build
```

## Conventions

- Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`)
- Decimal math for all money — never `float` for prices/P&L
- Agent tools must not mutate settings, enable live trading, or expose secrets
- New market/broker integrations implement the adapter interfaces in `data/base.py` and `brokers/base.py`
- UI copy: always note **not financial advice** where investment decisions appear

## Adding a broker plugin

1. Subclass `BrokerAdapter` in `backend/src/finagent/brokers/`
2. Set `supports_live = True` only if real orders are implemented
3. Register via `get_broker_registry().register(...)`
4. Document credentials in Settings UI + docs/guides/broker-plugins.md
5. Add unit tests with mocked HTTP

## Code of conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).