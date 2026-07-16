import { useState } from "react";
import type { QuoteDict } from "@/lib/marketStream";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/primitives";
import { cn, formatNumber } from "@/lib/utils";

type Props = {
  symbols: string[];
  quotes: Record<string, QuoteDict>;
  selectedSymbol: string;
  onSelect: (symbol: string) => void;
  onAdd: (symbol: string) => void | Promise<void>;
  onRemove: (symbol: string) => void | Promise<void>;
  onPrefetch?: (symbol: string) => void;
};

export function WatchlistPanel({
  symbols,
  quotes,
  selectedSymbol,
  onSelect,
  onAdd,
  onRemove,
  onPrefetch,
}: Props) {
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);

  async function add() {
    const sym = draft.trim().toUpperCase();
    if (!sym) return;
    setBusy(true);
    try {
      await onAdd(sym);
      setDraft("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div
      className="flex flex-col h-full min-h-[16rem] rounded-lg border border-border/60 bg-card/30"
      data-testid="watchlist-panel"
    >
      <div className="px-2 py-1.5 border-b border-border/50 text-xs font-medium text-muted-foreground">
        Watchlist
      </div>
      <div className="flex gap-1 p-2 border-b border-border/40">
        <Input
          className="h-8 text-xs font-mono"
          value={draft}
          placeholder="Add symbol"
          onChange={(e) => setDraft(e.target.value.toUpperCase())}
          onKeyDown={(e) => e.key === "Enter" && void add()}
        />
        <Button size="sm" className="h-8 shrink-0" disabled={busy || !draft.trim()} onClick={() => void add()}>
          Add
        </Button>
      </div>
      {symbols.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center gap-2 p-4 text-center">
          <p className="text-xs text-muted-foreground">No symbols yet</p>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setDraft(selectedSymbol || "AAPL");
            }}
          >
            Add {selectedSymbol || "AAPL"}
          </Button>
        </div>
      ) : (
        <div className="flex-1 overflow-auto">
          <table className="w-full text-[11px] font-mono">
            <thead className="sticky top-0 bg-card text-muted-foreground text-left">
              <tr>
                <th className="py-1 px-2 font-medium">Sym</th>
                <th className="py-1 px-1 font-medium text-right">LTP</th>
                <th className="py-1 px-1 font-medium text-right">Chg%</th>
                <th className="w-5" />
              </tr>
            </thead>
            <tbody>
              {symbols.map((sym) => {
                const q = quotes[sym];
                const chg = q?.change_pct != null ? Number(q.change_pct) : null;
                const selected = sym === selectedSymbol;
                return (
                  <tr
                    key={sym}
                    className={cn(
                      "border-b border-border/30 cursor-pointer hover:bg-accent/40",
                      selected && "bg-accent/60",
                    )}
                    onClick={() => onSelect(sym)}
                    onDoubleClick={() => onSelect(sym)}
                    onMouseEnter={() => onPrefetch?.(sym)}
                  >
                    <td className="py-1.5 px-2">
                      <div className="flex items-center gap-1">
                        <span>{sym}</span>
                        {q?.stale && (
                          <span className="text-[9px] text-amber-400 border border-amber-500/40 rounded px-0.5">
                            stale
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="py-1.5 px-1 text-right">
                      {q?.price != null ? formatNumber(q.price) : q?.error ? "—" : "…"}
                    </td>
                    <td
                      className={cn(
                        "py-1.5 px-1 text-right",
                        chg != null && chg >= 0 ? "text-up" : chg != null ? "text-down" : "",
                      )}
                    >
                      {chg != null ? `${chg >= 0 ? "+" : ""}${formatNumber(chg)}` : "—"}
                    </td>
                    <td className="px-1">
                      <button
                        type="button"
                        className="text-muted-foreground hover:text-red-400"
                        aria-label={`Remove ${sym}`}
                        onClick={(e) => {
                          e.stopPropagation();
                          void onRemove(sym);
                        }}
                      >
                        ×
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
