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
  const chartRef = useRef<HTMLDivElement>(null);
  const chartApi = useRef<IChartApi | null>(null);

  async function load(sym: string) {
    setError("");
    setParams({ symbol: sym });
    try {
      const q = await api<Record<string, unknown>>(`/api/market/quote/${encodeURIComponent(sym)}`);
      setQuote(q);
      const hist = await api<{ candles: { time: string; open: number; high: number; low: number; close: number }[] }>(
        `/api/market/history/${encodeURIComponent(sym)}?period=3mo`,
      );
      if (chartRef.current) {
        chartApi.current?.remove();
        const chart = createChart(chartRef.current, {
          height: 320,
          layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
          grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
        });
        chartApi.current = chart;
        const series = chart.addAreaSeries({ lineColor: "#38bdf8", topColor: "rgba(56,189,248,0.3)", bottomColor: "rgba(56,189,248,0.0)" });
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
    return () => chartApi.current?.remove();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Markets</h1>
        <p className="text-sm text-muted-foreground">Live quotes with age / staleness · TradingView lightweight-charts</p>
      </div>
      <div className="flex gap-2 flex-wrap">
        <Input className="max-w-xs" value={symbol} onChange={(e) => setSymbol(e.target.value)} onKeyDown={(e) => e.key === "Enter" && load(symbol)} />
        <Button onClick={() => load(symbol)}>Quote</Button>
      </div>
      {error && <p className="text-down text-sm">{error}</p>}
      {quote && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="font-mono">{String(quote.symbol)}</CardTitle>
            <div className="flex gap-2">
              <Badge>{String(quote.source)}</Badge>
              {quote.stale ? <Badge className="text-amber-400">stale</Badge> : <Badge className="text-up">fresh</Badge>}
            </div>
          </CardHeader>
          <CardContent>
            <div className="text-3xl font-mono font-semibold">
              {String(quote.currency)} {formatNumber(String(quote.price))}
            </div>
            <p className="text-xs text-muted-foreground mt-2">
              as of {String(quote.as_of)} · age {String(quote.age_seconds)}s
              {quote.change_pct != null && ` · ${formatNumber(String(quote.change_pct))}%`}
            </p>
            <div ref={chartRef} className="mt-4 w-full" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}