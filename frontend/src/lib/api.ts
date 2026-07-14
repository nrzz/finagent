import { getApiBase } from "./native";

const TOKEN_KEY = "finagent_token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

export async function api<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const url = path.startsWith("http") ? path : `${getApiBase()}${path}`;
  const res = await fetch(url, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    if (!path.includes("/api/auth/")) {
      window.location.href = "/login";
    }
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function streamChat(
  message: string,
  history: { role: string; content: string }[],
  onEvent: (ev: Record<string, unknown>) => void,
  signal?: AbortSignal,
) {
  const token = getToken();
  const res = await fetch(`${getApiBase()}/api/chat/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ message, history }),
    signal,
  });
  if (!res.ok || !res.body) throw new Error("Stream failed");
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const json = line.slice(5).trim();
      try {
        onEvent(JSON.parse(json));
      } catch {
        /* ignore partial */
      }
    }
  }
}

export type PullProgressEvent = {
  model: string;
  phase: string;
  percent: number | null;
  completed_bytes: number;
  total_bytes: number;
  speed_bps: number;
  eta_s: number | null;
  layer?: string | null;
  status?: string;
  error?: string | null;
  elapsed_s?: number;
  running?: boolean;
  attached?: boolean;
  heartbeat?: boolean;
};

/** Consume SSE from Ollama pull/stream until terminal phase. */
export async function streamOllamaPull(
  model: string,
  baseUrl: string | null,
  onEvent: (ev: PullProgressEvent) => void,
  signal?: AbortSignal,
  options?: { replace?: boolean },
): Promise<PullProgressEvent> {
  const token = getToken();
  const res = await fetch(`${getApiBase()}/api/settings/llm/ollama/pull/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      model,
      base_url: baseUrl,
      replace: options?.replace ?? false,
    }),
    signal,
  });
  if (res.status === 401) {
    clearToken();
    window.location.href = "/login";
    throw new Error("Not authenticated");
  }
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let last: PullProgressEvent = {
    model,
    phase: "starting",
    percent: null,
    completed_bytes: 0,
    total_bytes: 0,
    speed_bps: 0,
    eta_s: null,
  };
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith("data:")) continue;
      const json = line.slice(5).trim();
      try {
        last = JSON.parse(json) as PullProgressEvent;
        onEvent(last);
        if (["success", "failed", "cancelled"].includes(last.phase)) {
          return last;
        }
      } catch {
        /* ignore */
      }
    }
  }
  return last;
}

export function formatBytes(n: number): string {
  if (!n || n <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let v = n;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
}

export function formatEta(seconds: number | null | undefined): string {
  if (seconds == null || !Number.isFinite(seconds) || seconds < 0) return "…";
  if (seconds < 60) return `~${Math.ceil(seconds)}s`;
  const m = Math.ceil(seconds / 60);
  if (m < 60) return `~${m} min`;
  return `~${(m / 60).toFixed(1)} h`;
}
