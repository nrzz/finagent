import { useEffect, useState, type Ref } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

type Side = "buy" | "sell";

type Props = {
  symbol: string;
  onSymbolChange: (symbol: string) => void;
  side: Side;
  onSideChange: (side: Side) => void;
  ltp?: string | number | null;
  cash?: string | number | null;
  buyingPower?: string | number | null;
  onPlaced?: () => void | Promise<void>;
  symbolInputRef?: Ref<HTMLInputElement>;
  qtyInputRef?: Ref<HTMLInputElement>;
};

export function OrderTicket({
  symbol,
  onSymbolChange,
  side,
  onSideChange,
  ltp,
  cash,
  buyingPower,
  onPlaced,
  symbolInputRef,
  qtyInputRef,
}: Props) {
  const [qty, setQty] = useState("1");
  const [price, setPrice] = useState("");
  const [triggerPrice, setTriggerPrice] = useState("");
  const [orderType, setOrderType] = useState("market");
  const [product, setProduct] = useState("CNC");
  const [symbolToken, setSymbolToken] = useState("");
  const [broker, setBroker] = useState("");
  const [mode, setMode] = useState("paper");
  const [confirmNeeded, setConfirmNeeded] = useState(true);
  const [pendingConfirm, setPendingConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");

  const angelLive = mode === "live" && broker === "angel";
  const angelTokenMissing = angelLive && !symbolToken.trim();
  const ltpNum = ltp != null && ltp !== "" ? Number(ltp) : NaN;
  const pxNum = price.trim() ? Number(price) : ltpNum;
  const qtyNum = Number(qty) || 0;
  const notional =
    Number.isFinite(pxNum) && qtyNum > 0 ? pxNum * qtyNum : null;

  useEffect(() => {
    api<{
      settings: {
        trading: {
          mode: string;
          require_order_confirmation?: boolean;
          default_broker?: string;
        };
      };
    }>("/api/settings")
      .then((s) => {
        setMode(s.settings.trading.mode);
        setConfirmNeeded(s.settings.trading.require_order_confirmation !== false);
        setBroker(s.settings.trading.default_broker || "");
      })
      .catch(() => undefined);
  }, []);

  async function place(confirmed: boolean) {
    if (busy) return;
    setMsg("");
    setBusy(true);
    try {
      if (angelTokenMissing) {
        setMsg("Angel live orders need an instrument symbol_token before placing.");
        return;
      }
      let px = price;
      if (!px) {
        if (ltp != null && String(ltp)) {
          px = String(ltp);
          setPrice(px);
        } else {
          const q = await api<{ price: string }>(`/api/market/quote/${encodeURIComponent(symbol)}`);
          px = q.price;
          setPrice(px);
        }
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
      if (orderType === "SL") {
        meta.trigger_price = triggerPrice || px;
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
      if (res.ok) await onPlaced?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Order failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-lg border border-border/60 bg-card/30 p-3 space-y-3 h-full" data-testid="order-ticket">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">Order ticket</h3>
        <span className="text-[10px] text-muted-foreground uppercase tracking-wide">
          {mode === "live" ? `Live · ${broker || "broker"}` : "Paper"}
        </span>
      </div>
      <p className="text-[11px] text-amber-200/90 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5">
        Not financial advice. Live mode requires Settings re-auth. Use Panic Stop to block all orders.
      </p>
      <div className="flex gap-2">
        <Button
          variant={side === "buy" ? "default" : "outline"}
          className={side === "buy" ? "bg-up flex-1" : "flex-1"}
          size="sm"
          onClick={() => onSideChange("buy")}
        >
          Buy
        </Button>
        <Button
          variant={side === "sell" ? "destructive" : "outline"}
          className="flex-1"
          size="sm"
          onClick={() => onSideChange("sell")}
        >
          Sell
        </Button>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Symbol</Label>
        <Input
          ref={symbolInputRef}
          data-testid="ticket-symbol"
          className="h-9 font-mono text-sm"
          value={symbol}
          onChange={(e) => onSymbolChange(e.target.value.toUpperCase())}
        />
      </div>
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-xs">Quantity</Label>
          <Input
            ref={qtyInputRef}
            data-testid="ticket-qty"
            className="h-9"
            value={qty}
            onChange={(e) => setQty(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">LTP</Label>
          <div className="h-9 flex items-center px-2 rounded-md border border-input bg-muted/30 font-mono text-sm tabular-nums">
            {ltp != null && String(ltp) !== "" ? formatNumber(String(ltp)) : "…"}
          </div>
        </div>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Order type</Label>
        <select
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          value={orderType}
          onChange={(e) => setOrderType(e.target.value)}
        >
          <option value="market">Market</option>
          <option value="limit">Limit</option>
          <option value="SL">Stop-limit (SL)</option>
        </select>
      </div>
      <div className="space-y-1">
        <Label className="text-xs">Price (blank = LTP)</Label>
        <Input
          data-testid="ticket-price"
          className="h-9"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
        />
      </div>
      {orderType === "SL" && (
        <div className="space-y-1">
          <Label className="text-xs">Trigger price</Label>
          <Input
            className="h-9"
            value={triggerPrice}
            onChange={(e) => setTriggerPrice(e.target.value)}
            placeholder="Stop trigger"
          />
        </div>
      )}
      <div className="space-y-1">
        <Label className="text-xs">India product</Label>
        <select
          className="h-9 w-full rounded-md border border-input bg-background px-2 text-sm"
          value={product}
          onChange={(e) => setProduct(e.target.value)}
        >
          <option value="CNC">CNC</option>
          <option value="MIS">MIS</option>
          <option value="NRML">NRML</option>
        </select>
      </div>
      <div className="text-[11px] text-muted-foreground font-mono space-y-0.5">
        <div>Notional {notional != null ? formatNumber(notional) : "—"}</div>
        {cash != null && cash !== "" && <div>Cash {formatNumber(String(cash))}</div>}
        {buyingPower != null && buyingPower !== "" && (
          <div>Buying power {formatNumber(String(buyingPower))}</div>
        )}
      </div>
      {angelLive && (
        <>
          <p className="text-[11px] text-amber-200/90 rounded-md border border-amber-500/30 bg-amber-500/10 px-2 py-1.5">
            Angel live orders need the instrument <span className="font-mono">symbol_token</span>{" "}
            (advanced). Without it, live placement from this ticket is blocked.
          </p>
          <div className="space-y-1">
            <Label className="text-xs">Symbol token</Label>
            <Input
              className="h-9"
              value={symbolToken}
              onChange={(e) => setSymbolToken(e.target.value)}
              placeholder="Angel instrument token"
            />
          </div>
        </>
      )}
      {!pendingConfirm ? (
        <Button
          data-testid="ticket-submit"
          className="w-full"
          onClick={() => void place(false)}
          disabled={angelTokenMissing || busy}
        >
          {busy ? "…" : mode === "live" ? "Place live order" : "Place paper order"}
        </Button>
      ) : (
        <div className="flex gap-2">
          <Button
            data-testid="ticket-submit"
            className="flex-1"
            onClick={() => void place(true)}
            disabled={angelTokenMissing || busy}
          >
            {busy ? "…" : "Confirm"}
          </Button>
          <Button
            variant="outline"
            className="flex-1"
            disabled={busy}
            onClick={() => setPendingConfirm(false)}
          >
            Cancel
          </Button>
        </div>
      )}
      {msg && <p className="text-xs">{msg}</p>}
      {symbol.trim() && (
        <Button asChild variant="ghost" size="sm" className="w-full h-8 text-xs text-muted-foreground">
          <Link to={`/automation?symbol=${encodeURIComponent(symbol.trim())}`}>Alert on symbol</Link>
        </Button>
      )}
    </div>
  );
}
