import type { CapacitorConfig } from "@capacitor/cli";

/**
 * Capacitor config for FinAgent Android/iOS wrappers.
 * For LAN use, set server.url to your FinAgent host (e.g. http://192.168.1.10:8000).
 * Leave server.url unset to load bundled static assets from `dist/`.
 */
const config: CapacitorConfig = {
  appId: "app.finagent.selfhosted",
  appName: "FinAgent",
  webDir: "dist",
  server: {
    androidScheme: "https",
    // Uncomment and set your LAN URL when wrapping a remote self-hosted instance:
    // url: "http://192.168.1.10:8000",
    cleartext: true,
  },
  plugins: {
    SplashScreen: {
      launchShowDuration: 800,
      backgroundColor: "#0b1220",
    },
  },
};

export default config;
