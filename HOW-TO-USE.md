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

## Backup

**Settings → Backup** → Download backup. Store the `.db` file and your `.env` (`FINAGENT_SECRET_KEY`) together. Restore uploads the `.db` then restart FinAgent.

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
