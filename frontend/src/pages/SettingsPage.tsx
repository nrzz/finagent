import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { getApiBase, setApiBase } from "@/lib/native";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { LLMStudio } from "@/components/llm/LLMStudio";

type SettingsPayload = {
  settings: {
    llm: Record<string, unknown>;
    markets: { stocks_global: boolean; india: boolean; crypto: { enabled: boolean }; quote_cache_ttl_s: number };
    trading: {
      mode: string;
      kill_switch: boolean;
      risk: { max_position_pct: number; max_daily_loss_pct: number; max_order_value: number };
    };
    appearance: { theme: string; base_currency: string; timezone: string; number_format: string };
  };
};

type Tab = "ai" | "markets" | "trading" | "brokers" | "appearance" | "device" | "secrets";

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("ai");
  const [data, setData] = useState<SettingsPayload["settings"] | null>(null);
  const [secretName, setSecretName] = useState("OPENAI_API_KEY");
  const [secretValue, setSecretValue] = useState("");
  const [msg, setMsg] = useState("");
  const [reauth, setReauth] = useState("");
  const [brokers, setBrokers] = useState<
    { name: string; display_name?: string; supports_live: boolean; configured?: boolean; secret_names?: string[] }[]
  >([]);
  const [brokerSecret, setBrokerSecret] = useState("");
  const [brokerSecretVal, setBrokerSecretVal] = useState("");
  const [serverUrl, setServerUrl] = useState(() => getApiBase());

  async function load() {
    const res = await api<SettingsPayload>("/api/settings");
    setData(res.settings);
    try {
      const b = await api<{ brokers: typeof brokers }>("/api/trading/brokers");
      setBrokers(b.brokers);
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    load().catch((e) => setMsg(e.message));
  }, []);

  async function save(patch: Record<string, unknown>, needsReauth = false) {
    setMsg("");
    await api("/api/settings", {
      method: "PUT",
      body: JSON.stringify({ settings: patch, reauth_password: needsReauth ? reauth : null }),
    });
    setMsg("Saved");
    await load();
  }

  if (!data) return <p className="text-sm text-muted-foreground">Loading settings…</p>;

  const tabs: { id: Tab; label: string }[] = [
    { id: "ai", label: "AI / LLMs" },
    { id: "markets", label: "Markets" },
    { id: "trading", label: "Trading" },
    { id: "brokers", label: "Brokers" },
    { id: "appearance", label: "Appearance" },
    { id: "device", label: "Device / APK" },
    { id: "secrets", label: "Secrets" },
  ];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Configure everything in the UI — multi-LLM, markets, risk, and secrets. No config files.
        </p>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-border pb-1">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`rounded-md px-3 py-1.5 text-sm transition-colors ${
              tab === t.id ? "bg-primary/15 text-foreground font-medium" : "text-muted-foreground hover:bg-accent"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "ai" && <LLMStudio />}

      {tab === "brokers" && (
        <Card>
          <CardHeader>
            <CardTitle>Brokers</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Save API keys now. Execution stays on <strong>paper</strong> until you enable Live
              (re-auth). Stubs refuse live orders until a real plugin is implemented.
            </p>
            {brokers.map((b) => (
              <div key={b.name} className="rounded-lg border p-3 space-y-2">
                <div className="flex justify-between gap-2 text-sm">
                  <span className="font-medium">{b.display_name || b.name}</span>
                  <span className="text-xs text-muted-foreground">
                    {b.name === "paper"
                      ? "Active (paper)"
                      : b.configured
                        ? "Configured · paper until Live"
                        : "Not configured"}
                  </span>
                </div>
                {b.secret_names && b.secret_names.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {b.secret_names.map((s) => (
                      <button
                        key={s}
                        type="button"
                        className="text-[10px] rounded border px-1.5 py-0.5 hover:bg-accent"
                        onClick={() => setBrokerSecret(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            ))}
            <div className="space-y-2 border-t pt-3">
              <Label>Secret name</Label>
              <Input value={brokerSecret} onChange={(e) => setBrokerSecret(e.target.value)} placeholder="ZERODHA_API_KEY" />
              <Label>Value</Label>
              <Input type="password" value={brokerSecretVal} onChange={(e) => setBrokerSecretVal(e.target.value)} />
              <Button
                onClick={async () => {
                  await api("/api/settings/secrets", {
                    method: "PUT",
                    body: JSON.stringify({ name: brokerSecret, value: brokerSecretVal }),
                  });
                  setBrokerSecretVal("");
                  setMsg("Broker secret stored (encrypted)");
                  await load();
                }}
              >
                Store broker secret
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "markets" && (
        <Card>
          <CardHeader>
            <CardTitle>Markets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <label className="flex gap-2 text-sm items-center">
              <input
                type="checkbox"
                checked={data.markets.stocks_global}
                onChange={(e) =>
                  setData({ ...data, markets: { ...data.markets, stocks_global: e.target.checked } })
                }
              />
              Global stocks
            </label>
            <label className="flex gap-2 text-sm items-center">
              <input
                type="checkbox"
                checked={data.markets.india}
                onChange={(e) => setData({ ...data, markets: { ...data.markets, india: e.target.checked } })}
              />
              India + mutual funds
            </label>
            <label className="flex gap-2 text-sm items-center">
              <input
                type="checkbox"
                checked={data.markets.crypto.enabled}
                onChange={(e) =>
                  setData({
                    ...data,
                    markets: { ...data.markets, crypto: { ...data.markets.crypto, enabled: e.target.checked } },
                  })
                }
              />
              Crypto
            </label>
            <Button onClick={() => save({ markets: data.markets })}>Save markets</Button>
          </CardContent>
        </Card>
      )}

      {tab === "trading" && (
        <Card>
          <CardHeader>
            <CardTitle>Trading & risk</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Live mode requires re-auth. Kill switch halts all orders.</p>
            <div className="space-y-1">
              <Label>Mode (paper|live)</Label>
              <Input
                value={data.trading.mode}
                onChange={(e) => setData({ ...data, trading: { ...data.trading, mode: e.target.value } })}
              />
            </div>
            <label className="flex gap-2 text-sm items-center">
              <input
                type="checkbox"
                checked={data.trading.kill_switch}
                onChange={(e) =>
                  setData({ ...data, trading: { ...data.trading, kill_switch: e.target.checked } })
                }
              />
              Kill switch
            </label>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>Max pos %</Label>
                <Input
                  type="number"
                  value={data.trading.risk.max_position_pct}
                  onChange={(e) =>
                    setData({
                      ...data,
                      trading: {
                        ...data.trading,
                        risk: { ...data.trading.risk, max_position_pct: Number(e.target.value) },
                      },
                    })
                  }
                />
              </div>
              <div>
                <Label>Max daily loss %</Label>
                <Input
                  type="number"
                  value={data.trading.risk.max_daily_loss_pct}
                  onChange={(e) =>
                    setData({
                      ...data,
                      trading: {
                        ...data.trading,
                        risk: { ...data.trading.risk, max_daily_loss_pct: Number(e.target.value) },
                      },
                    })
                  }
                />
              </div>
              <div>
                <Label>Max order value</Label>
                <Input
                  type="number"
                  value={data.trading.risk.max_order_value}
                  onChange={(e) =>
                    setData({
                      ...data,
                      trading: {
                        ...data.trading,
                        risk: { ...data.trading.risk, max_order_value: Number(e.target.value) },
                      },
                    })
                  }
                />
              </div>
            </div>
            <div className="space-y-1">
              <Label>Re-auth password (for mode/kill switch)</Label>
              <Input type="password" value={reauth} onChange={(e) => setReauth(e.target.value)} />
            </div>
            <Button onClick={() => save({ trading: data.trading }, true)}>Save trading</Button>
          </CardContent>
        </Card>
      )}

      {tab === "appearance" && (
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1">
              <Label>Theme</Label>
              <Input
                value={data.appearance.theme}
                onChange={(e) => setData({ ...data, appearance: { ...data.appearance, theme: e.target.value } })}
              />
            </div>
            <div className="space-y-1">
              <Label>Base currency</Label>
              <Input
                value={data.appearance.base_currency}
                onChange={(e) =>
                  setData({ ...data, appearance: { ...data.appearance, base_currency: e.target.value } })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Timezone</Label>
              <Input
                value={data.appearance.timezone}
                onChange={(e) =>
                  setData({ ...data, appearance: { ...data.appearance, timezone: e.target.value } })
                }
              />
            </div>
            <div className="space-y-1">
              <Label>Number format (indian|western)</Label>
              <Input
                value={data.appearance.number_format}
                onChange={(e) =>
                  setData({ ...data, appearance: { ...data.appearance, number_format: e.target.value } })
                }
              />
            </div>
            <Button
              onClick={() => {
                document.documentElement.classList.toggle("light", data.appearance.theme === "light");
                document.documentElement.classList.toggle("dark", data.appearance.theme !== "light");
                return save({ appearance: data.appearance });
              }}
            >
              Save appearance
            </Button>
          </CardContent>
        </Card>
      )}

      {tab === "device" && (
        <Card>
          <CardHeader>
            <CardTitle>Device / APK</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              For Android APK / Capacitor on another device, set the FinAgent server URL (e.g.{" "}
              <span className="font-mono">http://192.168.1.10:8000</span>). Leave blank on the same
              host as the UI (PWA / START.bat).
            </p>
            <div className="space-y-1">
              <Label>API server URL</Label>
              <Input
                value={serverUrl}
                onChange={(e) => setServerUrl(e.target.value)}
                placeholder="http://192.168.1.10:8000"
                data-testid="apk-server-url"
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button
                onClick={() => {
                  setApiBase(serverUrl.trim());
                  setMsg(serverUrl.trim() ? `Server URL saved: ${serverUrl.trim()}` : "Using same-origin /api");
                }}
              >
                Save server URL
              </Button>
              <Button
                variant="secondary"
                onClick={() => {
                  setServerUrl("");
                  setApiBase("");
                  setMsg("Cleared — same-origin /api");
                }}
              >
                Clear
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Current: {getApiBase() || "(same origin)"} · cleartext LAN allowed in Capacitor config.
            </p>
          </CardContent>
        </Card>
      )}

      {tab === "secrets" && (
        <Card>
          <CardHeader>
            <CardTitle>Secrets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Encrypted at rest. Prefer adding API keys inside AI Studio when connecting a provider.
            </p>
            <div className="space-y-1">
              <Label>Name</Label>
              <Input value={secretName} onChange={(e) => setSecretName(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Value</Label>
              <Input type="password" value={secretValue} onChange={(e) => setSecretValue(e.target.value)} />
            </div>
            <Button
              onClick={async () => {
                await api("/api/settings/secrets", {
                  method: "PUT",
                  body: JSON.stringify({ name: secretName, value: secretValue }),
                });
                setSecretValue("");
                setMsg("Secret stored");
              }}
            >
              Store secret
            </Button>
          </CardContent>
        </Card>
      )}

      {msg && <p className="text-sm text-muted-foreground">{msg}</p>}
    </div>
  );
}
