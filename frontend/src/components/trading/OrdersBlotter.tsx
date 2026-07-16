import { useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn, formatNumber } from "@/lib/utils";

type Filter = "all" | "open" | "filled";

function isCancellable(status: unknown): boolean {
  const s = String(status || "").toLowerCase();
  return ["open", "submitted", "new", "pending", "accepted", "partially_filled"].includes(s);
}

function isOpen(status: unknown): boolean {
  return isCancellable(status);
}

function isFilled(status: unknown): boolean {
  const s = String(status || "").toLowerCase();
  return s === "filled" || s === "complete" || s === "completed";
}

type Props = {
  orders: Record<string, unknown>[];
  mode: string;
  onRefresh: () => void | Promise<void>;
  onCancel: (orderId: string) => void | Promise<void>;
  onResetPaper?: () => void | Promise<void>;
};

export function OrdersBlotter({ orders, mode, onRefresh, onCancel, onResetPaper }: Props) {
  const [filter, setFilter] = useState<Filter>("all");

  const filtered = useMemo(() => {
    if (filter === "open") return orders.filter((o) => isOpen(o.status));
    if (filter === "filled") return orders.filter((o) => isFilled(o.status));
    return orders;
  }, [orders, filter]);

  const chips: { key: Filter; label: string }[] = [
    { key: "all", label: "All" },
    { key: "open", label: "Open" },
    { key: "filled", label: "Filled" },
  ];

  return (
    <div
      className="rounded-lg border border-border/60 bg-card/30 flex flex-col min-h-[10rem]"
      data-testid="orders-blotter"
    >
      <div className="flex flex-wrap items-center justify-between gap-2 px-2 py-1.5 border-b border-border/50">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted-foreground">
            {mode === "live" ? "Broker orders" : "Blotter"}
          </span>
          <div className="flex gap-0.5">
            {chips.map((c) => (
              <button
                key={c.key}
                type="button"
                className={cn(
                  "px-1.5 py-0.5 text-[10px] rounded border",
                  filter === c.key
                    ? "bg-accent border-primary/40"
                    : "border-border text-muted-foreground hover:bg-accent/40",
                )}
                onClick={() => setFilter(c.key)}
              >
                {c.label}
              </button>
            ))}
          </div>
        </div>
        <div className="flex gap-1">
          <Button size="sm" variant="outline" className="h-7 text-[11px]" onClick={() => void onRefresh()}>
            Refresh
          </Button>
          {mode !== "live" && onResetPaper && (
            <Button size="sm" variant="secondary" className="h-7 text-[11px]" onClick={() => void onResetPaper()}>
              Reset paper
            </Button>
          )}
        </div>
      </div>
      <div className="flex-1 overflow-auto max-h-48 text-xs p-2 space-y-1">
        {filtered.map((o) => {
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
                  className="text-[11px] underline text-red-400 shrink-0"
                  onClick={() => void onCancel(id)}
                >
                  Cancel
                </button>
              )}
            </div>
          );
        })}
        {filtered.length === 0 && (
          <p className="text-muted-foreground text-xs">No orders yet.</p>
        )}
      </div>
    </div>
  );
}
