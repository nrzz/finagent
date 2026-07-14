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

## Optional later

- Install [Ollama](https://ollama.com) and connect it in **Settings → AI / LLMs**
  - Recommended local: **Qwen2.5 7B** or **Llama 3.1 8B**
  - Finance fine-tune: **Plutus** (`0xroyce/plutus`) — Detect → Pull → Test → Activate
  - Models can invent numbers; FinAgent still pulls live prices from tools
- Paste cloud API keys inside the same AI Studio flow (OpenAI, Anthropic, OpenRouter, Groq) — keys are encrypted locally
- Add multiple profiles and set **Active** + **Fallback** so chat keeps working if one provider is down
- Live trading stays **off** until you deliberately enable it

## Phone on the same Wi‑Fi

On your PC note the LAN IP (e.g. `192.168.1.10`), then on your phone open:

`http://192.168.1.10:8000`

You can also **Install** the site as an app (PWA) from the browser menu.

## Android APK

See [`docs/android.md`](docs/android.md) to wrap the UI with Capacitor and build an APK (needs Android Studio).

## Stop the app

Close the `START.bat` window, or press `Ctrl+C` in it.
