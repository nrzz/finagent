/**
 * Capacitor entry: on native builds, allow configuring API base URL.
 * Web builds use same-origin / relative /api paths.
 */
const STORAGE_KEY = "finagent_server_url";

export function getApiBase(): string {
  if (typeof window === "undefined") return "";
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) return saved.replace(/\/$/, "");
  // Capacitor native: default empty until user sets it
  const w = window as Window & { Capacitor?: { isNativePlatform?: () => boolean } };
  if (w.Capacitor?.isNativePlatform?.()) return "";
  return "";
}

export function setApiBase(url: string) {
  localStorage.setItem(STORAGE_KEY, url.replace(/\/$/, ""));
}
