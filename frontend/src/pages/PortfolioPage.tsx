import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";
import { formatNumber } from "@/lib/utils";

export function PortfolioPage() {
  const [symbol, setSymbol] = useState("");
  const [qty, setQty] = useState("");
  const [cost, setCost] = useState("");
  const [data, setData] = useState<{ holdings: { symbol: string; quantity: string; avg_cost: string; market_value?: string; unrealized_pnl?: string }[] } | null>(null);
  const [msg, setMsg] = useState("");

  async function refresh() {
    setData(await api("/api/portfolio"));
  }

  useEffect(() => {
    refresh().catch((e) => setMsg(e.message));
  }, []);

  async function addHolding() {
    await api("/api/portfolio/holdings", {
      method: "POST",
      body: JSON.stringify({ symbol, quantity: qty, avg_cost: cost }),
    });
    setSymbol("");
    setQty("");
    setCost("");
    await refresh();
  }

  async function onCsv(file: File) {
    const fd = new FormData();
    fd.append("file", file);
    const token = localStorage.getItem("finagent_token");
    const res = await fetch("/api/portfolio/import-csv", {
      method: "POST",
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: fd,
    });
    if (!res.ok) throw new Error(await res.text());
    const body = await res.json();
    setMsg(`Imported ${body.imported} rows`);
    await refresh();
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Portfolio</h1>
        <p className="text-sm text-muted-foreground">Manual entry · CSV import · Decimal P&L</p>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Add holding</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <div className="space-y-1"><Label>Symbol</Label><Input value={symbol} onChange={(e) => setSymbol(e.target.value)} placeholder="TCS.NS / AAPL / BTC/USDT / MF:120503" /></div>
            <div className="space-y-1"><Label>Quantity</Label><Input value={qty} onChange={(e) => setQty(e.target.value)} /></div>
            <div className="space-y-1"><Label>Avg cost</Label><Input value={cost} onChange={(e) => setCost(e.target.value)} /></div>
            <Button onClick={addHolding}>Add</Button>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>Import CSV</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-muted-foreground">Columns: symbol, quantity, avg_cost, currency, asset_class</p>
            <Input type="file" accept=".csv" onChange={(e) => e.target.files?.[0] && onCsv(e.target.files[0])} />
            {msg && <p className="text-sm">{msg}</p>}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Holdings</CardTitle></CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-muted-foreground text-left">
                <tr>
                  <th className="py-2">Symbol</th>
                  <th>Qty</th>
                  <th>Avg cost</th>
                  <th>Mkt value</th>
                  <th>Unrealized</th>
                </tr>
              </thead>
              <tbody>
                {data?.holdings.map((h) => (
                  <tr key={h.symbol} className="border-t border-border/50 font-mono">
                    <td className="py-2">{h.symbol}</td>
                    <td>{h.quantity}</td>
                    <td>{formatNumber(h.avg_cost)}</td>
                    <td>{h.market_value ? formatNumber(h.market_value) : "—"}</td>
                    <td className={Number(h.unrealized_pnl || 0) >= 0 ? "text-up" : "text-down"}>
                      {h.unrealized_pnl ? formatNumber(h.unrealized_pnl) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}