import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

export function TradingPage() {
  const [symbol, setSymbol] = useState("RELIANCE.NS");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [msg, setMsg] = useState("");

  async function refresh() {
    const res = await api<{ orders: Record<string, unknown>[] }>("/api/trading/blotter");
    setOrders(res.orders);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function place() {
    setMsg("");
    let px = price;
    if (!px) {
      const q = await api<{ price: string }>(`/api/market/quote/${encodeURIComponent(symbol)}`);
      px = q.price;
      setPrice(px);
    }
    const res = await api<{ ok: boolean; error?: string; order?: Record<string, unknown> }>("/api/trading/order", {
      method: "POST",
      body: JSON.stringify({
        symbol,
        side,
        quantity: qty,
        price: px,
        asset_class: symbol.includes("/") ? "crypto" : "equity",
        confirmed: true,
      }),
    });
    setMsg(res.ok ? `Order ${String(res.order?.status)}` : res.error || "Failed");
    await refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Paper trading</h1>
        <p className="text-sm text-muted-foreground">Kite-style ticket · risk limits enforced server-side</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Order ticket</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-amber-200/90 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
              Paper trading only on this screen by default. Not financial advice. You can lose money
              in real markets — live mode requires re-auth in Settings.
            </p>
            <div className="flex gap-2">
              <Button variant={side === "buy" ? "default" : "outline"} className={side === "buy" ? "bg-up" : ""} onClick={() => setSide("buy")}>Buy</Button>
              <Button variant={side === "sell" ? "destructive" : "outline"} onClick={() => setSide("sell")}>Sell</Button>
            </div>
            <div className="space-y-1"><Label>Symbol</Label><Input value={symbol} onChange={(e) => setSymbol(e.target.value)} /></div>
            <div className="space-y-1"><Label>Quantity</Label><Input value={qty} onChange={(e) => setQty(e.target.value)} /></div>
            <div className="space-y-1"><Label>Price (blank = last quote)</Label><Input value={price} onChange={(e) => setPrice(e.target.value)} /></div>
            <Button onClick={place}>Place paper order</Button>
            {msg && <p className="text-sm">{msg}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Blotter</CardTitle>
            <Button size="sm" variant="secondary" onClick={() => api("/api/trading/paper/reset", { method: "POST" }).then(refresh)}>Reset paper</Button>
          </CardHeader>
          <CardContent className="space-y-2 max-h-96 overflow-auto">
            {orders.map((o) => (
              <div key={String(o.idempotency_key)} className="text-xs font-mono border-b border-border/50 py-2 flex justify-between gap-2">
                <span>{String(o.side)} {String(o.quantity)} {String(o.symbol)}</span>
                <span>{String(o.status)} @ {o.avg_fill_price ? formatNumber(String(o.avg_fill_price)) : "—"}</span>
              </div>
            ))}
            {orders.length === 0 && <p className="text-sm text-muted-foreground">No orders yet</p>}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}