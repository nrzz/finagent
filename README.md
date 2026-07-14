# FinAgent

**Self-hosted AI finance helper** for stocks, mutual funds, F&O, and crypto.  
Chat-first · paper trading by default · your data stays on your computer · Apache-2.0.

> **Not financial advice.** Live trading is off until you deliberately enable it.

---

## Start in 3 steps (no coding)

1. **Install once:** [Python 3.11+](https://www.python.org/downloads/) *(check “Add to PATH”)* and [Node.js LTS](https://nodejs.org/)
2. **Download** this repo (GitHub → **Code → Download ZIP**) and unzip it
3. **Double-click `START.bat`** → browser opens → Setup Wizard → Launch

Full beginner guide: **[HOW-TO-USE.md](HOW-TO-USE.md)**

| Want… | Do this |
|-------|---------|
| Website on this PC | `START.bat` → http://127.0.0.1:8000 |
| Phone (same Wi‑Fi) | Use the **Phone / APK** URL printed by `START.bat` |
| Android APK | `BUILD-APK.bat` (needs [Android Studio](https://developer.android.com/studio)) |

Docker: `docker compose up --build` → http://localhost:8000

---

## What you get

- **Agent chat** with quick chips (quotes, portfolio, paper trades)
- **Demo AI** works with zero setup; optional Ollama / cloud keys in Settings
- **Paper trading**, F&O paper tickets, portfolio XIRR, automation alerts
- **PWA** + optional **Android APK** (Capacitor)
- **Zero telemetry** — secrets encrypted on your machine

---

## Docs

| Guide | For |
|-------|-----|
| [HOW-TO-USE.md](HOW-TO-USE.md) | Non-technical setup |
| [docs/android.md](docs/android.md) | APK details |
| [docs/guides/installation.md](docs/guides/installation.md) | Advanced / Linux / Docker |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Developers |

---

## Risk disclaimer

FinAgent is an **educational** tool — not financial, investment, tax, or legal advice. Markets involve risk of loss. Paper trading is the default. You are solely responsible for your decisions.

## License

Apache License 2.0 — see [LICENSE](LICENSE).
