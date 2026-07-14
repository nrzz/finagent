import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { formatNumber } from "@/lib/utils";
import { Card, CardContent, CardHeader, CardTitle, Skeleton, Badge } from "@/components/ui/primitives";
import { Button } from "@/components/ui/button";

type Portfolio = {
  paper: { cash: string; equity: string; currency: string; realized_pnl: string; positions: { symbol: string; unrealized_pnl: string; market_value: string }[] };
  holdings: { symbol: string; market_value?: string; unrealized_pnl?: string; stale?: boolean }[];
  allocation_pct: Record<string, string>;
};

export function DashboardPage() {
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Portfolio>("/api/portfolio")
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="text-down">{error}</p>;
  if (!data) {
    return (
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
          <p className="text-sm text-muted-foreground">Paper book · not financial advice</p>
        </div>
        <div className="flex gap-2">
          <Button asChild variant="secondary"><Link to="/chat">Ask the agent</Link></Button>
          <Button asChild><Link to="/trading">Trade</Link></Button>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Paper equity</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold font-mono">
              {data.paper.currency} {formatNumber(data.paper.equity)}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Cash</CardTitle></CardHeader>
          <CardContent>
            <div className="text-2xl font-semibold font-mono">{formatNumber(data.paper.cash)}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle className="text-sm text-muted-foreground">Realized P&L</CardTitle></CardHeader>
          <CardContent>
            <div className={`text-2xl font-semibold font-mono ${Number(data.paper.realized_pnl) >= 0 ? "text-up" : "text-down"}`}>
              {formatNumber(data.paper.realized_pnl)}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Paper positions</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {data.paper.positions.length === 0 && (
              <p className="text-sm text-muted-foreground">No positions yet — place a paper order or ask the agent.</p>
            )}
            {data.paper.positions.map((p) => (
              <div key={p.symbol} className="flex justify-between text-sm border-b border-border/60 py-2">
                <span className="font-mono">{p.symbol}</span>
                <span className={Number(p.unrealized_pnl) >= 0 ? "text-up" : "text-down"}>
                  {formatNumber(p.unrealized_pnl)}
                </span>
              </div>
            ))}
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Allocation</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {Object.keys(data.allocation_pct).length === 0 && (
              <p className="text-sm text-muted-foreground">Import holdings to see allocation by symbol.</p>
            )}
            {Object.entries(data.allocation_pct).map(([sym, pct]) => (
              <div key={sym} className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="font-mono">{sym}</span>
                  <span>{pct}%</span>
                </div>
                <div className="h-2 rounded-full bg-muted overflow-hidden">
                  <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Tracked holdings</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {data.holdings.map((h) => (
            <div key={h.symbol} className="flex items-center justify-between text-sm py-2 border-b border-border/50">
              <div className="flex items-center gap-2">
                <span className="font-mono">{h.symbol}</span>
                {h.stale && <Badge className="text-amber-400 border-amber-400/40">stale</Badge>}
              </div>
              <span className="font-mono">{h.market_value ? formatNumber(h.market_value) : "—"}</span>
            </div>
          ))}
          {data.holdings.length === 0 && <p className="text-sm text-muted-foreground">Add holdings on the Portfolio page.</p>}
        </CardContent>
      </Card>
    </div>
  );
}