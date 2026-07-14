# How to use FinAgent (no coding)

## Windows (easiest)

1. Double-click **`START.bat`**
2. Wait until it says the app is running
3. Your browser opens to **http://127.0.0.1:8000**
4. Follow the **Setup Wizard** on screen:
   - Create a username/password
   - Leave **Demo (easiest)** selected for AI (works with no install), or connect Ollama / a cloud key in AI Studio
   - Click through markets → **check the risk acknowledgment** → Launch

That’s it. You never need to edit `.env` or any config file. The home screen is the **Agent chat** (quick chips for quotes, portfolio, paper trades).

## Risk disclaimer (read this)

FinAgent is an **educational tool**, not financial advice. Markets involve risk of loss. Paper trading is on by default. Live trading stays locked until you deliberately enable it in Settings (with re-auth). You are responsible for your own decisions.

## Optional later — local AI (Ollama)

1. Install [Ollama](https://ollama.com/download) (Windows / Mac / Linux).
2. Open **Settings → AI / LLMs**. If Ollama is running, the **Ollama** card shows **Detected · N models** automatically.
3. Click Ollama → pick an installed model (or **Pull** `qwen2.5:3b` / `qwen2.5:7b` / `0xroyce/plutus`) → **Test** → **Save & activate**.
4. Chat uses the live local model; numbers still come from FinAgent tools (models can invent prices otherwise).

Also supported: cloud keys (OpenAI, Anthropic, OpenRouter, Groq) in the same AI Studio — encrypted locally. Set **Active** + **Fallback** so chat keeps working if one provider is down.

## Phone on the same Wi‑Fi

On your PC note the LAN IP (e.g. `192.168.1.10`), then on your phone open:

`http://192.168.1.10:8000`

You can also **Install** the site as an app (PWA) from the browser menu.

## Android APK

See [`docs/android.md`](docs/android.md) to wrap the UI with Capacitor and build an APK (needs Android Studio).

## Markets & paper trading

- **Chat** home: ask for quotes, portfolio, or paper trades (Confirm/Cancel before fills).
- **F&O**: option chain, illustrative greeks/margin, paper option tickets. Expired paper options are square-off’d by a daily job.
- **Automation**: price alerts, DCA paper buys, scheduled analysis — stored in the DB; in-app notification feed (no Telegram required).
- **Portfolio**: holdings, CSV import, XIRR cashflows, stock splits, benchmark history.
- **Brokers** (Settings): save Zerodha / Angel / Alpaca keys encrypted. Status stays **paper only until Live** is enabled. Live mode needs re-auth; stubs still refuse real fills in this release.

## AI models

Default **Active = Demo** (works offline). Optional **Ollama** as Active with **Demo as Fallback** so chat keeps working if the local model is down. Cloud keys work the same way in AI Studio.

## Stop the app

Close the `START.bat` window, or press `Ctrl+C` in it.
