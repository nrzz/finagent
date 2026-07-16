# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Trading Desk** unified UX: Equity / F&O / Crypto modes, candle chart, dense order ticket, watchlist, blotter, B/S keyboard shortcuts
- Batch market quotes (`GET /api/market/quotes`) and SSE quote stream (`GET /api/market/stream`)
- Dashboard watch strip (delayed free quotes) and Portfolio / position **Trade** deep-links to the desk
- Order ticket **Alert on symbol** → Automation; Settings note that quotes may lag live fills

### Changed

- Nav label **Trade** (replaces separate Markets page flow); F&O lives under `/trading?mode=fno`
- Playwright A–Z desk smoke (tests 05–07) and mobile nav paths

## [0.2.0] — 2026-07-15

### Added

- Live broker adapters: Zerodha, Angel One, Alpaca + Settings Connect wizards
- Notification dispatcher: Telegram, Email, Webhook, Web Push, Discord, Slack (quiet hours / mutes / event filters)
- Panic Stop, reauth gates for secrets / live mode / kill-switch off
- Log redaction for secrets; webhook URL SSRF guards
- Docker `HEALTHCHECK` on `/api/health/ready` + `restart: unless-stopped`; always-on docs
- Agent steward tools (read-only): broker health, watchlist CRUD, alerts/jobs, explain last error
- Live trading blotter + cancel; Automation job toggle/delete; watchlist delete
- React ErrorBoundary; frontend vitest for notify helpers + API 401
- F&O educational margin labels + options chain table foundations
- Backtest foundation: `simulate_dca` + `/api/backtest/dca`
- ADR 0005 multi-user households; Tauri desktop guide + placeholder
- `PROJECT.md` PM charter (backlog, risk, releases, DoD)
- Mocked httpx unit tests for Zerodha / Angel / Alpaca

### Changed

- Auth tokens via **PyJWT** (replaces python-jose / ecdsa)
- Chat SSE always emits `error` then `done` on LLM failures
- Market history/options error handling; cache stale flag; registry pick without full rebuild
- Broker holdings HTTP errors surface as errors (not empty books)
- Angel live orders gated until `symbol_token` resolvable; Zerodha session-expiry UX
- Coverage fail-under 50%; pip-audit documents setuptools ignore for ccxt pin
- Ruff clean on CI (B008/N802 policy; e2e E402)

### Security

- Paper remains default; agent cannot enable live or set `confirmed`
- Reauth required for secrets, live mode, and disabling kill switch

## [0.1.0] — 2026-07-14

### Added

- Initial public release: FastAPI backend, React UI, setup wizard, OpenAI-compatible LLM router (httpx)
- Market data adapters: yfinance, India/AMFI, ccxt
- Paper trading engine, portfolio Decimal/FIFO/XIRR math
- Automation (alerts, DCA, scheduled analysis)
- BrokerAdapter plugin interface with live-mode safety gates
- PWA + Capacitor Android packaging docs/CI
- Docker Compose, MkDocs docs, ADRs
- Paper-complete product surface: F&O page, portfolio XIRR/corp actions/benchmarks
- Playwright A–Z + mobile/APK viewport e2e
- Beginner one-click flow: `START.bat`, `BUILD-APK.bat`
- GitHub Release workflow builds FinAgent-android.apk
- Settings → Device / APK server URL for Capacitor phones

[Unreleased]: https://github.com/nrzz/finagent/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/nrzz/finagent/releases/tag/v0.2.0
[0.1.0]: https://github.com/nrzz/finagent/releases/tag/v0.1.0
