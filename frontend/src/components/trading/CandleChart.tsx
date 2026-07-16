import { useEffect, useRef, useState } from "react";
import {
  createChart,
  type IChartApi,
  type ISeriesApi,
  type UTCTimestamp,
} from "lightweight-charts";
import { api } from "@/lib/api";
import { isDailyInterval, sma, tfToQuery, type TfKey } from "@/lib/chartMath";
import { Badge } from "@/components/ui/primitives";
import { cn } from "@/lib/utils";

const TFS: TfKey[] = ["1D", "5D", "1M", "3M", "1Y", "1H", "15m", "5m"];

type Candle = {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
};

type Props = {
  symbol: string;
  height?: number;
};

function mapTime(raw: string, interval: string): string | UTCTimestamp {
  if (isDailyInterval(interval)) {
    return raw.slice(0, 10);
  }
  const ms = Date.parse(raw);
  if (Number.isNaN(ms)) return raw.slice(0, 10);
  return Math.floor(ms / 1000) as UTCTimestamp;
}

export function CandleChart({ symbol, height = 360 }: Props) {
  const hostRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const sma20Ref = useRef<ISeriesApi<"Line"> | null>(null);
  const sma50Ref = useRef<ISeriesApi<"Line"> | null>(null);

  const [tf, setTf] = useState<TfKey>("3M");
  const [showSma20, setShowSma20] = useState(true);
  const [showSma50, setShowSma50] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!hostRef.current) return;
    const chart = createChart(hostRef.current, {
      height,
      layout: { background: { color: "transparent" }, textColor: "#94a3b8" },
      grid: { vertLines: { color: "#1e293b" }, horzLines: { color: "#1e293b" } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false },
      crosshair: { mode: 0 },
    });
    chartRef.current = chart;
    candleRef.current = chart.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    volumeRef.current = chart.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "",
      color: "rgba(148,163,184,0.35)",
    });
    volumeRef.current.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });
    sma20Ref.current = chart.addLineSeries({
      color: "#38bdf8",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });
    sma50Ref.current = chart.addLineSeries({
      color: "#f59e0b",
      lineWidth: 1,
      priceLineVisible: false,
      lastValueVisible: false,
    });

    const ro = new ResizeObserver(() => {
      if (hostRef.current) {
        chart.applyOptions({ width: hostRef.current.clientWidth });
      }
    });
    ro.observe(hostRef.current);
    chart.applyOptions({ width: hostRef.current.clientWidth });

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      candleRef.current = null;
      volumeRef.current = null;
      sma20Ref.current = null;
      sma50Ref.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!symbol.trim()) return;
    let cancelled = false;
    const { period, interval } = tfToQuery(tf);

    async function load() {
      setLoading(true);
      setError("");
      try {
        const hist = await api<{ candles: Candle[]; note?: string }>(
          `/api/market/history/${encodeURIComponent(symbol)}?period=${encodeURIComponent(period)}&interval=${encodeURIComponent(interval)}`,
        );
        if (cancelled) return;
        const candles = hist.candles || [];
        if (!candleRef.current || !volumeRef.current) return;
        if (candles.length === 0) {
          candleRef.current.setData([]);
          volumeRef.current.setData([]);
          sma20Ref.current?.setData([]);
          sma50Ref.current?.setData([]);
          setError(hist.note || "No candles");
          return;
        }
        const mapped = candles.map((c) => ({
          time: mapTime(c.time, interval),
          open: c.open,
          high: c.high,
          low: c.low,
          close: c.close,
          volume: c.volume ?? 0,
        }));
        candleRef.current.setData(
          mapped.map(({ time, open, high, low, close }) => ({ time: time as UTCTimestamp, open, high, low, close })),
        );
        volumeRef.current.setData(
          mapped.map((c) => ({
            time: c.time as UTCTimestamp,
            value: c.volume,
            color: c.close >= c.open ? "rgba(34,197,94,0.35)" : "rgba(239,68,68,0.35)",
          })),
        );
        const closes = mapped.map((c) => c.close);
        const s20 = sma(closes, 20);
        const s50 = sma(closes, 50);
        sma20Ref.current?.setData(
          showSma20
            ? s20
                .map((v, i) => (v == null ? null : { time: mapped[i].time as UTCTimestamp, value: v }))
                .filter((x): x is { time: UTCTimestamp; value: number } => x != null)
            : [],
        );
        sma50Ref.current?.setData(
          showSma50
            ? s50
                .map((v, i) => (v == null ? null : { time: mapped[i].time as UTCTimestamp, value: v }))
                .filter((x): x is { time: UTCTimestamp; value: number } => x != null)
            : [],
        );
        chartRef.current?.timeScale().fitContent();
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load history");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [symbol, tf, showSma20, showSma50]);

  return (
    <div className="flex flex-col gap-2 min-w-0" data-testid="candle-chart">
      <div className="flex flex-wrap items-center gap-1.5 justify-between">
        <div className="flex flex-wrap gap-1">
          {TFS.map((t) => (
            <button
              key={t}
              type="button"
              className={cn(
                "px-2 py-0.5 text-[11px] font-mono rounded border",
                tf === t
                  ? "bg-accent border-primary/40 text-foreground"
                  : "border-border text-muted-foreground hover:bg-accent/50",
              )}
              onClick={() => setTf(t)}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground cursor-pointer">
            <input type="checkbox" checked={showSma20} onChange={(e) => setShowSma20(e.target.checked)} />
            SMA20
          </label>
          <label className="flex items-center gap-1 text-[11px] text-muted-foreground cursor-pointer">
            <input type="checkbox" checked={showSma50} onChange={(e) => setShowSma50(e.target.checked)} />
            SMA50
          </label>
          <Badge className="text-[10px] text-amber-300/90">Delayed · free data</Badge>
        </div>
      </div>
      <div className="relative rounded-lg border border-border/60 bg-card/40">
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center text-xs text-muted-foreground bg-background/40">
            Loading…
          </div>
        )}
        {error && !loading && (
          <div className="absolute inset-x-0 top-2 z-10 text-center text-xs text-down px-2">{error}</div>
        )}
        <div ref={hostRef} className="w-full" style={{ height }} />
      </div>
    </div>
  );
}
