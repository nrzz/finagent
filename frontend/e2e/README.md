# FinAgent UI E2E (Playwright)

## Run

```bash
cd frontend
npm run build
npx playwright test
```

Screenshots are written to `e2e/artifacts/*.png` (gitignored). HTML report: `e2e/playwright-report/`.

## Coverage

| Project | What |
|--------|------|
| **desktop** | Auth edges, wizard (short password / risk ack), chat quote + cancel/confirm paper, dashboard, portfolio (holding/XIRR/split), markets invalid+valid, trading buy/oversell/reset, F&O greeks+paper, automation alerts/jobs, all Settings tabs (incl. Device/APK + kill switch), command palette, sign-out/bad login, unknown route |
| **mobile-apk** | Pixel 5 viewport — all pages via routes + bottom nav, Device/APK server URL (`10.0.2.2`), paper trade, safe-area nav |

## APK

Mobile project simulates Capacitor WebView size. Real APK: `npm run cap:sync` then Android Studio build (see `docs/android.md`). Set **Settings → Device / APK → API server URL** on device.
