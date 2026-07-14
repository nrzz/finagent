import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, Input, Label } from "@/components/ui/primitives";

export function AutomationPage() {
  const [alerts, setAlerts] = useState<Record<string, unknown>[]>([]);
  const [jobs, setJobs] = useState<Record<string, unknown>[]>([]);
  const [notes, setNotes] = useState<Record<string, unknown>[]>([]);
  const [symbol, setSymbol] = useState("AAPL");
  const [condition, setCondition] = useState("above");
  const [threshold, setThreshold] = useState("200");
  const [jobName, setJobName] = useState("morning-dca");
  const [jobType, setJobType] = useState("dca");
  const [cron, setCron] = useState("0 9 * * 1-5");
  const [dcaSymbol, setDcaSymbol] = useState("BTC/USDT");
  const [dcaQty, setDcaQty] = useState("0.001");
  const [msg, setMsg] = useState("");

  async function refresh() {
    const [a, j, n] = await Promise.all([
      api<{ alerts: Record<string, unknown>[] }>("/api/automation/alerts"),
      api<{ jobs: Record<string, unknown>[] }>("/api/automation/jobs"),
      api<{ items: Record<string, unknown>[] }>("/api/notifications"),
    ]);
    setAlerts(a.alerts);
    setJobs(j.jobs);
    setNotes(n.items);
  }

  useEffect(() => {
    refresh().catch((e) => setMsg(e.message));
  }, []);

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-semibold">Automation</h1>
        <p className="text-sm text-muted-foreground">
          Alerts, DCA paper buys, scheduled analysis — persisted. Not financial advice.
        </p>
      </div>
      {msg && <p className="text-sm text-red-400">{msg}</p>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Price alert</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Label>Symbol</Label>
            <Input value={symbol} onChange={(e) => setSymbol(e.target.value)} />
            <Label>Condition</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={condition}
              onChange={(e) => setCondition(e.target.value)}
            >
              <option value="above">above</option>
              <option value="below">below</option>
            </select>
            <Label>Threshold</Label>
            <Input value={threshold} onChange={(e) => setThreshold(e.target.value)} />
            <Button
              onClick={async () => {
                try {
                  await api("/api/automation/alerts", {
                    method: "POST",
                    body: JSON.stringify({ symbol, condition, threshold }),
                  });
                  setMsg("");
                  await refresh();
                } catch (e) {
                  setMsg(e instanceof Error ? e.message : "Failed to add alert");
                }
              }}
            >
              Add alert
            </Button>
            <div className="text-xs space-y-1 max-h-40 overflow-auto pt-2">
              {alerts.map((a) => (
                <div key={String(a.id)} className="font-mono border-b border-border/40 py-1">
                  {String(a.symbol)} {String(a.condition)} {String(a.threshold)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Scheduled job</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <Label>Name</Label>
            <Input value={jobName} onChange={(e) => setJobName(e.target.value)} />
            <Label>Type</Label>
            <select
              className="h-10 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={jobType}
              onChange={(e) => setJobType(e.target.value)}
            >
              <option value="dca">DCA paper buy</option>
              <option value="analysis">Scheduled analysis</option>
              <option value="alert_scan">Alert scan</option>
              <option value="square_off">F&O square-off</option>
            </select>
            <Label>Cron</Label>
            <Input value={cron} onChange={(e) => setCron(e.target.value)} />
            {jobType === "dca" && (
              <>
                <Label>DCA symbol</Label>
                <Input value={dcaSymbol} onChange={(e) => setDcaSymbol(e.target.value)} />
                <Label>Quantity</Label>
                <Input value={dcaQty} onChange={(e) => setDcaQty(e.target.value)} />
              </>
            )}
            <Button
              onClick={async () => {
                await api("/api/automation/jobs", {
                  method: "POST",
                  body: JSON.stringify({
                    name: jobName,
                    job_type: jobType,
                    cron,
                    timezone: "Asia/Kolkata",
                    payload:
                      jobType === "dca"
                        ? { symbol: dcaSymbol, quantity: dcaQty, asset_class: dcaSymbol.includes("/") ? "crypto" : "equity" }
                        : { symbols: ["AAPL", "RELIANCE.NS", "BTC/USDT"] },
                  }),
                });
                await refresh();
              }}
            >
              Save job
            </Button>
            <div className="text-xs space-y-1 max-h-40 overflow-auto pt-2">
              {jobs.map((j) => (
                <div key={String(j.id || j.name)} className="font-mono border-b border-border/40 py-1">
                  {String(j.name)} · {String(j.job_type)} · {String(j.cron)}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>In-app notifications</CardTitle>
          <Button size="sm" variant="secondary" onClick={() => refresh()}>Refresh</Button>
        </CardHeader>
        <CardContent className="space-y-2 max-h-64 overflow-auto">
          {notes.map((n) => (
            <div key={String(n.id)} className="rounded-lg border p-3 text-sm">
              <div className="font-medium">{String(n.title)}</div>
              <div className="text-muted-foreground text-xs mt-1 whitespace-pre-wrap">{String(n.body)}</div>
              <div className="text-[10px] text-muted-foreground mt-1">{String(n.created_at)}</div>
            </div>
          ))}
          {notes.length === 0 && <p className="text-sm text-muted-foreground">No notifications yet.</p>}
        </CardContent>
      </Card>
    </div>
  );
}
