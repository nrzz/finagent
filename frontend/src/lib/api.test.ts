import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, getToken, setToken } from "./api";

const store = new Map<string, string>();

beforeEach(() => {
  store.clear();
  vi.stubGlobal("localStorage", {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => {
      store.set(k, String(v));
    },
    removeItem: (k: string) => {
      store.delete(k);
    },
  });
  vi.stubGlobal("window", {
    location: { href: "" },
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("api", () => {
  it("clears token and throws on 401", async () => {
    setToken("stale-token");
    expect(getToken()).toBe("stale-token");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        status: 401,
        ok: false,
        statusText: "Unauthorized",
        json: async () => ({ detail: "Not authenticated" }),
      })),
    );

    await expect(api("/api/settings")).rejects.toThrow("Not authenticated");
    expect(getToken()).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("throws with detail message on non-ok responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        status: 400,
        ok: false,
        statusText: "Bad Request",
        json: async () => ({ detail: "Invalid payload" }),
      })),
    );

    await expect(api("/api/settings")).rejects.toThrow("Invalid payload");
  });
});
