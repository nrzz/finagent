import type { QuoteDict } from "@/lib/marketStream";
import { Badge } from "@/components/ui/primitives";
import { cn, formatNumber } from "@/lib/utils";

type Props = {
  symbol: string;
  quote?: QuoteDict | null;
  modeLabel?: string;
};

export function SymbolHeader({ symbol, quote, modeLabel }: Props) {
  const chg = quote?.change_pct != null ? Number(quote.change_pct) : null;
  const up = chg != null && chg >= 0;

  return (
    <div
      className="sticky top-0 z-10 flex flex-wrap items-end justify-between gap-3 border-b border-border/50 bg-background/90 backdrop-blur px-1 py-2"
      data-testid="symbol-header"
    >
      <div className="min-w-0">
        <div className="flex items-center gap-2 flex-wrap">
          <h2 className="text-lg font-semibold font-mono tracking-tight truncate">{symbol}</h2>
          {modeLabel && (
            <Badge className="text-[10px] font-normal text-muted-foreground">{modeLabel}</Badge>
          )}
          {quote?.stale && <Badge className="text-[10px] text-amber-400">stale</Badge>}
        </div>
        <div className="flex items-baseline gap-3 mt-0.5 flex-wrap">
          <span className="text-3xl font-mono font-semibold tabular-nums">
            {quote?.price != null ? formatNumber(quote.price) : "—"}
          </span>
          {chg != null && (
            <span className={cn("text-sm font-mono tabular-nums", up ? "text-up" : "text-down")}>
              {up ? "+" : ""}
              {formatNumber(chg)}%
            </span>
          )}
        </div>
      </div>
      <div className="text-right text-[11px] text-muted-foreground space-y-0.5">
        <div>
          Delayed · {quote?.source || "free data"}
          {quote?.currency ? ` · ${quote.currency}` : ""}
        </div>
        {(quote?.bid != null || quote?.ask != null) && (
          <div className="font-mono">
            Bid {quote.bid != null ? formatNumber(quote.bid) : "—"} · Ask{" "}
            {quote.ask != null ? formatNumber(quote.ask) : "—"}
          </div>
        )}
        {quote?.age_seconds != null && <div>age {quote.age_seconds}s</div>}
      </div>
    </div>
  );
}
