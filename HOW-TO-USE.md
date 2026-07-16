# FinAgent — easy start (no tech background needed)

**FinAgent is an educational tool — not financial advice.** Paper trading is on by default.

---

## 1. Get the app onto your computer

### Option A — Download ZIP (easiest)

1. Open the FinAgent page on GitHub
2. Click the green **Code** button → **Download ZIP**
3. Unzip the folder somewhere simple, e.g. `Documents\finagent`

### Option B — Git clone

If you have Git installed:

```text
git clone https://github.com/nrzz/finagent.git
```

(Replace with the real repo URL when published.)

---

## 2. Install two free programs (one-time)

| Program | Download | Tip |
|---------|----------|-----|
| **Python 3.11+** | https://www.python.org/downloads/ | On the installer, check **“Add python.exe to PATH”** |
| **Node.js LTS** | https://nodejs.org/ | Use the big **LTS** button |

Restart your PC once after installing (helps PATH updates).

---

## 3. Start FinAgent

1. Open the `finagent` folder
2. Double-click **`START.bat`**
3. Wait (first run downloads packages — can take a few minutes)
4. Your browser opens to **http://127.0.0.1:8000**

### Setup Wizard (first visit only)

1. Create a username + password (saved only on your PC)
2. Leave **Demo** selected for AI (works with no extra install)
3. Click through markets → check the **risk** box → **Launch FinAgent**

Home screen = **Agent chat**. Try chips like “Paper-buy 10 AAPL”.

---

## Trading Desk

Open **Trade** in the sidebar (or Portfolio → **Open desk**). One desk covers:

| Mode | Use for |
|------|---------|
| **Equity** | Stocks / ETFs — chart + order ticket |
| **F&O** | Options chain, educational greeks/margin, paper options |
| **Crypto** | Spot pairs (e.g. `BTC/USDT`) |

- Chart timeframes: switch intervals on the candle chart (1m → daily).
- Keyboard: **B** / **S** set buy/sell side; **/** focuses the symbol field.
- Quotes are **free delayed data** (yfinance / ccxt) — not a live broker feed. Fills from a connected broker may not match the delayed LTP you see on screen.

---

## 4. Use on your phone (same Wi‑Fi)

1. Keep **`START.bat`** running on the PC  
2. Look at the black window — it shows a **Phone / APK** address like `http://192.168.1.7:8000`  
3. On your phone’s browser, open that address  
4. Optional: browser menu → **Add to Home screen** / **Install app** (PWA — no APK needed)

---

## 5. Android APK (optional — no Android Studio)

Most people should use the **phone browser** (section 4) or **Add to Home screen**.

If you want an installable APK:

1. Keep **`START.bat`** running on the PC and copy the **Phone / APK** URL it shows  
2. On GitHub, open **Releases** and download **`FinAgent-android.apk`**  
   (published automatically when maintainers tag a version — see `docs/guides/release.md`)  
3. Install the APK on your phone  
4. Open FinAgent → **Settings → Device / APK** → paste the PC URL → **Save**

You do **not** need Android Studio for this.

(Developers only: `BUILD-APK.bat` builds from source.)

---

## Optional — smarter local AI (Ollama)

1. Install [Ollama](https://ollama.com/download) (one-time)
2. In FinAgent: **Settings → AI / LLMs → Ollama**
3. Click a model once — FinAgent **downloads + activates** it (and keeps **Demo** as Fallback)

| Tier | Examples | Rough hardware |
|------|----------|----------------|
| Fast | 3B | 4–8 GB RAM |
| Balanced | 7B / 8B | 8–16 GB |
| Quality | 14B–27B | 12–24 GB VRAM |
| High-end | 32B | 24–48 GB |
| Flagship | 70B / 72B | 48 GB+ |
| Extreme | 405B | Multi-GPU / server |

Leave the tab open during big downloads. If chat feels wrong, set Active back to **Demo**.

---

## Connect a broker (Zerodha / Angel / Alpaca) — click path

1. **Settings → Brokers**
2. Type your FinAgent password at the top (needed to save keys)
3. Pick **Alpaca**, **Zerodha**, or **Angel**
4. Follow the numbered steps on screen → paste keys → **Save secret**
5. **Test connection** until it says Connected (Zerodha: Open Kite login → Exchange token; Angel: Login to Angel)
6. **Settings → Trading** → set **Default live broker** → keep mode **Paper** until you are ready
7. Optional: **Sync holdings** to pull positions into Portfolio

Live money: **Settings → Trading → Live** (password required). Use header **Panic Stop** to block all orders instantly.

---

## Get alerts on Telegram / Email / Discord (click path)

1. **Settings → Notifications**
2. Turn on **Send alerts outside this app**
3. Open **Telegram** (or Email / Discord / Slack / Webhook)
4. Paste credentials → **Save** → **Test send**
5. Price alerts still appear under **Auto**; external channels only fire after a successful Test

Web Push: **Generate VAPID keys**, then allow notifications in the browser/PWA.

---

## Backup

**Settings → Backup** → Download backup. Store the `.db` file and your `.env` (`FINAGENT_SECRET_KEY`) together. Restore uploads the `.db` then restart FinAgent.

---

## Stop the app

Close the `START.bat` window, or press `Ctrl+C` in it.

---

## Keep FinAgent running (Windows service / Docker)

Price alerts and DCA jobs only fire while FinAgent is running.

- **Simple:** leave `START.bat` open on your PC
- **Windows (optional):** run FinAgent in the background with [NSSM](https://nssm.cc/) or Task Scheduler (start at login)
- **Docker (recommended for always-on):** `docker compose up -d` — restarts automatically (`restart: unless-stopped`) and health-checks `/api/health/ready`
- Open **Auto** anytime to see in-app notifications; external channels need **Settings → Notifications** tested once

---

## If something goes wrong

| Problem | Fix |
|---------|-----|
| “Python was not found” | Reinstall Python with **Add to PATH**, restart PC |
| “Node was not found” | Install Node LTS, restart PC |
| Phone can’t open the site | Same Wi‑Fi; allow port **8000** in Windows Firewall; use the IP from `START.bat` |
| Page won’t load on PC | Wait until `START.bat` finishes starting; try http://127.0.0.1:8000 again |
| Forgot password | Delete the `data` folder inside finagent (resets the app — you’ll set up again) |

---

## Risk reminder

FinAgent is **not** financial advice. Markets involve risk of loss. Live trading stays locked until you turn it on in Settings (with re-auth). You are responsible for your own decisions.
