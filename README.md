# FinAgent

**Self-hosted AI finance agent** for stocks, mutual funds, F&O, and crypto — with a configurable LLM (Ollama 3B → cloud), paper trading first, and a full settings UI. Zero telemetry. Apache-2.0.

> **Not financial advice.** Live trading is off by default and gated behind explicit confirmation + server-side risk limits.

[![CI](https://github.com/YOUR_ORG/finagent/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_ORG/finagent/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](backend/pyproject.toml)

## Why FinAgent?

| | Ghostfolio | OpenBB | Freqtrade | **FinAgent** |
|---|---|---|---|---|
| Portfolio tracking | Yes | Partial | No | Yes |
| AI agent with tools | No | BYO | No | **Yes** |
| Local small LLMs (Ollama) | No | Partial | No | **Yes** |
| Paper + pluggable brokers | No | No | Yes | **Yes** |
| Setup wizard / settings UI | Partial | CLI | Config files | **Full UI** |
| PWA + Android APK | PWA | No | No | **Both** |
| Zero telemetry | Yes | Varies | Yes | **Yes** |

## 5-minute quickstart (no coding)

**Windows:** double-click [`START.bat`](START.bat) → browser opens → Setup Wizard.

See [`HOW-TO-USE.md`](HOW-TO-USE.md) for the full non-technical guide.

Demo AI mode works out of the box (no Ollama/API keys). Secrets are auto-generated.

```bash
# Or Docker
docker compose up --build
# open http://localhost:8000 → Setup Wizard
```

Local (dev):

```bash
# backend
cd backend && python -m venv .venv
# Windows: .\.venv\Scripts\activate
source .venv/bin/activate
pip install -e ".[dev]"
finagent   # or: uvicorn finagent.main:app --host 0.0.0.0 --port 8000 --app-dir src

# frontend (another terminal)
cd frontend && npm install && npm run dev
```

## LLM matrix

| Tier | Examples | Notes |
|------|----------|--------|
| Demo | built-in | Zero install; tool-grounded replies |
| 3B CPU | `qwen2.5:3b`, `llama3.2:3b` | CPU-friendly; auto JSON tool mode |
| Finance local | `qwen2.5:7b`, `llama3.1:8b`, `0xroyce/plutus` | Recommended self-hosted; pull from **Settings → AI Studio** |
| Finance fine-tune | Plutus / AdaptLLM finance-chat | Domain-adapted — **prices still come from FinAgent tools** |
| Cloud | OpenAI / Anthropic / OpenRouter / Groq | Highest quality; keys encrypted on your server |

## Features

- **Chat-first agent** (Walbi-style) with quick-action chips, rich quote/portfolio cards, and inline paper-trade confirmation
- **Markets**: yfinance (global), NSE/BSE + AMFI mutual funds, ccxt crypto
- **Portfolio**: Decimal money math, FIFO P&L, XIRR, CSV import, allocation
- **Paper trading**: order state machine, market calendars, F&O helpers (lots, greeks)
- **Automation**: alerts, DCA jobs, scheduled analysis (APScheduler)
- **Broker plugins**: `BrokerAdapter` interface with live-mode safety gates
- **Access**: Web (LAN) · installable PWA · Android APK (Capacitor) — see [docs/android.md](docs/android.md)

## Risk disclaimer

**FinAgent is not financial, investment, tax, or legal advice.** It is an educational, self-hosted tool.

- Markets involve **risk of loss**, including loss of principal.
- Past performance does **not** guarantee future results.
- LLMs (including finance fine-tunes) can **hallucinate** numbers; FinAgent is designed to ground prices via tools — always verify.
- **Paper trading is the default.** Live trading is opt-in, requires re-authentication, and is at your own risk.
- You are solely responsible for any trading decisions and for compliance with laws in your jurisdiction.

## Security

- Secrets encrypted at rest (Fernet)
- JWT auth on all API routes
- Agent **cannot** change settings, enable live mode, or read keys
- Kill switch + max position / daily loss / order value limits
- Wizard requires explicit risk acknowledgment before first launch

## Docs

- [How to use (non-technical)](HOW-TO-USE.md)
- [Android APK](docs/android.md)
- [Installation](docs/guides/installation.md)
- [Remote access](docs/guides/remote-access.md)
- [Broker plugins](docs/guides/broker-plugins.md)
- [ADRs](docs/adr/)
- [Contributing](CONTRIBUTING.md)
- [Security policy](SECURITY.md)

## License

Apache License 2.0 — see [LICENSE](LICENSE).
