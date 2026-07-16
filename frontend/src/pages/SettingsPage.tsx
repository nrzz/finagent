import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { formatNotifyTestResult } from "@/lib/notify";
import { getApiBase, setApiBase } from "@/lib/native";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { LLMStudio } from "@/components/llm/LLMStudio";

type Trading = {
  mode: string;
  kill_switch: boolean;
  require_order_confirmation?: boolean;
  risk: { max_position_pct: number; max_daily_loss_pct: number; max_order_value: number };
  paper_starting_cash?: number;
  paper_currency?: string;
  default_broker?: string;
  paper_backend?: string;
  india_default_product?: string;
};

type Notifications = {
  master_enabled: boolean;
  events_alert?: boolean;
  events_job?: boolean;
  events_order?: boolean;
  events_system?: boolean;
  quiet_hours_start?: string | null;
  quiet_hours_end?: string | null;
  mute_symbols?: string[];
  telegram?: Record<string, unknown>;
  email?: Record<string, unknown>;
  webhook?: Record<string, unknown>;
  webpush?: Record<string, unknown>;
  discord?: Record<string, unknown>;
  slack?: Record<string, unknown>;
};

type SettingsData = {
  llm: Record<string, unknown>;
  markets: {
    stocks_global: boolean;
    india: boolean;
    crypto: { enabled: boolean; exchanges?: string[] };
    quote_cache_ttl_s?: number;
  };
  trading: Trading;
  appearance: {
    theme: string;
    base_currency: string;
    timezone: string;
    number_format: string;
    locale?: string;
  };
  notifications?: Notifications;
};

type Broker = {
  name: string;
  display_name?: string;
  supports_live: boolean;
  configured?: boolean;
  session?: boolean;
  secret_names?: string[];
};

type Tab =
  | "ai"
  | "markets"
  | "trading"
  | "brokers"
  | "notifications"
  | "appearance"
  | "device"
  | "secrets"
  | "security"
  | "backup";

const BROKER_HELP: Record<string, { title: string; steps: string[]; link?: string }> = {
  zerodha: {
    title: "Connect Zerodha Kite (5 steps)",
    link: "https://developers.kite.trade/",
    steps: [
      "Create a Kite Connect app and copy API key + secret.",
      "Paste them below and save with your FinAgent password.",
      "Click Open Kite login, sign in, copy the request_token from the redirect URL.",
      "Paste request token → Exchange token.",
      "Click Test connection — status should say Connected.",
    ],
  },
  angel: {
    title: "Connect Angel One (4 steps)",
    link: "https://smartapi.angelbroking.com/",
    steps: [
      "Create a SmartAPI app; copy API key.",
      "Save client id, PIN, and TOTP secret (from your authenticator setup).",
      "Click Login to Angel — FinAgent creates a session.",
      "Test connection, then set Angel as default live broker if you want.",
    ],
  },
  alpaca: {
    title: "Connect Alpaca (3 steps)",
    link: "https://app.alpaca.markets/paper/dashboard/overview",
    steps: [
      "Open Alpaca → Paper (or Live) → API Keys.",
      "Paste Key ID + Secret below and save with your password.",
      "Test connection. For practice without local paper book, set Paper backend = Alpaca in Trading → Advanced.",
    ],
  },
};

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("ai");
  const [data, setData] = useState<SettingsData | null>(null);
  const [secrets, setSecrets] = useState<{ name: string; masked: string }[]>([]);
  const [secretName, setSecretName] = useState("OPENAI_API_KEY");
  const [secretValue, setSecretValue] = useState("");
  const [msg, setMsg] = useState("");
  const [reauth, setReauth] = useState("");
  const [brokers, setBrokers] = useState<Broker[]>([]);
  const [brokerSecret, setBrokerSecret] = useState("");
  const [brokerSecretVal, setBrokerSecretVal] = useState("");
  const [activeBroker, setActiveBroker] = useState("alpaca");
  const [requestToken, setRequestToken] = useState("");
  const [serverUrl, setServerUrl] = useState(() => getApiBase());
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [audit, setAudit] = useState<Record<string, unknown>[]>([]);
  const [tgToken, setTgToken] = useState("");
  const [tgChat, setTgChat] = useState("");
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpTo, setSmtpTo] = useState("");
  const [smtpPass, setSmtpPass] = useState("");
  const [hookUrl, setHookUrl] = useState("");
  const [hookSecretName, setHookSecretName] = useState("NOTIFY_WEBHOOK_URL");

  async function load() {
    const res = await api<{
      settings: SettingsData;
      secrets: { name: string; masked: string }[];
    }>("/api/settings");
    setData(res.settings);
    setSecrets(res.secrets || []);
    try {
      const b = await api<{ brokers: Broker[] }>("/api/trading/brokers");
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

  async function storeSecret(name: string, value: string) {
    if (!reauth) {
      setMsg("Enter your FinAgent password (re-auth) first — required to save secrets.");
      return;
    }
    await api("/api/settings/secrets", {
      method: "PUT",
      body: JSON.stringify({ name, value, reauth_password: reauth }),
    });
    setMsg(`Saved ${name} (encrypted)`);
    setBrokerSecretVal("");
    setSecretValue("");
    await load();
  }

  if (!data) return <p className="text-sm text-muted-foreground">Loading settings…</p>;

  const tabs: { id: Tab; label: string }[] = [
    { id: "ai", label: "AI / LLMs" },
    { id: "markets", label: "Markets" },
    { id: "trading", label: "Trading" },
    { id: "brokers", label: "Brokers" },
    { id: "notifications", label: "Notifications" },
    { id: "appearance", label: "Appearance" },
    { id: "device", label: "Device / APK" },
    { id: "secrets", label: "Secrets" },
    { id: "security", label: "Security / Audit" },
    { id: "backup", label: "Backup" },
  ];

  const n = data.notifications || { master_enabled: false };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Everything is configurable here — no config files. Paper trading is the safe default.
        </p>
      </div>

      <div className="sticky top-0 z-10 rounded-lg border border-border bg-background/95 backdrop-blur p-3 space-y-2 shadow-sm">
        <Label>Your FinAgent password (needed to save secrets or change live trading)</Label>
        <Input
          type="password"
          value={reauth}
          onChange={(e) => setReauth(e.target.value)}
          placeholder="Re-enter password when saving sensitive changes"
          autoComplete="current-password"
        />
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

      {msg && <p className="text-sm text-amber-200">{msg}</p>}

      {tab === "ai" && <LLMStudio />}

      {tab === "markets" && (
        <Card>
          <CardHeader>
            <CardTitle>Markets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {(
              [
                ["stocks_global", "US / global stocks"],
                ["india", "India equities + mutual funds"],
              ] as const
            ).map(([k, label]) => (
              <label key={k} className="flex items-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={Boolean(data.markets[k])}
                  onChange={(e) =>
                    setData({
                      ...data,
                      markets: { ...data.markets, [k]: e.target.checked },
                    })
                  }
                />
                {label}
              </label>
            ))}
            <label className="flex items-center gap-2 text-sm">
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
            {showAdvanced && (
              <div className="space-y-1">
                <Label>Quote cache TTL (seconds)</Label>
                <Input
                  type="number"
                  value={data.markets.quote_cache_ttl_s ?? 30}
                  onChange={(e) =>
                    setData({
                      ...data,
                      markets: { ...data.markets, quote_cache_ttl_s: Number(e.target.value) },
                    })
                  }
                />
              </div>
            )}
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdvanced(!showAdvanced)}>
              {showAdvanced ? "Hide advanced" : "Show advanced"}
            </Button>
            <Button onClick={() => save({ markets: data.markets })}>Save markets</Button>
          </CardContent>
        </Card>
      )}

      {tab === "trading" && (
        <Card>
          <CardHeader>
            <CardTitle>Trading safety</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Safe Mode: Paper on, confirm on. Live money needs your password and a connected broker.
            </p>
            <p className="text-xs text-muted-foreground">
              Market quotes use free delayed data (yfinance/ccxt). Live broker orders are separate — quotes
              may lag fills.
            </p>
            <Label>Mode</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={data.trading.mode}
              onChange={(e) => setData({ ...data, trading: { ...data.trading, mode: e.target.value } })}
            >
              <option value="paper">Paper (practice — no real money)</option>
              <option value="live">Live (real broker orders)</option>
            </select>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={data.trading.kill_switch}
                onChange={(e) =>
                  setData({ ...data, trading: { ...data.trading, kill_switch: e.target.checked } })
                }
              />
              Kill switch (blocks all orders) — turning OFF needs password
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={data.trading.require_order_confirmation !== false}
                onChange={(e) =>
                  setData({
                    ...data,
                    trading: { ...data.trading, require_order_confirmation: e.target.checked },
                  })
                }
              />
              Require Confirm before placing orders
            </label>
            <Label>Default live broker</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={data.trading.default_broker || "alpaca"}
              onChange={(e) =>
                setData({ ...data, trading: { ...data.trading, default_broker: e.target.value } })
              }
            >
              <option value="zerodha">Zerodha Kite</option>
              <option value="angel">Angel One</option>
              <option value="alpaca">Alpaca</option>
            </select>
            <div className="grid grid-cols-3 gap-2">
              <div>
                <Label>Max position %</Label>
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
            {showAdvanced && (
              <div className="space-y-2 border-t pt-3">
                <Label>Paper starting cash</Label>
                <Input
                  type="number"
                  value={data.trading.paper_starting_cash ?? 1_000_000}
                  onChange={(e) =>
                    setData({
                      ...data,
                      trading: { ...data.trading, paper_starting_cash: Number(e.target.value) },
                    })
                  }
                />
                <Label>Paper currency</Label>
                <Input
                  value={data.trading.paper_currency || "INR"}
                  onChange={(e) =>
                    setData({ ...data, trading: { ...data.trading, paper_currency: e.target.value } })
                  }
                />
                <Label>Paper backend</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={data.trading.paper_backend || "local"}
                  onChange={(e) =>
                    setData({ ...data, trading: { ...data.trading, paper_backend: e.target.value } })
                  }
                >
                  <option value="local">Local paper book</option>
                  <option value="alpaca">Alpaca paper API</option>
                </select>
                <Label>India default product</Label>
                <select
                  className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                  value={data.trading.india_default_product || "CNC"}
                  onChange={(e) =>
                    setData({
                      ...data,
                      trading: { ...data.trading, india_default_product: e.target.value },
                    })
                  }
                >
                  <option value="CNC">CNC (delivery)</option>
                  <option value="MIS">MIS (intraday)</option>
                  <option value="NRML">NRML (F&O carry)</option>
                </select>
              </div>
            )}
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdvanced(!showAdvanced)}>
              {showAdvanced ? "Hide advanced" : "Show advanced"}
            </Button>
            <Button onClick={() => save({ trading: data.trading }, true)}>Save trading (needs password)</Button>
          </CardContent>
        </Card>
      )}

      {tab === "brokers" && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Connect a broker</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Save keys now. Orders stay on <strong>paper</strong> until you enable Live in Trading
                (with your password). Always click Test connection.
              </p>
              <div className="flex flex-wrap gap-2">
                {brokers
                  .filter((b) => b.name !== "paper")
                  .map((b) => (
                    <Button
                      key={b.name}
                      size="sm"
                      variant={activeBroker === b.name ? "default" : "outline"}
                      onClick={() => setActiveBroker(b.name)}
                    >
                      {b.display_name || b.name}
                      {b.configured ? " · set" : ""}
                    </Button>
                  ))}
              </div>
              {BROKER_HELP[activeBroker] && (
                <div className="rounded-md border border-border/60 bg-muted/20 p-3 text-sm space-y-1">
                  <div className="font-medium">{BROKER_HELP[activeBroker].title}</div>
                  <ol className="list-decimal pl-4 text-muted-foreground space-y-0.5">
                    {BROKER_HELP[activeBroker].steps.map((s) => (
                      <li key={s}>{s}</li>
                    ))}
                  </ol>
                  {BROKER_HELP[activeBroker].link && (
                    <a
                      className="text-primary underline text-xs"
                      href={BROKER_HELP[activeBroker].link}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Official developer site
                    </a>
                  )}
                </div>
              )}
              {brokers
                .filter((b) => b.name === activeBroker)
                .map((b) => (
                  <div key={b.name} className="space-y-2">
                    <div className="text-xs text-muted-foreground">
                      Status:{" "}
                      {b.session
                        ? "Connected"
                        : b.configured
                          ? "Configured · needs login/session"
                          : "Not set up"}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(b.secret_names || []).map((s) => (
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
                  </div>
                ))}
              <Label>Secret name</Label>
              <Input
                value={brokerSecret}
                onChange={(e) => setBrokerSecret(e.target.value)}
                placeholder="ALPACA_API_KEY"
              />
              <Label>Value</Label>
              <Input
                type="password"
                value={brokerSecretVal}
                onChange={(e) => setBrokerSecretVal(e.target.value)}
              />
              <div className="flex flex-wrap gap-2">
                <Button
                  onClick={async () => {
                    try {
                      await storeSecret(brokerSecret, brokerSecretVal);
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Save failed");
                    }
                  }}
                >
                  Save secret
                </Button>
                <Button
                  variant="secondary"
                  onClick={async () => {
                    try {
                      const r = await api<{ status?: string; ok?: boolean }>(
                        `/api/settings/brokers/${activeBroker}/test`,
                        { method: "POST" },
                      );
                      setMsg(`Test: ${r.status || (r.ok ? "ok" : "failed")}`);
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Test failed");
                    }
                  }}
                >
                  Test connection
                </Button>
                <Button
                  variant="outline"
                  onClick={async () => {
                    try {
                      const r = await api<{ imported: number }>(
                        `/api/settings/brokers/${activeBroker}/sync-holdings`,
                        { method: "POST" },
                      );
                      setMsg(`Imported ${r.imported} holdings into Portfolio`);
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Sync failed");
                    }
                  }}
                >
                  Sync holdings
                </Button>
              </div>
              {activeBroker === "zerodha" && (
                <div className="space-y-2 border-t pt-3">
                  <Button
                    variant="outline"
                    onClick={async () => {
                      const r = await api<{ login_url?: string }>(
                        `/api/settings/brokers/zerodha/test`,
                        { method: "POST" },
                      );
                      if (r.login_url) window.open(r.login_url, "_blank");
                      else setMsg("Save ZERODHA_API_KEY first, then open login");
                    }}
                  >
                    Open Kite login
                  </Button>
                  <Label>Request token (from redirect URL)</Label>
                  <Input value={requestToken} onChange={(e) => setRequestToken(e.target.value)} />
                  <Button
                    onClick={async () => {
                      try {
                        await api("/api/settings/brokers/zerodha/exchange-token", {
                          method: "POST",
                          body: JSON.stringify({
                            request_token: requestToken,
                            reauth_password: reauth,
                          }),
                        });
                        setMsg("Zerodha access token saved");
                        setRequestToken("");
                        await load();
                      } catch (e) {
                        setMsg(e instanceof Error ? e.message : "Exchange failed");
                      }
                    }}
                  >
                    Exchange token
                  </Button>
                </div>
              )}
              {activeBroker === "angel" && (
                <div className="border-t pt-3">
                  <Button
                    onClick={async () => {
                      try {
                        await api("/api/settings/brokers/angel/login", {
                          method: "POST",
                          body: JSON.stringify({ reauth_password: reauth }),
                        });
                        setMsg("Angel session saved");
                        await load();
                      } catch (e) {
                        setMsg(e instanceof Error ? e.message : "Angel login failed");
                      }
                    }}
                  >
                    Login to Angel
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "notifications" && (
        <Card>
          <CardHeader>
            <CardTitle>Notifications</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              In-app alerts always work. Turn on channels below and click Test before relying on them.
            </p>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={Boolean(n.master_enabled)}
                onChange={(e) =>
                  setData({
                    ...data,
                    notifications: { ...n, master_enabled: e.target.checked },
                  })
                }
              />
              Send alerts outside this app
            </label>
            <div className="rounded-md border p-3 space-y-3">
              <div className="font-medium text-sm">Quiet hours & filters</div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label>Quiet hours start</Label>
                  <Input
                    type="time"
                    value={n.quiet_hours_start || ""}
                    onChange={(e) =>
                      setData({
                        ...data,
                        notifications: {
                          ...n,
                          quiet_hours_start: e.target.value || null,
                        },
                      })
                    }
                  />
                </div>
                <div className="space-y-1">
                  <Label>Quiet hours end</Label>
                  <Input
                    type="time"
                    value={n.quiet_hours_end || ""}
                    onChange={(e) =>
                      setData({
                        ...data,
                        notifications: {
                          ...n,
                          quiet_hours_end: e.target.value || null,
                        },
                      })
                    }
                  />
                </div>
              </div>
              <div className="space-y-1">
                <Label>Mute symbols (comma-separated)</Label>
                <Input
                  value={(n.mute_symbols || []).join(", ")}
                  onChange={(e) =>
                    setData({
                      ...data,
                      notifications: {
                        ...n,
                        mute_symbols: e.target.value
                          .split(",")
                          .map((s) => s.trim())
                          .filter(Boolean),
                      },
                    })
                  }
                  placeholder="RELIANCE.NS, BTC/USDT"
                />
              </div>
              <div className="flex flex-wrap gap-3 text-sm">
                {(
                  [
                    ["events_alert", "Price alerts"],
                    ["events_job", "Jobs"],
                    ["events_order", "Orders"],
                    ["events_system", "System"],
                  ] as const
                ).map(([key, label]) => (
                  <label key={key} className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={n[key] !== false}
                      onChange={(e) =>
                        setData({
                          ...data,
                          notifications: { ...n, [key]: e.target.checked },
                        })
                      }
                    />
                    {label}
                  </label>
                ))}
              </div>
            </div>
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium text-sm">Telegram</div>
              <p className="text-xs text-muted-foreground">
                Talk to @BotFather → create bot → paste token. Message your bot, then put your chat id.
              </p>
              <Input
                type="password"
                placeholder="Bot token"
                value={tgToken}
                onChange={(e) => setTgToken(e.target.value)}
              />
              <Input
                placeholder="Chat id"
                value={tgChat || String(n.telegram?.chat_id || "")}
                onChange={(e) => setTgChat(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={async () => {
                    try {
                      if (tgToken) await storeSecret("TELEGRAM_BOT_TOKEN", tgToken);
                      await save({
                        notifications: {
                          master_enabled: true,
                          telegram: {
                            enabled: true,
                            bot_token_secret: "TELEGRAM_BOT_TOKEN",
                            chat_id: tgChat || n.telegram?.chat_id,
                          },
                        },
                      });
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Failed");
                    }
                  }}
                >
                  Save Telegram
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={async () => {
                    try {
                      const r = await api<{ ok?: boolean; results?: Array<{ ok?: boolean; error?: string }> }>(
                        "/api/settings/notifications/test/telegram",
                        { method: "POST" },
                      );
                      setMsg(formatNotifyTestResult(r));
                    } catch (e) {
                      setMsg(e instanceof Error ? `Test failed: ${e.message}` : "Test failed");
                    }
                  }}
                >
                  Test send
                </Button>
              </div>
            </div>
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium text-sm">Email (SMTP)</div>
              <Input placeholder="SMTP host" value={smtpHost} onChange={(e) => setSmtpHost(e.target.value)} />
              <Input placeholder="To address" value={smtpTo} onChange={(e) => setSmtpTo(e.target.value)} />
              <Input
                type="password"
                placeholder="SMTP password"
                value={smtpPass}
                onChange={(e) => setSmtpPass(e.target.value)}
              />
              <div className="flex gap-2">
                <Button
                  size="sm"
                  onClick={async () => {
                    try {
                      if (smtpPass) await storeSecret("SMTP_PASSWORD", smtpPass);
                      await save({
                        notifications: {
                          master_enabled: true,
                          email: {
                            enabled: true,
                            smtp_host: smtpHost,
                            smtp_to: smtpTo,
                            smtp_from: smtpTo,
                            smtp_password_secret: "SMTP_PASSWORD",
                          },
                        },
                      });
                    } catch (e) {
                      setMsg(e instanceof Error ? e.message : "Failed");
                    }
                  }}
                >
                  Save Email
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={async () => {
                    try {
                      setMsg(
                        formatNotifyTestResult(
                          await api("/api/settings/notifications/test/email", { method: "POST" }),
                        ),
                      );
                    } catch (e) {
                      setMsg(e instanceof Error ? `Test failed: ${e.message}` : "Test failed");
                    }
                  }}
                >
                  Test send
                </Button>
              </div>
            </div>
            {(
              [
                ["webhook", "NOTIFY_WEBHOOK_URL", "Generic webhook"],
                ["discord", "DISCORD_WEBHOOK_URL", "Discord"],
                ["slack", "SLACK_WEBHOOK_URL", "Slack"],
              ] as const
            ).map(([ch, secret, label]) => (
              <div key={ch} className="rounded-md border p-3 space-y-2">
                <div className="font-medium text-sm">{label}</div>
                <Input
                  type="password"
                  placeholder="Webhook URL"
                  value={hookSecretName === secret ? hookUrl : ""}
                  onFocus={() => setHookSecretName(secret)}
                  onChange={(e) => {
                    setHookSecretName(secret);
                    setHookUrl(e.target.value);
                  }}
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    onClick={async () => {
                      try {
                        if (hookUrl && hookSecretName === secret) await storeSecret(secret, hookUrl);
                        await save({
                          notifications: {
                            master_enabled: true,
                            [ch]: { enabled: true, webhook_url_secret: secret },
                          },
                        });
                      } catch (e) {
                        setMsg(e instanceof Error ? e.message : "Failed");
                      }
                    }}
                  >
                    Save {label}
                  </Button>
                  <Button
                    size="sm"
                    variant="secondary"
                    onClick={async () => {
                      try {
                        setMsg(
                          formatNotifyTestResult(
                            await api(`/api/settings/notifications/test/${ch}`, { method: "POST" }),
                          ),
                        );
                      } catch (e) {
                        setMsg(e instanceof Error ? `Test failed: ${e.message}` : "Test failed");
                      }
                    }}
                  >
                    Test send
                  </Button>
                </div>
              </div>
            ))}
            <div className="rounded-md border p-3 space-y-2">
              <div className="font-medium text-sm">Browser / phone push (Web Push)</div>
              <Button
                size="sm"
                onClick={async () => {
                  try {
                    const r = await api<{ vapid_public_key: string }>(
                      "/api/settings/notifications/vapid/generate",
                      { method: "POST" },
                    );
                    setMsg(`VAPID public key ready: ${r.vapid_public_key.slice(0, 16)}…`);
                    await load();
                  } catch (e) {
                    setMsg(e instanceof Error ? e.message : "VAPID failed");
                  }
                }}
              >
                Generate VAPID keys
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={async () => {
                  try {
                    setMsg(
                      formatNotifyTestResult(
                        await api("/api/settings/notifications/test/webpush", { method: "POST" }),
                      ),
                    );
                  } catch (e) {
                    setMsg(e instanceof Error ? e.message : "Test failed");
                  }
                }}
              >
                Test Web Push
              </Button>
            </div>
            <Button onClick={() => save({ notifications: data.notifications })}>Save notification prefs</Button>
          </CardContent>
        </Card>
      )}

      {tab === "appearance" && (
        <Card>
          <CardHeader>
            <CardTitle>Appearance</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Label>Theme</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={data.appearance.theme}
              onChange={(e) =>
                setData({ ...data, appearance: { ...data.appearance, theme: e.target.value } })
              }
            >
              <option value="dark">Dark</option>
              <option value="light">Light</option>
              <option value="system">System</option>
            </select>
            <Label>Base currency</Label>
            <Input
              value={data.appearance.base_currency}
              onChange={(e) =>
                setData({
                  ...data,
                  appearance: { ...data.appearance, base_currency: e.target.value },
                })
              }
            />
            <Label>Timezone</Label>
            <Input
              value={data.appearance.timezone}
              onChange={(e) =>
                setData({ ...data, appearance: { ...data.appearance, timezone: e.target.value } })
              }
            />
            <Label>Locale</Label>
            <Input
              value={data.appearance.locale || "en-IN"}
              onChange={(e) =>
                setData({ ...data, appearance: { ...data.appearance, locale: e.target.value } })
              }
            />
            <Label>Number format</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={data.appearance.number_format}
              onChange={(e) =>
                setData({
                  ...data,
                  appearance: { ...data.appearance, number_format: e.target.value },
                })
              }
            >
              <option value="indian">Indian</option>
              <option value="western">Western</option>
            </select>
            <Button onClick={() => save({ appearance: data.appearance })}>Save appearance</Button>
          </CardContent>
        </Card>
      )}

      {tab === "device" && (
        <Card>
          <CardHeader>
            <CardTitle>Device / APK</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Label>API server URL (phone / APK)</Label>
            <Input
              data-testid="apk-server-url"
              value={serverUrl}
              onChange={(e) => setServerUrl(e.target.value)}
              placeholder="http://192.168.x.x:8000"
            />
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  setApiBase(serverUrl);
                  setMsg("Server URL saved");
                }}
              >
                Save server URL
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setApiBase("");
                  setServerUrl("");
                  setMsg("Cleared");
                }}
              >
                Clear
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "secrets" && (
        <Card>
          <CardHeader>
            <CardTitle>Encrypted secrets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-muted-foreground">
              Values are encrypted at rest. After save you only see a masked preview.
            </p>
            <div className="text-xs space-y-1 max-h-40 overflow-auto">
              {secrets.length === 0 && <p className="text-muted-foreground">No secrets stored yet.</p>}
              {secrets.map((s) => (
                <div key={s.name} className="font-mono border-b border-border/40 py-1">
                  {s.name} · {s.masked}
                </div>
              ))}
            </div>
            <Label>Name</Label>
            <Input value={secretName} onChange={(e) => setSecretName(e.target.value)} />
            <Label>Value</Label>
            <Input
              type="password"
              value={secretValue}
              onChange={(e) => setSecretValue(e.target.value)}
            />
            <Button
              onClick={async () => {
                try {
                  await storeSecret(secretName, secretValue);
                } catch (e) {
                  setMsg(e instanceof Error ? e.message : "Failed");
                }
              }}
            >
              Store secret
            </Button>
          </CardContent>
        </Card>
      )}

      {tab === "security" && (
        <Card>
          <CardHeader>
            <CardTitle>Security & audit</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <ul className="text-sm text-muted-foreground list-disc pl-4 space-y-1">
              <li>FinAgent never lets the AI agent enable Live or confirm real orders.</li>
              <li>Secrets need your password; they are encrypted on disk.</li>
              <li>Panic Stop (header) turns kill switch on instantly.</li>
              <li>Backups keep secrets encrypted — restore needs the same FINAGENT_SECRET_KEY.</li>
            </ul>
            <div className="flex gap-2">
              <Button
                variant="destructive"
                onClick={async () => {
                  await save({ trading: { ...data.trading, kill_switch: true } }, false);
                  setMsg("Panic Stop on — all orders blocked");
                }}
              >
                Panic Stop now
              </Button>
              <Button
                variant="secondary"
                onClick={async () => {
                  const r = await api<{ items: Record<string, unknown>[] }>("/api/settings/audit");
                  setAudit(r.items || []);
                }}
              >
                Refresh audit log
              </Button>
            </div>
            <div className="text-xs font-mono max-h-60 overflow-auto space-y-1">
              {audit.map((a) => (
                <div key={String(a.id)} className="border-b border-border/40 py-1">
                  {String(a.created_at)} · {String(a.actor)} · {String(a.action)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {tab === "backup" && (
        <Card>
          <CardHeader>
            <CardTitle>Backup & restore</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Downloads your encrypted database. Keep the same FINAGENT_SECRET_KEY to decrypt secrets
              after restore.
            </p>
            <Button
              onClick={async () => {
                try {
                  const token = localStorage.getItem("finagent_token");
                  const res = await fetch("/api/settings/backup", {
                    headers: token ? { Authorization: `Bearer ${token}` } : {},
                  });
                  if (!res.ok) throw new Error("Backup failed");
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement("a");
                  a.href = url;
                  a.download = "finagent-backup.db";
                  a.click();
                  URL.revokeObjectURL(url);
                  setMsg("Backup downloaded");
                } catch {
                  setMsg("Backup failed");
                }
              }}
            >
              Download backup
            </Button>
            <Label>Restore .db file</Label>
            <Input
              type="file"
              accept=".db,.sqlite,.sqlite3"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const fd = new FormData();
                fd.append("file", file);
                const token = localStorage.getItem("finagent_token");
                const res = await fetch("/api/settings/backup/restore", {
                  method: "POST",
                  headers: token ? { Authorization: `Bearer ${token}` } : {},
                  body: fd,
                });
                if (!res.ok) setMsg("Restore failed");
                else setMsg("Restored — restart FinAgent to load the database");
              }}
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
