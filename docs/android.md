# Android APK — simple steps

You do **not** need an APK to use FinAgent on a phone. Same Wi‑Fi + browser is enough (see [HOW-TO-USE.md](../HOW-TO-USE.md)).

Use an APK only if you want a home-screen app icon from an installable file.

## Before you start

1. FinAgent is running on your PC (`START.bat`) — note the **Phone / APK** URL it prints  
2. [Android Studio](https://developer.android.com/studio) is installed (large one-time download)  
3. Phone and PC are on the **same Wi‑Fi**

## Build the APK (Windows)

1. Double-click **`BUILD-APK.bat`** in the FinAgent folder  
2. Wait for Android Studio to open and Gradle to finish  
3. Menu: **Build → Build Bundle(s) / APK(s) → Build APK(s)**  
4. Click **locate** → copy the `.apk` to your phone → install  
5. Open FinAgent → **Settings → Device / APK** → set **API server URL** to your PC address from `START.bat`  
   Example: `http://192.168.1.7:8000` → **Save server URL**

**Android emulator:** use `http://10.0.2.2:8000` as the server URL.

## Manual commands (developers)

```bash
cd frontend
npm install
npm run build
npx cap add android   # first time only
npx cap sync
npx cap open android
```

## Notes

- The `frontend/android/` folder is local (gitignored). `BUILD-APK.bat` / `cap add` creates it when needed.  
- Never commit keystores, API keys, or `.env` files.  
- Same risk rules as the website: not financial advice; paper trading by default.
