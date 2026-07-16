import type { QuoteDict } from "@/lib/marketStream";
import { cn, formatNumber } from "@/lib/utils";

export type PositionRow = {
  symbol: string;
  quantity?: string | number;
  market_value?: string | number;
  unrealized_pnl?: string | number;
  avg_cost?: string | number;
  mark?: string | number;
};

type Props = {
  positions: PositionRow[];
  quotes?: Record<string, QuoteDict>;
  onSelect?: (symbol: string) => void;
};

export function PositionsPanel({ positions, quotes = {}, onSelect }: Props) {
  return (
    <div
      className="rounded-lg border border-border/60 bg-card/30 flex flex-col min-h-[10rem]"
      data-testid="positions-panel"
    >
      <div className="px-2 py-1.5 border-b border-border/50 text-xs font-medium text-muted-foreground">
        Positions
      </div>
      <div className="flex-1 overflow-auto max-h-48">
        {positions.length === 0 ? (
          <p className="text-xs text-muted-foreground p-3">No open positions.</p>
        ) : (
          <table className="w-full text-[11px] font-mono">
            <thead className="sticky top-0 bg-card text-muted-foreground text-left">
              <tr>
                <th className="py-1 px-2 font-medium">Symbol</th>
                <th className="py-1 px-1 font-medium text-right">Qty</th>
                <th className="py-1 px-1 font-medium text-right">LTP</th>
                <th className="py-1 px-1 font-medium text-right">Mkt</th>
                <th className="py-1 px-2 font-medium text-right">uPnL</th>
              </tr>
            </thead>
            <tbody>
              {positions.map((p) => {
                const q = quotes[p.symbol];
                const ltp = q?.price ?? p.mark;
                const qty = p.quantity != null ? Number(p.quantity) : NaN;
                const avg = p.avg_cost != null ? Number(p.avg_cost) : NaN;
                const ltpN = ltp != null ? Number(ltp) : NaN;
                const uPnL =
                  p.unrealized_pnl != null
                    ? Number(p.unrealized_pnl)
                    : Number.isFinite(qty) && Number.isFinite(avg) && Number.isFinite(ltpN)
                      ? (ltpN - avg) * qty
                      : null;
                const pct =
                  uPnL != null && Number.isFinite(avg) && Number.isFinite(qty) && avg * qty !== 0
                    ? (uPnL / (avg * qty)) * 100
                    : null;
                const mv =
                  p.market_value != null
                    ? Number(p.market_value)
                    : Number.isFinite(qty) && Number.isFinite(ltpN)
                      ? qty * ltpN
                      : null;
                return (
                  <tr
                    key={p.symbol}
                    className={cn(
                      "border-b border-border/30",
                      onSelect && "cursor-pointer hover:bg-accent/40",
                    )}
                    onClick={() => onSelect?.(p.symbol)}
                  >
                    <td className="py-1.5 px-2">{p.symbol}</td>
                    <td className="py-1.5 px-1 text-right">
                      {p.quantity != null ? formatNumber(String(p.quantity), "indian", 0) : "—"}
                    </td>
                    <td className="py-1.5 px-1 text-right">
                      {ltp != null ? formatNumber(String(ltp)) : "—"}
                    </td>
                    <td className="py-1.5 px-1 text-right">
                      {mv != null ? formatNumber(mv) : "—"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 px-2 text-right",
                        uPnL != null && uPnL >= 0 ? "text-up" : uPnL != null ? "text-down" : "",
                      )}
                    >
                      {uPnL != null ? formatNumber(uPnL) : "—"}
                      {pct != null ? ` (${pct >= 0 ? "+" : ""}${formatNumber(pct)}%)` : ""}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
