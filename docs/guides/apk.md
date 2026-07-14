# Android APK

FinAgent ships as a Capacitor wrapper around the same React build.

## Local build

```bash
cd frontend
npm install
npm run build
npm install @capacitor/core @capacitor/cli @capacitor/android
npx cap add android
npx cap sync
npx cap open android
```

Build a debug APK in Android Studio, or:

```bash
cd android && ./gradlew assembleDebug
```

## First launch

Enter your FinAgent server URL, e.g. `http://192.168.1.10:8000` or a Tailscale IP.

## CI

Tagged releases attach mobile packaging notes; extend `.github/workflows/release.yml` with a signed keystore secret for Play-unlisted sideload APKs.
