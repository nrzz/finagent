# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Paper-complete product surface: persisted paper book & automation, F&O page, portfolio XIRR/corp actions/benchmarks, brokers UI (live gated)
- Playwright A–Z + mobile/APK viewport e2e with screenshots
- Beginner one-click flow: `START.bat`, `BUILD-APK.bat`, simplified `HOW-TO-USE.md` / `README.md`
- GitHub Release workflow builds and attaches **FinAgent-android.apk** (no Android Studio for end users)
- Settings → Device / APK server URL for Capacitor phones

### Changed

- End-user APK path is GitHub Releases download, not local Android Studio
- Mobile nav includes all pages; Demo LLM fallback hardened

## [0.1.0] — 2026-07-14

### Added

- Initial public release: FastAPI backend, React UI, setup wizard, OpenAI-compatible LLM router (httpx)
- Market data adapters: yfinance, India/AMFI, ccxt
- Paper trading engine, portfolio Decimal/FIFO/XIRR math
- Automation (alerts, DCA, scheduled analysis)
- BrokerAdapter plugin interface with live-mode safety gates
- PWA + Capacitor Android packaging docs/CI
- Docker Compose, MkDocs docs, ADRs

[Unreleased]: https://github.com/YOUR_ORG/finagent/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/YOUR_ORG/finagent/releases/tag/v0.1.0
