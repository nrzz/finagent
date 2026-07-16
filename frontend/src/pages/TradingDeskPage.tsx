import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "@/lib/api";
import { MarketStream, type QuoteDict } from "@/lib/marketStream";
import { CandleChart } from "@/components/trading/CandleChart";
import { WatchlistPanel } from "@/components/trading/WatchlistPanel";
import { SymbolHeader } from "@/components/trading/SymbolHeader";
import { OrderTicket } from "@/components/trading/OrderTicket";
import { OrdersBlotter } from "@/components/trading/OrdersBlotter";
import { PositionsPanel, type PositionRow } from "@/components/trading/PositionsPanel";
import { OptionChainPanel } from "@/components/trading/OptionChainPanel";
import { cn } from "@/lib/utils";

type DeskMode = "equity" | "fno" | "crypto";
type Side = "buy" | "sell";

function parseDeskMode(raw: string | null): DeskMode {
  if (raw === "fno" || raw === "crypto") return raw;
  return "equity";
}

function parseSide(raw: string | null): Side {
  return raw === "sell" ? "sell" : "buy";
}

function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  return el.isContentEditable;
}

export function TradingDeskPage() {
  const [params, setParams] = useSearchParams();
  const deskMode = parseDeskMode(params.get("mode"));
  const symbol = params.get("symbol") || (deskMode === "crypto" ? "BTC/USDT" : "RELIANCE.NS");
  const side = parseSide(params.get("side"));

  const [watchlist, setWatchlist] = useState<string[]>([]);
  const [quotes, setQuotes] = useState<Record<string, QuoteDict>>({});
  const [orders, setOrders] = useState<Record<string, unknown>[]>([]);
  const [positions, setPositions] = useState<PositionRow[]>([]);
  const [cash, setCash] = useState<string | null>(null);
  const [tradingMode, setTradingMode] = useState("paper");
  const [fnoUnderlying, setFnoUnderlying] = useState(
    symbol.replace(".NS", "").replace("^", "") || "NIFTY",
  );

  const symbolInputRef = useRef<HTMLInputElement | null>(null);
  const qtyInputRef = useRef<HTMLInputElement | null>(null);
  const streamRef = useRef<MarketStream | null>(null);

  const setSymbol = useCallback(
    (sym: string) => {
      const next = new URLSearchParams(params);
      next.set("symbol", sym);
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const setSide = useCallback(
    (s: Side) => {
      const next = new URLSearchParams(params);
      next.set("side", s);
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const setDeskMode = useCallback(
    (m: DeskMode) => {
      const next = new URLSearchParams(params);
      next.set("mode", m);
      if (m === "crypto" && !params.get("symbol")?.includes("/")) {
        next.set("symbol", "BTC/USDT");
      }
      if (m === "equity" && params.get("symbol")?.includes("/")) {
        next.set("symbol", "RELIANCE.NS");
      }
      setParams(next, { replace: true });
    },
    [params, setParams],
  );

  const loadWatchlist = useCallback(async () => {
    try {
      const w = await api<{ items: { symbol: string }[] }>("/api/watchlist");
      setWatchlist((w.items || []).map((i) => i.symbol));
    } catch {
      /* ignore */
    }
  }, []);

  const refreshBook = useCallback(async () => {
    let mode = tradingMode;
    try {
      const s = await api<{
        settings?: { trading?: { mode?: string } };
      }>("/api/settings");
      mode = s.settings?.trading?.mode || "paper";
      setTradingMode(mode);
    } catch {
      /* ignore */
    }
    try {
      const endpoint = mode === "live" ? "/api/trading/orders" : "/api/trading/blotter";
      const res = await api<{ orders?: Record<string, unknown>[] }>(endpoint);
      setOrders(Array.isArray(res.orders) ? res.orders : []);
    } catch {
      /* ignore */
    }
    try {
      const pf = await api<{
        paper?: { cash?: string; positions?: PositionRow[] };
      }>("/api/portfolio");
      setCash(pf.paper?.cash ?? null);
      const pos = pf.paper?.positions;
      setPositions(Array.isArray(pos) ? pos.filter((p) => p && typeof p.symbol === "string") : []);
    } catch {
      /* ignore */
    }
  }, [tradingMode]);

  useEffect(() => {
    void loadWatchlist();
    void refreshBook();
  }, [loadWatchlist, refreshBook]);

  useEffect(() => {
    const id = window.setInterval(() => {
      void refreshBook();
    }, 8000);
    return () => window.clearInterval(id);
  }, [refreshBook]);

  const streamSymbols = useMemo(() => {
    const set = new Set<string>([...(watchlist || []), symbol].filter(Boolean));
    for (const p of positions || []) {
      if (p?.symbol) set.add(p.symbol);
    }
    return [...set];
  }, [watchlist, symbol, positions]);

  useEffect(() => {
    if (!streamRef.current) streamRef.current = new MarketStream();
    const stream = streamRef.current;
    stream.connect(streamSymbols, (batch) => {
      setQuotes((prev) => {
        const next = { ...prev };
        for (const q of batch) {
          if (q?.symbol) next[q.symbol] = q;
        }
        return next;
      });
    });
    return () => stream.disconnect();
  }, [streamSymbols.join("|")]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (isTypingTarget(e.target)) return;
      if (e.key === "b" || e.key === "B") {
        e.preventDefault();
        setSide("buy");
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        setSide("sell");
      } else if (e.key === "/") {
        e.preventDefault();
        symbolInputRef.current?.focus();
        symbolInputRef.current?.select();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setSide]);

  async function addWatch(sym: string) {
    await api("/api/watchlist", { method: "POST", body: JSON.stringify({ symbol: sym }) });
    await loadWatchlist();
  }

  async function removeWatch(sym: string) {
    await api(`/api/watchlist/${encodeURIComponent(sym)}`, { method: "DELETE" });
    await loadWatchlist();
  }

  async function cancelOrder(orderId: string) {
    await api(`/api/trading/orders/${encodeURIComponent(orderId)}/cancel`, { method: "POST" });
    await refreshBook();
  }

  async function resetPaper() {
    await api("/api/trading/paper/reset", { method: "POST" });
    await refreshBook();
  }

  function onSelectSymbol(sym: string) {
    setSymbol(sym);
    qtyInputRef.current?.focus();
  }

  const quote = quotes[symbol];
  const modeLabel =
    deskMode === "fno"
      ? "F&O"
      : deskMode === "crypto"
        ? "Crypto"
        : tradingMode === "live"
          ? "Live"
          : "Equity";

  const pageTitle =
    deskMode === "fno"
      ? "F&O (paper)"
      : tradingMode === "live"
        ? "Live trading"
        : "Paper trading";

  return (
    <div
      className="w-full max-w-none -mx-3 md:-mx-6 px-3 md:px-4 space-y-2"
      data-testid="trading-desk"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold leading-tight">{pageTitle}</h1>
          <p className="text-[11px] text-muted-foreground">
            Dense desk · B/S side · / focus symbol · Delayed free data
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-border/60 p-0.5">
          {(
            [
              ["equity", "Equity"],
              ["fno", "F&O"],
              ["crypto", "Crypto"],
            ] as const
          ).map(([key, label]) => (
            <button
              key={key}
              type="button"
              className={cn(
                "px-3 py-1 text-xs rounded",
                deskMode === key ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/40",
              )}
              onClick={() => setDeskMode(key)}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <SymbolHeader symbol={symbol} quote={quote} modeLabel={modeLabel} />

      <div className="grid gap-2 lg:grid-cols-[14rem_minmax(0,1fr)_20rem]">
        <WatchlistPanel
          symbols={watchlist}
          quotes={quotes}
          selectedSymbol={symbol}
          onSelect={onSelectSymbol}
          onAdd={addWatch}
          onRemove={removeWatch}
          onPrefetch={(sym) => {
            if (!quotes[sym]) {
              api<QuoteDict>(`/api/market/quote/${encodeURIComponent(sym)}`)
                .then((q) => setQuotes((prev) => ({ ...prev, [sym]: q })))
                .catch(() => undefined);
            }
          }}
        />

        <div className="min-w-0 space-y-2">
          {deskMode !== "fno" && <CandleChart symbol={symbol} height={340} />}
          {deskMode === "fno" && (
            <>
              <CandleChart symbol={symbol.includes(".") || symbol.startsWith("^") ? symbol : `${fnoUnderlying}.NS`} height={220} />
              <OptionChainPanel
                underlying={fnoUnderlying}
                onUnderlyingChange={setFnoUnderlying}
                onStrikeSelect={(_strike, _type, _premium, _expiry) => {
                  /* parent ticket stays equity; F&O uses internal ticket */
                }}
              />
            </>
          )}
        </div>

        <OrderTicket
          symbol={symbol}
          onSymbolChange={setSymbol}
          side={side}
          onSideChange={setSide}
          ltp={quote?.price}
          cash={cash}
          onPlaced={refreshBook}
          symbolInputRef={symbolInputRef}
          qtyInputRef={qtyInputRef}
        />
      </div>

      <div className="grid gap-2 lg:grid-cols-2">
        <PositionsPanel
          positions={positions}
          quotes={quotes}
          onSelect={onSelectSymbol}
        />
        <OrdersBlotter
          orders={orders}
          mode={tradingMode}
          onRefresh={refreshBook}
          onCancel={cancelOrder}
          onResetPaper={resetPaper}
        />
      </div>
    </div>
  );
}
