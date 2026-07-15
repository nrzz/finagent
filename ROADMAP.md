# Roadmap

## v0.1 — Foundation (current)

- [x] Setup wizard + settings UI
- [x] Configurable LLM (Ollama → cloud)
- [x] Market adapters (global / India+MF / crypto)
- [x] Paper trading + portfolio
- [x] PWA + APK packaging pipeline
- [x] Docker Compose

## v0.2 — Brokers, notifications, security UX (shipped in uplift)

- [x] Zerodha / Angel / Alpaca live adapters + Connect wizards
- [x] Notification channels (Telegram / Email / Webhook / Web Push / Discord / Slack)
- [x] Beginner Settings (all knobs in UI) + Panic Stop + Audit
- [ ] Richer F&O chain UI + SPAN-class margin — *in progress: educational margin labels + chain table / empty-state (foundations 0.2.x); full SPAN still later*
- [ ] Multi-user households with roles — *unchecked; foundations landed 0.2.x (ADR 0005 documents `is_admin`, future owner/member)*

## v0.3

- [ ] Tauri desktop app — *unchecked; foundations landed 0.2.x (guide + `frontend/src-tauri` placeholder)*
- [x] Tax lot CSV export (lite)
- [ ] Backtesting workspace — *unchecked; foundations landed 0.2.x (`simulate_dca` + `/api/backtest/dca` stub)*
- [ ] Strategy marketplace (community YAML)
