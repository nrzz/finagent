import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { createChart, type IChartApi } from "lightweight-charts";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Badge } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

export function MarketsPage() {
  const [params, setParams] = useSearchParams();
  const [symbol, setSymbol] = useState(params.get("symbol") || "RELIANCE.NS");
  const [quote, setQuote] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [benchmarkCount, setBenchmarkCount] = useState<number | null>(null);
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApi = useRef<IChartApi | null>(null);

  async function loadWatchlist() {
    try {
      const w = await api<{ items: { symbol: string }[] }>("/api/watchlist");
      setWatchlist((w.items || []).map((i) => i.symbol));
    } catch {
      /* ignore */
    }
  }

  async function load(sym: string) {
    setError("");
    setParams({ symbol: sym });
    try {
      const q = await api<Record<string, unknown>>(`/api/market/quote/${encodeURIComponent(sym)}`);
      setQuote(q);
      const hist = await api<{ candles: { time: string; open: number; high: number; low: number; close: number }[] }>(
        `/api/market/history/${encodeURIComponent(sym)}?period=3mo`,
      );
      try {
        const bench = await api<{ candles: unknown[] }>(
          `/api/portfolio/benchmark?symbol=${encodeURIComponent("^NSEI")}&period=3mo`,
        );
        setBenchmarkCount((bench.candles || []).length);
      } catch {
        setBenchmarkCount(null);
      }
      if (chartRef.current) {
        chartApi.current?.remove();
        const chart = createChart(chartRef.current, {
          height: 320,
          layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
          grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        });
        chartApi.current = chart;
        const series = chart.addAreaSeries({
          lineColor: "#38bdf8",
          topColor: "rgba(56,189,248,0.3)",
          bottomColor: "rgba(56,189,248,0.0)",
        });
        series.setData(
          hist.candles.map((c) => ({
            time: c.time.slice(0, 10) as `${number}-${number}-${number}`,
            value: c.close,
          })),
        );
        chart.timeScale().fitContent();
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed");
    }
  }

  useEffect(() => {
    load(symbol);
    loadWatchlist();
    return () => chartApi.current?.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Markets</h1>
        <p className="text-sm text-muted-foreground">
          Quotes with age / staleness · watchlist · chart
        </p>
      </div>
      <div className="flex gap-2 flex-wrap">
        <Input
          className="max-w-xs"
          value={symbol}
          onChange={(e) => setSymbol(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load(symbol)}
        />
        <Button onClick={() => load(symbol)}>Quote</Button>
        <Button
          variant="outline"
          onClick={async () => {
            await api("/api/watchlist", {
              method: "POST",
              body: JSON.stringify({ symbol }),
            });
            await loadWatchlist();
          }}
        >
          Add to watchlist
        </Button>
      </div>
      {watchlist.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {watchlist.map((s) => (
            <span
              key={s}
              className="inline-flex items-center gap-1 text-xs rounded border px-2 py-1 font-mono"
            >
              <button
                type="button"
                className="hover:underline"
                onClick={() => {
                  setSymbol(s);
                  load(s);
                }}
              >
                {s}
              </button>
              <button
                type="button"
                className="text-muted-foreground hover:text-red-400 px-0.5"
                title={`Remove ${s}`}
                aria-label={`Remove ${s}`}
                onClick={async (e) => {
                  e.stopPropagation();
                  try {
                    await api(`/api/watchlist/${encodeURIComponent(s)}`, { method: "DELETE" });
                    await loadWatchlist();
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Failed to remove");
                  }
                }}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground">
          No symbols yet — quote a ticker and click Add to watchlist
        </p>
      )}
      {error && <p className="text-down text-sm">{error}</p>}
      {quote && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="font-mono">{String(quote.symbol)}</CardTitle>
            <div className="flex gap-2">
              <Badge>{String(quote.source)}</Badge>
              {quote.stale ? (
                <Badge className="text-amber-400">stale</Badge>
              ) : (
                <Badge className="text-up">fresh</Badge>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-semibold">
              {String(quote.currency)} {formatNumber(String(quote.price))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              as of {String(quote.as_of)} · age {String(quote.age_seconds)}s
              {quote.change_pct != null && ` · ${formatNumber(String(quote.change_pct))}%`}
              {benchmarkCount != null && ` · Nifty bars available: ${benchmarkCount}`}
            </p>
            <div ref={chartRef} className="mt-4 w-full" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}