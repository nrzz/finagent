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
git clone https://github.com/YOUR_ORG/finagent.git
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

## 4. Use on your phone (same Wi‑Fi)

1. Keep **`START.bat`** running on the PC  
2. Look at the black window — it shows a **Phone / APK** address like `http://192.168.1.7:8000`  
3. On your phone’s browser, open that address  
4. Optional: browser menu → **Add to Home screen** / **Install app** (PWA — no APK needed)

---

## 5. Android APK (optional)

Only if you want a real installable app file:

1. Install [Android Studio](https://developer.android.com/studio) once (large download)
2. Keep FinAgent running with **`START.bat`**
3. Double-click **`BUILD-APK.bat`**
4. When Android Studio opens:
   - Wait for Gradle to finish
   - **Build → Build Bundle(s) / APK(s) → Build APK(s)**
   - Click **locate** and copy the `.apk` to your phone
5. Install the APK → open FinAgent → **Settings → Device / APK**  
   Set **API server URL** to the Phone address from `START.bat` (e.g. `http://192.168.1.7:8000`) → Save

More detail: [`docs/android.md`](docs/android.md)

---

## Optional — smarter local AI (Ollama)

1. Install [Ollama](https://ollama.com/download)
2. In FinAgent: **Settings → AI / LLMs**
3. Activate Ollama and set **Demo** as Fallback

---

## Stop the app

Close the `START.bat` window, or press `Ctrl+C` in it.

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
