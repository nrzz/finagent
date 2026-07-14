import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, setToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { LLMStudio, type LLMProfile } from "@/components/llm/LLMStudio";

type Step = 0 | 1 | 2 | 3 | 4;

export function SetupWizardPage() {
  const [step, setStep] = useState<Step>(0);
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [activeLlm, setActiveLlm] = useState<LLMProfile | null>(null);
  const [india, setIndia] = useState(true);
  const [global, setGlobal] = useState(true);
  const [crypto, setCrypto] = useState(true);
  const [currency, setCurrency] = useState("INR");
  const [timezone, setTimezone] = useState("Asia/Kolkata");
  const [riskAck, setRiskAck] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    api<{ needs_setup: boolean; setup_complete: boolean }>("/api/auth/status")
      .then((s) => {
        if (s.setup_complete) navigate("/");
      })
      .catch(() => undefined);
  }, [navigate]);

  async function createAdmin() {
    setError("");
    setBusy(true);
    try {
      const res = await api<{ access_token: string }>("/api/auth/setup", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(res.access_token);
      setStep(1);
    } catch (err) {
      try {
        const res = await api<{ access_token: string }>("/api/auth/login", {
          method: "POST",
          body: JSON.stringify({ username, password }),
        });
        setToken(res.access_token);
        setStep(1);
      } catch {
        setError(err instanceof Error ? err.message : "Setup failed");
      }
    } finally {
      setBusy(false);
    }
  }

  async function finish() {
    setBusy(true);
    setError("");
    try {
      await api("/api/settings/wizard/complete", {
        method: "POST",
        body: JSON.stringify({
          settings: {
            risk_acknowledged: true,
            markets: {
              stocks_global: global,
              india,
              crypto: { enabled: crypto, exchanges: ["binance"] },
            },
            appearance: {
              base_currency: currency,
              timezone,
              theme: "dark",
              number_format: currency === "INR" ? "indian" : "western",
            },
            trading: { mode: "paper" },
          },
        }),
      });
      navigate("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not finish setup");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen grid place-items-center p-4 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-sky-950/40 via-background to-background">
      <Card className="w-full max-w-3xl border-border/80 shadow-xl">
        <CardHeader>
          <CardTitle>Welcome to FinAgent</CardTitle>
          <p className="text-sm text-muted-foreground">
            Guided setup — no coding or config files. Step {step + 1} of 5.
          </p>
          <div className="flex gap-2 pt-2">
            {[0, 1, 2, 3, 4].map((i) => (
              <div key={i} className={`h-1.5 flex-1 rounded-full ${i <= step ? "bg-primary" : "bg-muted"}`} />
            ))}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {step === 0 && (
            <>
              <p className="text-sm">Create your admin login (saved only on this computer).</p>
              <div className="space-y-2">
                <Label>Username</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>Password (min 8 characters)</Label>
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
              </div>
              {error && <p className="text-sm text-red-400">{error}</p>}
              <Button onClick={createAdmin} disabled={password.length < 8 || busy}>
                {busy ? "Working…" : "Continue"}
              </Button>
            </>
          )}

          {step === 1 && (
            <>
              <p className="text-sm text-muted-foreground">
                Pick Demo to start instantly, or connect Ollama / a cloud key. You can add more models later in
                Settings → AI Studio.
              </p>
              <LLMStudio
                compact
                onActivated={(p) => {
                  setActiveLlm(p);
                }}
              />
              <div className="flex justify-end gap-2 pt-2">
                <Button onClick={() => setStep(2)}>
                  Continue{activeLlm ? ` with ${activeLlm.name}` : " (Demo is fine)"}
                </Button>
              </div>
            </>
          )}

          {step === 2 && (
            <>
              <p className="text-sm">Turn markets on/off (you can change anytime in Settings).</p>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={global} onChange={(e) => setGlobal(e.target.checked)} />
                Global stocks / ETFs
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={india} onChange={(e) => setIndia(e.target.checked)} />
                India NSE/BSE + mutual funds
              </label>
              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={crypto} onChange={(e) => setCrypto(e.target.checked)} />
                Crypto
              </label>
              <Button onClick={() => setStep(3)}>Continue</Button>
            </>
          )}

          {step === 3 && (
            <>
              <div className="space-y-2">
                <Label>Base currency</Label>
                <Input value={currency} onChange={(e) => setCurrency(e.target.value.toUpperCase())} />
              </div>
              <div className="space-y-2">
                <Label>Timezone</Label>
                <Input value={timezone} onChange={(e) => setTimezone(e.target.value)} />
              </div>
              <p className="text-sm text-muted-foreground">
                Broker API keys are optional — add later in Settings if you want.
              </p>
              <Button onClick={() => setStep(4)}>Continue</Button>
            </>
          )}

          {step === 4 && (
            <>
              <p className="text-sm">
                Paper trading is on. Live trading stays locked until you turn it on in Settings.
              </p>
              <ul className="text-sm text-muted-foreground list-disc pl-5 space-y-1">
                <li>
                  AI:{" "}
                  {activeLlm
                    ? `${activeLlm.provider} / ${activeLlm.model}`
                    : "Demo (default — change anytime in AI Studio)"}
                </li>
                <li>
                  Markets: {[global && "global", india && "india", crypto && "crypto"].filter(Boolean).join(", ")}
                </li>
                <li>
                  Currency: {currency} · {timezone}
                </li>
              </ul>
              <label className="flex items-start gap-2 text-sm rounded-lg border border-amber-500/30 bg-amber-500/10 p-3">
                <input
                  type="checkbox"
                  className="mt-1"
                  checked={riskAck}
                  onChange={(e) => setRiskAck(e.target.checked)}
                />
                <span>
                  I understand FinAgent is <strong>not financial advice</strong>; paper trading is the
                  default; live trading (if enabled later) is at my own risk; markets involve risk of
                  loss.
                </span>
              </label>
              {error && <p className="text-sm text-red-400">{error}</p>}
              <Button onClick={finish} disabled={busy || !riskAck}>
                {busy ? "Launching…" : "Launch FinAgent"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
