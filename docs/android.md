# Android APK

## For everyone (no Android Studio)

1. Run FinAgent on a PC (`START.bat`) and note the **Phone / APK** URL it prints.  
2. Download **FinAgent-android.apk** from the project’s [GitHub Releases](../../releases) page.  
3. Install on the phone (allow “unknown apps” if asked).  
4. Open the app → **Settings → Device / APK** → paste the PC URL → **Save**.

Same Wi‑Fi required. Emulator: use `http://10.0.2.2:8000`.

**Even easier:** skip the APK and open the Phone URL in Chrome → Add to Home screen (PWA).

## For developers (optional)

`BUILD-APK.bat` opens Android Studio / Gradle when you need to change native code. See [release.md](guides/release.md) for tagging releases that publish the APK automatically.

## Notes

- `frontend/android/` is local/CI-generated (gitignored).  
- Never commit keystores or `.env` files.  
- Not financial advice; paper trading by default.
