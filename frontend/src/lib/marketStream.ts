import { getToken } from "@/lib/api";
import { getApiBase } from "@/lib/native";

export type QuoteDict = {
  symbol: string;
  price?: string;
  change_pct?: string | null;
  stale?: boolean;
  source?: string;
  age_seconds?: number;
  bid?: string | null;
  ask?: string | null;
  currency?: string;
  error?: string;
  as_of?: string;
};

/** Split a comma-separated symbols query into trimmed unique entries. */
export function parseSymbolsParam(s: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const part of s.split(",")) {
    const sym = part.trim();
    if (!sym || seen.has(sym)) continue;
    seen.add(sym);
    out.push(sym);
  }
  return out;
}

/** Backoff delays: 1s, 2s, then 5s max. */
export function nextBackoffMs(attempt: number): number {
  const delays = [1000, 2000, 5000];
  return delays[Math.min(Math.max(0, attempt), delays.length - 1)];
}

function extractQuotes(payload: unknown): QuoteDict[] | null {
  if (!payload || typeof payload !== "object") return null;
  const obj = payload as { quotes?: unknown; type?: string };
  if (Array.isArray(obj.quotes)) return obj.quotes as QuoteDict[];
  if (Array.isArray(payload)) return payload as QuoteDict[];
  return null;
}

export class MarketStream {
  private abort: AbortController | null = null;
  private closed = false;
  private attempt = 0;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {}

  connect(
    symbols: string[],
    onQuotes: (q: QuoteDict[]) => void,
    onError?: (e: Error) => void,
  ): void {
    this.disconnect();
    this.closed = false;
    this.attempt = 0;
    const cleaned = symbols.map((s) => s.trim()).filter(Boolean);
    if (cleaned.length === 0) return;
    void this.loop(cleaned, onQuotes, onError);
  }

  disconnect(): void {
    this.closed = true;
    if (this.reconnectTimer != null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.abort?.abort();
    this.abort = null;
  }

  private scheduleReconnect(
    symbols: string[],
    onQuotes: (q: QuoteDict[]) => void,
    onError?: (e: Error) => void,
  ) {
    if (this.closed) return;
    const delay = nextBackoffMs(this.attempt);
    this.attempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (!this.closed) void this.loop(symbols, onQuotes, onError);
    }, delay);
  }

  private async loop(
    symbols: string[],
    onQuotes: (q: QuoteDict[]) => void,
    onError?: (e: Error) => void,
  ) {
    if (this.closed) return;
    const controller = new AbortController();
    this.abort = controller;
    const token = getToken();
    const qs = encodeURIComponent(symbols.join(","));
    const url = `${getApiBase()}/api/market/stream?symbols=${qs}&interval_s=5`;

    try {
      const res = await fetch(url, {
        headers: {
          Accept: "text/event-stream",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        throw new Error(res.statusText || "Market stream failed");
      }
      this.attempt = 0;
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (!this.closed) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n");
        buffer = parts.pop() || "";
        for (const raw of parts) {
          const line = raw.trimEnd();
          if (!line.startsWith("data:")) continue;
          const json = line.slice(5).trim();
          if (!json || json === "[DONE]") continue;
          try {
            const parsed = JSON.parse(json) as unknown;
            const quotes = extractQuotes(parsed);
            if (quotes) onQuotes(quotes);
          } catch {
            /* ignore partial JSON */
          }
        }
      }
      if (!this.closed) {
        this.scheduleReconnect(symbols, onQuotes, onError);
      }
    } catch (e) {
      if (this.closed || (e instanceof DOMException && e.name === "AbortError")) return;
      const err = e instanceof Error ? e : new Error(String(e));
      onError?.(err);
      this.scheduleReconnect(symbols, onQuotes, onError);
    }
  }
}
