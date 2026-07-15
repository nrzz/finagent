# FinAgent — Project Manager charter

**Owner:** Cursor agent (core PM)  
**Product:** Self-hosted AI finance agent — paper-first, zero telemetry  
**Repo:** https://github.com/nrzz/finagent

This file is the living source of truth for backlog, risk, releases, and decisions. Update it in the same change that moves work.

---

## Decision authority

| I decide without asking | I ask the human first |
|-------------------------|------------------------|
| Refactors, bug fixes, tests, docs | Spending money |
| Dependency patches / security bumps | Enabling live trading as default |
| UX copy, Settings labels | Deleting user data |
| Patch / minor release timing | Force-push / history rewrite |
| CI policy (lint, audit allowlists with expiry) | Major framework upgrades that change UX (React/Vite majors) |
| | Publishing to app stores |

---

## Definition of done (every item)

1. Code + tests + docs in one change  
2. Backend pytest green, frontend typecheck+build green, ruff clean  
3. Playwright desktop smoke if UI-facing  
4. Security invariants preserved (paper default; agent cannot go live/confirm; reauth on secrets/live/kill-off)  
5. Commit with clear message; this file’s backlog/status updated  

---

## Cadence

Each session: health → top backlog item → quality gates → update this file → 3-line status (shipped / next / blockers).

---

## Backlog

### P0 — Release / reliability

| ID | Item | Status |
|----|------|--------|
| R0 | Release 0.2.0 — land uplift, green CI, tag | done (2026-07-15) |
| R1 | Docker HEALTHCHECK + restart; scheduler-aware ready; always-on docs | done |
| R2 | Agent/chat LLM error + SSE `error`/`done` | done |
| R3 | Market history/options errors; cache stale semantics; registry rebuild | done |
| R4 | Broker honesty + Angel token gate + mocked adapter tests | done |

### P1 — UX / agent operator

| ID | Item | Status |
|----|------|--------|
| U1 | Settings quiet hours / mutes / events; humanize notify tests | done |
| U2 | Watchlist delete; empty states; ErrorBoundary | done |
| U3 | Live blotter + cancel; Automation job disable/delete | done |
| A1 | Read-only steward tools (broker health, watchlist, jobs, last error) | done |
| A2 | Frontend unit tests for notify + API 401 | done |

### P2 — Roadmap bets

| ID | Item | Status |
|----|------|--------|
| F1 | Richer F&O chain + honest margin | foundations in 0.2.0; SPAN later |
| M1 | Multi-user households + roles | ADR 0005 landed; schema later |
| T1 | Tauri desktop | guide + placeholder; full app later |
| B1 | Backtesting + strategy YAML | DCA stub in 0.2.0; workspace later |

### Next after 0.2.0

| ID | Item | Priority |
|----|------|----------|
| N1 | Confirm CI green on main post-push; triage any flake | done — e2e project name fixed (`desktop`) |
| N2 | yfinance backoff / circuit breaker under alert scan | P1 |
| N3 | Playwright regression after Settings/Trading UX | P1 |
| N4 | SPAN-class F&O margin or remove illustrative fallbacks | P2 |

---

## Risk register

| Risk | Severity | Mitigation | Status |
|------|----------|------------|--------|
| Red CI on main blocks shipping | High | Fixed ruff + PyJWT + pip-audit policy in 0.2.0 | mitigated |
| Live broker bug loses money | High | Mocked tests, confirm gates, paper default, Panic Stop | open |
| Scheduler dies with console | Medium | Docker restart + healthcheck; docs | mitigated |
| yfinance rate-limits under alerts | Medium | Backoff / circuit breaker (N2) | open |
| Dependabot majors break build | Medium | Batch + manual review | open |
| Secret leakage via logs/git | High | log_redact + gitignore; regression tests | mitigated |

---

## Release log

| Version | Date | Notes |
|---------|------|-------|
| 0.1.x | 2026-07 | Foundation: paper, chat, PWA/APK, Docker |
| 0.2.0 | 2026-07-15 | Live brokers, notifications, reliability, steward tools, Sprint 4 foundations |

---

## Decision log

| Date | Decision |
|------|----------|
| 2026-07-15 | Human appointed agent as core PM; paper stays default; live gated |
| 2026-07-15 | Full live brokers (Zerodha/Angel/Alpaca) + all notify channels in product scope |
| 2026-07-15 | pip-audit: time-boxed ignore PYSEC-2026-3447 (setuptools via ccxt pin) |
| 2026-07-15 | Replace python-jose with PyJWT for CVE hygiene |
