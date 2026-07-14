import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/utils";
import { cn } from "@/lib/utils";

type ToolEvent = {
  tool?: string;
  ok?: boolean;
  result?: Record<string, unknown>;
  error?: string;
};

type Draft = {
  symbol: string;
  side: string;
  quantity: string;
  price: string;
  asset_class?: string;
  idempotency_key?: string | null;
};

type Props = {
  tools?: unknown[];
  onConfirmOrder?: (draft: Draft) => void;
  onCancelOrder?: (draft: Draft) => void;
  confirmingKey?: string | null;
};

function asNum(v: unknown): string {
  if (v == null) return "—";
  return formatNumber(String(v));
}

export function ToolResultCards({ tools, onConfirmOrder, onCancelOrder, confirmingKey }: Props) {
  if (!tools?.length) return null;

  return (
    <div className="mt-3 space-y-2 border-t border-border/40 pt-2">
      {tools.map((raw, j) => {
        const t = raw as ToolEvent;
        const result = (t.result || {}) as Record<string, unknown>;
        const name = t.tool || "tool";

        if (name === "get_quote" && result.symbol) {
          const change = Number(result.change_pct ?? result.changePercent ?? NaN);
          return (
            <div key={j} className="rounded-xl border border-border/60 bg-background/50 p-3">
              <div className="flex items-baseline justify-between gap-2">
                <div>
                  <div className="text-xs text-muted-foreground">Quote</div>
                  <div className="font-semibold">{String(result.symbol)}</div>
                </div>
                <div className="text-right">
                  <div className="text-lg font-semibold tabular-nums">{asNum(result.price)}</div>
                  {!Number.isNaN(change) && (
                    <div className={cn("text-xs", change >= 0 ? "text-emerald-400" : "text-red-400")}>
                      {change >= 0 ? "+" : ""}
                      {formatNumber(change)}%
                    </div>
                  )}
                </div>
              </div>
              <div className="mt-2 text-[10px] text-muted-foreground font-mono">
                {String(result.source || "market")} · {String(result.as_of || result.timestamp || "")}
              </div>
            </div>
          );
        }

        if (name === "get_portfolio") {
          const positions = (result.positions as unknown[]) || [];
          return (
            <div key={j} className="rounded-xl border border-border/60 bg-background/50 p-3 space-y-2">
              <div className="text-xs text-muted-foreground">Portfolio</div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <div className="text-[10px] text-muted-foreground">Cash</div>
                  <div className="font-medium tabular-nums">
                    {asNum(result.cash)} {String(result.currency || "")}
                  </div>
                </div>
                <div>
                  <div className="text-[10px] text-muted-foreground">Equity</div>
                  <div className="font-medium tabular-nums">{asNum(result.equity)}</div>
                </div>
              </div>
              {positions.length > 0 && (
                <div className="text-xs space-y-1 max-h-28 overflow-auto">
                  {positions.slice(0, 8).map((p, i) => {
                    const row = p as Record<string, unknown>;
                    return (
                      <div key={i} className="flex justify-between font-mono text-muted-foreground">
                        <span>{String(row.symbol)}</span>
                        <span>{String(row.quantity ?? row.qty ?? "")}</span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        }

        if (name === "place_paper_order" && result.pending_confirmation && result.draft) {
          const draft = result.draft as Draft;
          const key = `${draft.side}-${draft.quantity}-${draft.symbol}-${draft.price}`;
          return (
            <div key={j} className="rounded-xl border border-amber-500/40 bg-amber-500/10 p-3 space-y-2">
              <div className="text-xs font-medium text-amber-200">Confirm paper trade</div>
              <div className="text-sm">
                <span className="uppercase font-semibold">{draft.side}</span> {draft.quantity}{" "}
                <span className="font-mono">{draft.symbol}</span>
                {draft.price && draft.price !== "0" ? ` @ ${asNum(draft.price)}` : " @ market"}
              </div>
              <p className="text-[11px] text-muted-foreground leading-relaxed">
                {String(result.warning || "Paper only. Not financial advice. You can lose money in markets.")}
              </p>
              <div className="flex gap-2">
                <Button
                  size="sm"
                  disabled={confirmingKey === key}
                  onClick={() => onConfirmOrder?.(draft)}
                >
                  {confirmingKey === key ? "Placing…" : "Confirm"}
                </Button>
                <Button size="sm" variant="outline" onClick={() => onCancelOrder?.(draft)}>
                  Cancel
                </Button>
              </div>
            </div>
          );
        }

        if (name === "place_paper_order" && (result.status || result.id)) {
          return (
            <div key={j} className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-3 text-sm">
              <div className="text-xs text-muted-foreground">Order filled (paper)</div>
              <div className="font-medium">
                {String(result.side)} {String(result.quantity)} {String(result.symbol)} ·{" "}
                {String(result.status)}
              </div>
            </div>
          );
        }

        if (name === "run_screener") {
          const quotes = (result.quotes as Record<string, unknown>[]) || [];
          return (
            <div key={j} className="rounded-xl border border-border/60 bg-background/50 p-3 space-y-2">
              <div className="text-xs text-muted-foreground">
                Screener · {String(result.universe || "watchlist")}
              </div>
              <div className="space-y-1 max-h-40 overflow-auto">
                {quotes.slice(0, 10).map((q, i) => (
                  <div key={i} className="flex justify-between text-xs font-mono">
                    <span>{String(q.symbol || q.error || "—")}</span>
                    <span>{q.price != null ? asNum(q.price) : "err"}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        }

        if (name === "get_option_chain") {
          return (
            <div key={j} className="rounded-xl border border-border/60 bg-background/50 p-3 text-xs">
              <div className="text-muted-foreground mb-1">Option chain</div>
              <div className="font-mono truncate">{String(result.symbol || "underlying")}</div>
              <div className="text-muted-foreground mt-1">
                {Array.isArray(result.expirations)
                  ? `${(result.expirations as unknown[]).length} expirations`
                  : Array.isArray(result.calls)
                    ? `${(result.calls as unknown[]).length} calls`
                    : "See assistant summary"}
              </div>
            </div>
          );
        }

        return (
          <div key={j} className="text-xs font-mono text-muted-foreground">
            tool · {name} · {t.ok === false ? "error" : "ok"}
            {t.error ? ` · ${t.error}` : ""}
          </div>
        );
      })}
    </div>
  );
}
