import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

type Chain = {
  symbol: string;
  expiries?: string[];
  selected_expiry?: string;
  calls?: Record<string, unknown>[];
  puts?: Record<string, unknown>[];
};

export function FnoPage() {
  const [underlying, setUnderlying] = useState("NIFTY");
  const [chain, setChain] = useState<Chain | null>(null);
  const [expiry, setExpiry] = useState("");
  const [strike, setStrike] = useState("");
  const [optType, setOptType] = useState<"CE" | "PE">("CE");
  const [premium, setPremium] = useState("");
  const [lots, setLots] = useState("1");
  const [greeks, setGreeks] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  async function loadChain() {
    setMsg("");
    try {
      const sym = underlying.toUpperCase().includes("^") ? underlying : `^${underlying}`;
      // yfinance options use underlyings like ^NSEI for index; also try bare
      let res: Chain;
      try {
        res = await api(`/api/market/options/${encodeURIComponent(underlying.toUpperCase())}`);
      } catch {
        res = await api(`/api/market/options/${encodeURIComponent(sym)}`);
      }
      setChain(res);
      const ex = res.selected_expiry || res.expiries?.[0] || "";
      setExpiry(ex);
      const first = (res.calls || res.puts || [])[0];
      if (first?.strike != null) setStrike(String(first.strike));
      if (first?.lastPrice != null) setPremium(String(first.lastPrice));
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Failed to load chain");
    }
  }

  useEffect(() => {
    loadChain().catch(() => undefined);
  }, []);

  async function calcGreeks() {
    const spot = Number((await api<{ price: string }>(`/api/market/quote/${encodeURIComponent(underlying.includes(".") || underlying.startsWith("^") ? underlying : underlying + ".NS")}`).catch(() => ({ price: "0" }))).price);
    const res = await api<Record<string, unknown>>("/api/trading/fno/greeks", {
      method: "POST",
      body: JSON.stringify({
        spot: spot || 22000,
        strike: Number(strike) || 22000,
        t_years: 0.08,
        iv: 0.18,
        option_type: optType,
        underlying: underlying.replace("^", "").replace(".NS", ""),
        premium: Number(premium) || undefined,
        quantity_lots: Number(lots) || 1,
      }),
    });
    setGreeks(res);
  }

  async function place() {
    setBusy(true);
    setMsg("");
    try {
      const und = underlying.replace("^", "").replace(".NS", "").toUpperCase();
      const res = await api<{ ok: boolean; error?: string; order?: Record<string, unknown> }>(
        "/api/trading/fno/order",
        {
          method: "POST",
          body: JSON.stringify({
            underlying: und,
            expiry,
            strike,
            option_type: optType,
            side: "buy",
            quantity_lots: Number(lots) || 1,
            premium: premium || "1",
            confirmed: true,
          }),
        },
      );
      setMsg(res.ok ? `Paper option ${String(res.order?.status)} · ${String(res.order?.symbol)}` : res.error || "Failed");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Order failed");
    } finally {
      setBusy(false);
    }
  }

  const rows = optType === "CE" ? chain?.calls || [] : chain?.puts || [];

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-semibold">F&O (paper)</h1>
        <p className="text-sm text-muted-foreground">
          Option chain + illustrative margin/greeks. Paper only — not SPAN, not financial advice.
        </p>
      </div>

      <Card>
        <CardHeader><CardTitle>Underlying</CardTitle></CardHeader>
        <CardContent className="flex flex-wrap gap-2 items-end">
          <div className="space-y-1 flex-1 min-w-[10rem]">
            <Label>Symbol</Label>
            <Input value={underlying} onChange={(e) => setUnderlying(e.target.value.toUpperCase())} placeholder="NIFTY / BANKNIFTY" />
          </div>
          <Button onClick={loadChain}>Load chain</Button>
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Chain</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="flex gap-2 flex-wrap">
              <select
                className="h-10 rounded-md border border-input bg-background px-2 text-sm"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              >
                {(chain?.expiries || []).map((e) => (
                  <option key={e} value={e}>{e}</option>
                ))}
              </select>
              <Button size="sm" variant={optType === "CE" ? "default" : "outline"} onClick={() => setOptType("CE")}>CE</Button>
              <Button size="sm" variant={optType === "PE" ? "default" : "outline"} onClick={() => setOptType("PE")}>PE</Button>
            </div>
            <div className="max-h-72 overflow-auto text-xs font-mono space-y-1">
              {rows.slice(0, 40).map((r, i) => (
                <button
                  key={i}
                  type="button"
                  className="w-full flex justify-between border-b border-border/40 py-1 hover:bg-accent/40 text-left px-1"
                  onClick={() => {
                    setStrike(String(r.strike ?? ""));
                    setPremium(String(r.lastPrice ?? r.bid ?? ""));
                  }}
                >
                  <span>{String(r.strike)}</span>
                  <span>{r.lastPrice != null ? formatNumber(String(r.lastPrice)) : "—"}</span>
                </button>
              ))}
              {rows.length === 0 && <p className="text-muted-foreground">No rows — try another underlying or expiry.</p>}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Paper ticket</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1"><Label>Expiry</Label><Input value={expiry} onChange={(e) => setExpiry(e.target.value)} /></div>
            <div className="space-y-1"><Label>Strike</Label><Input value={strike} onChange={(e) => setStrike(e.target.value)} /></div>
            <div className="space-y-1"><Label>Premium</Label><Input value={premium} onChange={(e) => setPremium(e.target.value)} /></div>
            <div className="space-y-1"><Label>Lots</Label><Input value={lots} onChange={(e) => setLots(e.target.value)} /></div>
            <div className="flex gap-2 flex-wrap">
              <Button variant="secondary" onClick={calcGreeks}>Greeks / margin</Button>
              <Button onClick={place} disabled={busy || !expiry || !strike}>{busy ? "…" : "Buy paper"}</Button>
            </div>
            {greeks && (
              <div className="text-xs space-y-1 rounded-md border p-3 bg-muted/30">
                <div>Δ {Number(greeks.delta).toFixed(3)} · Γ {Number(greeks.gamma).toFixed(5)}</div>
                <div>Θ {Number(greeks.theta).toFixed(3)} · Vega {Number(greeks.vega).toFixed(3)}</div>
                <div>Lot {String(greeks.lot_size)} · Margin ~ {formatNumber(String(greeks.margin_estimate))}</div>
                <p className="text-muted-foreground">{String(greeks.disclaimer || "")}</p>
              </div>
            )}
            {msg && <p className="text-sm">{msg}</p>}
            <p className="text-[11px] text-amber-200/90">Expired paper options are auto square-off by the scheduler (illustrative).</p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
