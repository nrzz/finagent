import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

type OptionRow = {
  strike?: number | string;
  type?: string;
  option_type?: string;
  last?: number | string;
  lastPrice?: number | string;
  bid?: number | string;
};

type Chain = {
  symbol: string;
  expiries?: string[];
  selected_expiry?: string;
  calls?: OptionRow[];
  puts?: OptionRow[];
  options?: OptionRow[];
  note?: string;
};

const EMPTY_CHAIN_NOTE =
  "Chain unavailable from free data — try US underlyings or use paper ticket with manual premium";

function rowType(r: OptionRow, fallback: "CE" | "PE"): string {
  const t = String(r.type ?? r.option_type ?? fallback).toUpperCase();
  if (t === "CALL" || t === "C") return "CE";
  if (t === "PUT" || t === "P") return "PE";
  return t || fallback;
}

function rowLast(r: OptionRow): string | null {
  const v = r.last ?? r.lastPrice ?? r.bid;
  return v != null && v !== "" ? String(v) : null;
}

type Props = {
  underlying?: string;
  onUnderlyingChange?: (u: string) => void;
  onStrikeSelect?: (strike: string, type: "CE" | "PE", premium: string, expiry: string) => void;
};

export function OptionChainPanel({
  underlying: underlyingProp,
  onUnderlyingChange,
  onStrikeSelect,
}: Props) {
  const [underlyingLocal, setUnderlyingLocal] = useState("NIFTY");
  const underlying = underlyingProp ?? underlyingLocal;
  const setUnderlying = (v: string) => {
    if (onUnderlyingChange) onUnderlyingChange(v);
    else setUnderlyingLocal(v);
  };

  const [chain, setChain] = useState<Chain | null>(null);
  const [expiry, setExpiry] = useState("");
  const [strike, setStrike] = useState("");
  const [optType, setOptType] = useState<"CE" | "PE">("CE");
  const [premium, setPremium] = useState("");
  const [lots, setLots] = useState("1");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [greeks, setGreeks] = useState<Record<string, unknown> | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [chainLoaded, setChainLoaded] = useState(false);

  const tableRows = useMemo(() => {
    if (!chain) return [];
    if (Array.isArray(chain.options) && chain.options.length > 0) {
      return chain.options.map((r) => ({
        strike: r.strike,
        type: rowType(r, "CE"),
        last: rowLast(r),
        raw: r,
      }));
    }
    const source = optType === "CE" ? chain.calls || [] : chain.puts || [];
    return source.map((r) => ({
      strike: r.strike,
      type: optType,
      last: rowLast(r),
      raw: r,
    }));
  }, [chain, optType]);

  const chainEmpty = chainLoaded && tableRows.length === 0;
  const hasFlatOptions = Array.isArray(chain?.options) && (chain?.options?.length ?? 0) > 0;

  async function loadChain() {
    setMsg("");
    setChainLoaded(false);
    try {
      const sym = underlying.toUpperCase().includes("^") ? underlying : `^${underlying}`;
      let res: Chain;
      try {
        res = await api(`/api/market/options/${encodeURIComponent(underlying.toUpperCase())}`);
      } catch {
        res = await api(`/api/market/options/${encodeURIComponent(sym)}`);
      }
      setChain(res);
      setChainLoaded(true);
      const ex = res.selected_expiry || res.expiries?.[0] || "";
      setExpiry(ex);
      const flat = res.options?.[0];
      const first = flat || (res.calls || res.puts || [])[0];
      if (first?.strike != null) setStrike(String(first.strike));
      const last = rowLast(first || {});
      if (last != null) setPremium(last);
    } catch (e) {
      setChain(null);
      setChainLoaded(true);
      setMsg(e instanceof Error ? e.message : "Failed to load chain");
    }
  }

  async function calcGreeks() {
    setMsg("");
    try {
      let spot = 22000;
      let spotIsEstimate = true;
      try {
        const controller = new AbortController();
        const timer = window.setTimeout(() => controller.abort(), 5_000);
        const q = await api<{ price: string }>(
          `/api/market/quote/${encodeURIComponent(
            underlying.includes(".") || underlying.startsWith("^")
              ? underlying
              : `${underlying}.NS`,
          )}`,
          { signal: controller.signal },
        );
        window.clearTimeout(timer);
        const px = Number(q.price);
        if (px) {
          spot = px;
          spotIsEstimate = false;
        }
      } catch {
        /* illustrative fallback */
      }
      const res = await api<Record<string, unknown>>("/api/trading/fno/greeks", {
        method: "POST",
        body: JSON.stringify({
          spot,
          strike: Number(strike) || 22000,
          t_years: 0.08,
          iv: 0.18,
          option_type: optType,
          underlying: underlying.replace("^", "").replace(".NS", ""),
          premium: Number(premium) || undefined,
          quantity_lots: Number(lots) || 1,
        }),
      });
      setGreeks({ ...res, _spot: spot, _spotIsEstimate: spotIsEstimate });
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Greeks failed");
    }
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
            side,
            quantity_lots: Number(lots) || 1,
            premium: premium || "1",
            confirmed: true,
          }),
        },
      );
      setMsg(
        res.ok
          ? `Paper option ${String(res.order?.status)} · ${String(res.order?.symbol)}`
          : res.error || "Failed",
      );
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Order failed");
    } finally {
      setBusy(false);
    }
  }

  function selectRow(r: { strike?: number | string; type: string; last: string | null }) {
    const s = String(r.strike ?? "");
    const t: "CE" | "PE" = r.type === "PE" ? "PE" : "CE";
    const prem = r.last ?? premium;
    setStrike(s);
    setOptType(t);
    if (r.last != null) setPremium(r.last);
    onStrikeSelect?.(s, t, prem || "", expiry);
  }

  return (
    <div className="space-y-3" data-testid="option-chain-panel">
      <div className="flex flex-wrap gap-2 items-end">
        <div className="space-y-1 flex-1 min-w-[10rem]">
          <Label className="text-xs">Underlying</Label>
          <Input
            className="h-9"
            value={underlying}
            onChange={(e) => setUnderlying(e.target.value.toUpperCase())}
            placeholder="NIFTY / AAPL"
          />
        </div>
        <Button size="sm" className="h-9" onClick={() => void loadChain()}>
          Load chain
        </Button>
      </div>
      <p className="text-[11px] text-muted-foreground">
        Option chain + greeks/margin that are{" "}
        <strong>educational — not exchange SPAN</strong>. Paper only — not financial advice.
      </p>

      <div className="grid gap-3 lg:grid-cols-2">
        <Card className="border-border/60">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-sm">Chain</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-2">
            {!hasFlatOptions && (
              <div className="flex gap-2 flex-wrap">
                <select
                  className="h-8 rounded-md border border-input bg-background px-2 text-xs"
                  value={expiry}
                  onChange={(e) => setExpiry(e.target.value)}
                >
                  {(chain?.expiries || []).map((e) => (
                    <option key={e} value={e}>
                      {e}
                    </option>
                  ))}
                </select>
                <Button size="sm" variant={optType === "CE" ? "default" : "outline"} onClick={() => setOptType("CE")}>
                  CE
                </Button>
                <Button size="sm" variant={optType === "PE" ? "default" : "outline"} onClick={() => setOptType("PE")}>
                  PE
                </Button>
              </div>
            )}
            {tableRows.length > 0 ? (
              <div className="max-h-56 overflow-auto text-xs">
                <table className="w-full font-mono border-collapse">
                  <thead className="sticky top-0 bg-card text-muted-foreground text-left">
                    <tr>
                      <th className="py-1 px-1 font-medium">Strike</th>
                      <th className="py-1 px-1 font-medium">Type</th>
                      <th className="py-1 px-1 font-medium text-right">Last</th>
                    </tr>
                  </thead>
                  <tbody>
                    {tableRows.slice(0, 40).map((r, i) => (
                      <tr
                        key={i}
                        className="border-b border-border/40 hover:bg-accent/40 cursor-pointer"
                        onClick={() => selectRow(r)}
                      >
                        <td className="py-1 px-1">{String(r.strike ?? "—")}</td>
                        <td className="py-1 px-1">{r.type}</td>
                        <td className="py-1 px-1 text-right">
                          {r.last != null ? formatNumber(r.last) : "—"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-xs text-muted-foreground">
                {chainEmpty ? EMPTY_CHAIN_NOTE : "Load a chain to see strikes."}
              </p>
            )}
          </CardContent>
        </Card>

        <Card data-testid="fno-ticket" className="border-border/60">
          <CardHeader className="p-3 pb-2">
            <CardTitle className="text-sm">Paper ticket</CardTitle>
          </CardHeader>
          <CardContent className="p-3 pt-0 space-y-2">
            <div className="flex gap-2">
              <Button
                size="sm"
                variant={side === "buy" ? "default" : "outline"}
                className={side === "buy" ? "bg-up flex-1" : "flex-1"}
                onClick={() => setSide("buy")}
              >
                Buy
              </Button>
              <Button
                size="sm"
                variant={side === "sell" ? "destructive" : "outline"}
                className="flex-1"
                onClick={() => setSide("sell")}
              >
                Sell
              </Button>
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Expiry</Label>
              <Input
                data-testid="fno-expiry"
                className="h-8 text-sm"
                value={expiry}
                onChange={(e) => setExpiry(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Strike</Label>
              <Input
                data-testid="fno-strike"
                className="h-8 text-sm"
                value={strike}
                onChange={(e) => setStrike(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Premium</Label>
              <Input
                data-testid="fno-premium"
                className="h-8 text-sm"
                value={premium}
                onChange={(e) => setPremium(e.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">Lots</Label>
              <Input
                data-testid="fno-lots"
                className="h-8 text-sm"
                value={lots}
                onChange={(e) => setLots(e.target.value)}
              />
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button size="sm" variant="secondary" onClick={() => void calcGreeks()}>
                Greeks / educational margin
              </Button>
              <Button size="sm" onClick={() => void place()} disabled={busy || !expiry || !strike}>
                {busy ? "…" : side === "buy" ? "Buy paper" : "Sell paper"}
              </Button>
            </div>
            {greeks && (
              <div className="text-xs space-y-1 rounded-md border p-2 bg-muted/30">
                <p className="text-amber-200/90 font-medium">
                  Educational estimates — not exchange SPAN
                </p>
                <div>
                  Spot {formatNumber(String(greeks._spot))}
                  {greeks._spotIsEstimate ? " (estimate)" : ""}
                </div>
                <div>
                  Δ {Number(greeks.delta).toFixed(3)} · Γ {Number(greeks.gamma).toFixed(5)}
                </div>
                <div>
                  Θ {Number(greeks.theta).toFixed(3)} · Vega {Number(greeks.vega).toFixed(3)}
                </div>
                <div>
                  Lot {String(greeks.lot_size)} ·{" "}
                  <span className="text-amber-200/90">Educational margin estimate</span>
                  {" ~ "}
                  {formatNumber(String(greeks.margin_estimate))}
                </div>
                <p className="text-muted-foreground">{String(greeks.disclaimer || "")}</p>
              </div>
            )}
            {msg && <p className="text-xs">{msg}</p>}
            <p className="text-[10px] text-amber-200/90">
              Expired paper options are auto square-off by the scheduler (illustrative).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
