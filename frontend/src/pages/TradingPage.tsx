import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

function isCancellable(status: unknown): boolean {
  const s = String(status || "").toLowerCase();
  return ["open", "submitted", "new", "pending", "accepted", "partially_filled"].includes(s);
}

export function TradingPage() {
  const [symbol, setSymbol] = useState("RELIANCE.NS");
  const [side, setSide] = useState<"buy" | "sell">("buy");
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [orderType, setOrderType] = useState("market");
  const [product, setProduct] = useState("CNC");
  const [symbolToken, setSymbolToken] = useState("");
  const [broker, setBroker] = useState("");
  const [mode, setMode] = useState("paper");
  const [confirmNeeded, setConfirmNeeded] = useState(true);
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [msg, setMsg] = useState("");

  const angelLive = mode === "live" && broker === "angel";
  const angelTokenMissing = angelLive && !symbolToken.trim();

  async function refresh() {
    let tradingMode = mode;
    try {
      const s = await api<{
        settings: {
          trading: {
            mode: string;
            require_order_confirmation?: boolean;
            default_broker?: string;
          };
        };
      }>("/api/settings");
      tradingMode = s.settings.trading.mode;
      setMode(tradingMode);
      setConfirmNeeded(s.settings.trading.require_order_confirmation !== false);
      setBroker(s.settings.trading.default_broker || "");
    } catch {
      /* ignore */
    }
    const endpoint = tradingMode === "live" ? "/api/trading/orders" : "/api/trading/blotter";
    const res = await api<{ orders: Record<string, unknown>[] }>(endpoint);
    setOrders(res.orders || []);
  }

  useEffect(() => {
    refresh().catch(() => undefined);
  }, []);

  async function place(confirmed: boolean) {
    setMsg("");
    try {
      if (angelTokenMissing) {
        setMsg("Angel live orders need an instrument symbol_token before placing.");
        return;
      }
      let px = price;
      if (!px) {
        const q = await api<{ price: string }>(`/api/market/quote/${encodeURIComponent(symbol)}`);
        px = q.price;
        setPrice(px);
      }
      if (confirmNeeded && mode === "live" && !confirmed) {
        setPendingConfirm(true);
        setMsg("Live order — review, then Confirm.");
        return;
      }
      const meta: Record<string, string> = { product, mark_price: px };
      if (angelLive && symbolToken.trim()) {
        meta.symbol_token = symbolToken.trim();
      }
      const res = await api<{ ok: boolean; error?: string; order?: Record<string, unknown>; broker?: string }>(
        "/api/trading/order",
        {
          method: "POST",
          body: JSON.stringify({
            symbol,
            side,
            quantity: qty,
            price: px,
            order_type: orderType,
            asset_class: symbol.includes("/") ? "crypto" : "equity",
            confirmed: true,
            broker_name: mode === "live" ? broker || undefined : undefined,
            meta,
          }),
        },
      );
      setPendingConfirm(false);
      setMsg(
        res.ok
          ? `Order ${String(res.order?.status || "filled")} via ${res.broker || mode}`
          : res.error || "Failed",
      );
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Order failed");
    }
  }

  async function cancelOrder(orderId: string) {
    setMsg("");
    try {
      const res = await api<{ ok?: boolean; error?: string }>(
        `/api/trading/orders/${encodeURIComponent(orderId)}/cancel`,
        { method: "POST" },
      );
      setMsg(res.ok === false ? res.error || "Cancel failed" : "Cancel requested");
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Cancel failed");
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{mode === "live" ? "Live trading" : "Paper trading"}</h1>
        <p className="text-sm text-muted-foreground">
          {mode === "live"
            ? `Live via ${broker || "default broker"} — real money. Confirm every order.`
            : "Practice ticket · risk limits enforced server-side"}
        </p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Order ticket</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-xs text-amber-200/90 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
              Not financial advice. Live mode requires Settings re-auth. Use Panic Stop to block all orders.
            </p>
            <div className="flex gap-2">
              <Button
                variant={side === "buy" ? "default" : "outline"}
                className={side === "buy" ? "bg-up" : ""}
                onClick={() => setSide("buy")}
              >
                Buy
              </Button>
              <Button
                variant={side === "sell" ? "destructive" : "outline"}
                onClick={() => setSide("sell")}
              >
                Sell
              </Button>
            </div>
            <div className="space-y-1">
              <Label>Symbol</Label>
              <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Quantity</Label>
              <Input value={qty} onChange={(e) => setQty(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>Order type</Label>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={orderType}
                onChange={(e) => setOrderType(e.target.value)}
              >
                <option value="market">Market</option>
                <option value="limit">Limit</option>
                <option value="SL">Stop-limit (SL)</option>
              </select>
            </div>
            <div className="space-y-1">
              <Label>Price (blank = last quote)</Label>
              <Input value={price} onChange={(e) => setPrice(e.target.value)} />
            </div>
            <div className="space-y-1">
              <Label>India product</Label>
              <select
                className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
                value={product}
                onChange={(e) => setProduct(e.target.value)}
              >
                <option value="CNC">CNC</option>
                <option value="MIS">MIS</option>
                <option value="NRML">NRML</option>
              </select>
            </div>
            {angelLive && (
              <>
                <p className="text-xs text-amber-200/90 rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2">
                  Angel live orders need the instrument <span className="font-mono">symbol_token</span>{" "}
                  (advanced). Without it, live placement from this ticket is blocked.
                </p>
                <div className="space-y-1">
                  <Label>Symbol token</Label>
                  <Input
                    value={symbolToken}
                    onChange={(e) => setSymbolToken(e.target.value)}
                    placeholder="Angel instrument token"
                  />
                </div>
              </>
            )}
            {!pendingConfirm ? (
              <Button onClick={() => place(false)} disabled={angelTokenMissing}>
                {mode === "live" ? "Place live order" : "Place paper order"}
              </Button>
            ) : (
              <div className="flex gap-2">
                <Button onClick={() => place(true)} disabled={angelTokenMissing}>
                  Confirm
                </Button>
                <Button variant="outline" onClick={() => setPendingConfirm(false)}>
                  Cancel
                </Button>
              </div>
            )}
            {msg && <p className="text-sm">{msg}</p>}
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{mode === "live" ? "Broker orders" : "Blotter"}</CardTitle>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => refresh()}>
                Refresh
              </Button>
              {mode !== "live" && (
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => api("/api/trading/paper/reset", { method: "POST" }).then(refresh)}
                >
                  Reset paper
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-2 max-h-96 overflow-auto text-sm">
            {orders.map((o) => {
              const id = String(o.id || o.order_id || o.idempotency_key || "");
              const status = o.status;
              return (
                <div
                  key={id || `${o.symbol}-${o.side}-${o.created_at}`}
                  className="font-mono border-b border-border/40 py-1 flex justify-between gap-2 items-center"
                >
                  <span>
                    {String(o.side)} {String(o.quantity ?? o.qty)} {String(o.symbol)} @{" "}
                    {formatNumber(Number(o.price || o.limit_price || 0))} · {String(status)}
                  </span>
                  {id && isCancellable(status) && (
                    <button
                      type="button"
                      className="text-xs underline text-red-400 shrink-0"
                      onClick={() => cancelOrder(id)}
                    >
                      Cancel
                    </button>
                  )}
                </div>
              );
            })}
            {orders.length === 0 && (
              <p className="text-muted-foreground text-sm">No orders yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
