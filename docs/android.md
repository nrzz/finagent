# Android APK (Capacitor)

FinAgent’s UI is a PWA. For a store-style Android APK, wrap `frontend/dist` with Capacitor.

## Prerequisites

- Node.js 20+
- Android Studio (SDK + platform tools)
- JDK 17
- A running FinAgent backend reachable from the phone (same Wi‑Fi LAN IP, or a reverse proxy)

## One-time setup (from `frontend/`)

```bash
cd frontend
npm install
npm run build
npx cap add android
npm run cap:sync
npx cap open android
```

In Android Studio: **Build → Build Bundle(s) / APK(s) → Build APK(s)**.

## Point the app at your server

By default the packaged app loads the built static UI and calls relative `/api` paths. For a phone on LAN:

1. Set the Capacitor `server.url` in [`frontend/capacitor.config.ts`](../frontend/capacitor.config.ts) to your PC, e.g. `http://192.168.1.10:8000`, **or**
2. Serve the built UI from the same FastAPI process (recommended for self-host): run `START.bat` / Docker and open that URL in the WebView via `server.url`.

Never commit API keys, keystores, or production `.env` files. Use a local `*.keystore` ignored by git.

## Scripts

| Script | Purpose |
|--------|---------|
| `npm run build` | Production web build |
| `npm run cap:sync` | Copy web assets into the Android project |
| `npm run cap:open` | Open Android Studio |

## Notes

- The `android/` folder is generated locally and gitignored under Capacitor paths — rebuild with `cap add` / `cap sync` on each machine.
- PWA install from Chrome remains the zero-SDK option.
- Same risk disclaimers apply on mobile: not financial advice; paper trading by default.
