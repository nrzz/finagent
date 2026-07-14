import { useEffect, useRef, useState } from "react";
import { streamChat, api } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/primitives";
import { ToolResultCards } from "@/components/chat/ToolResultCards";
import { cn } from "@/lib/utils";

type Msg = {
  role: "user" | "assistant";
  content: string;
  tools?: unknown[];
  citations?: Record<string, unknown>[];
};

const CHIPS = [
  { label: "Price of RELIANCE.NS", prompt: "What's the quote for RELIANCE.NS?" },
  { label: "Analyze my portfolio", prompt: "Analyze my portfolio" },
  { label: "Top movers today", prompt: "Show top movers today" },
  { label: "Paper-buy 10 AAPL", prompt: "Paper-buy 10 AAPL" },
  { label: "NIFTY option chain", prompt: "Show NIFTY option chain" },
];

type StatusInfo = {
  mode: string;
  llm: string;
};

export function ChatPage() {
  const [messages, setMessages] = useState<Msg[]>([
    {
      role: "assistant",
      content:
        "Hi — I'm FinAgent. Ask for quotes, option chains, portfolio checks, or paper trades. I only use numbers from tools and cite timestamps.\n\n**Not financial advice.** Paper trading is on by default.",
    },
  ]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<StatusInfo>({ mode: "paper", llm: "demo" });
  const [confirmingKey, setConfirmingKey] = useState<string | null>(null);
  const [banner, setBanner] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api<{
      settings: {
        trading: { mode: string };
        llm: { model: string; provider: string; profiles?: { id: string; name: string; model: string }[]; active_profile_id?: string };
      };
    }>("/api/settings")
      .then((res) => {
        const llm = res.settings.llm;
        const active = llm.profiles?.find((p) => p.id === llm.active_profile_id);
        setStatus({
          mode: res.settings.trading.mode || "paper",
          llm: active?.name || `${llm.provider}/${llm.model}`,
        });
      })
      .catch(() => undefined);
  }, []);

  async function send(text?: string) {
    const userMsg = (text ?? input).trim();
    if (!userMsg || busy) return;
    setInput("");
    setBanner("");
    setMessages((m) => [...m, { role: "user", content: userMsg }, { role: "assistant", content: "", tools: [] }]);
    setBusy(true);
    const history = messages.filter((m) => m.content).map((m) => ({ role: m.role, content: m.content }));
    try {
      await streamChat(userMsg, history, (ev) => {
        setMessages((prev) => {
          const copy = [...prev];
          const last = { ...copy[copy.length - 1] };
          if (ev.type === "token") {
            last.content += String(ev.content || "");
          } else if (ev.type === "tool_result") {
            last.tools = [...(last.tools || []), ev.data];
          } else if (ev.type === "final") {
            last.content = String(ev.content || last.content);
            last.citations = (ev.citations as Record<string, unknown>[]) || [];
            last.tools = (ev.tool_trace as unknown[]) || last.tools;
          } else if (ev.type === "status") {
            if (!last.content) last.content = String(ev.message || "Thinking…");
          }
          copy[copy.length - 1] = last;
          return copy;
        });
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
      });
    } catch (err) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = {
          role: "assistant",
          content: err instanceof Error ? err.message : "Chat failed",
        };
        return copy;
      });
    } finally {
      setBusy(false);
      inputRef.current?.focus();
    }
  }

  async function confirmOrder(draft: {
    symbol: string;
    side: string;
    quantity: string;
    price: string;
    asset_class?: string;
    idempotency_key?: string | null;
  }) {
    const key = `${draft.side}-${draft.quantity}-${draft.symbol}-${draft.price}`;
    setConfirmingKey(key);
    setBanner("");
    try {
      let px = draft.price;
      if (!px || px === "0") {
        const q = await api<{ price: string }>(`/api/market/quote/${encodeURIComponent(draft.symbol)}`);
        px = q.price;
      }
      const res = await api<{ ok: boolean; error?: string; order?: Record<string, unknown> }>(
        "/api/trading/order",
        {
          method: "POST",
          body: JSON.stringify({
            symbol: draft.symbol,
            side: draft.side,
            quantity: draft.quantity,
            price: px,
            asset_class: draft.asset_class || (draft.symbol.includes("/") ? "crypto" : "equity"),
            idempotency_key: draft.idempotency_key || undefined,
            confirmed: true,
          }),
        },
      );
      if (res.ok) {
        setMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `Paper order ${String(res.order?.status || "submitted")}: ${draft.side} ${draft.quantity} ${draft.symbol} @ ${px}.\n\n_Not financial advice. Paper account only._`,
            tools: [
              {
                tool: "place_paper_order",
                ok: true,
                result: res.order,
              },
            ],
          },
        ]);
        setBanner("Paper order placed");
      } else {
        setBanner(res.error || "Order failed");
      }
    } catch (e) {
      setBanner(e instanceof Error ? e.message : "Order failed");
    } finally {
      setConfirmingKey(null);
    }
  }

  function cancelOrder(draft: { symbol: string; side: string; quantity: string }) {
    setMessages((prev) => [
      ...prev,
      {
        role: "assistant",
        content: `Cancelled proposed ${draft.side} ${draft.quantity} ${draft.symbol}. Nothing was executed.`,
      },
    ]);
  }

  return (
    <div className="flex flex-col h-[calc(100dvh-7.5rem)] md:h-[calc(100vh-6.5rem)] max-w-3xl mx-auto -mx-1">
      <div className="mb-3 space-y-2 shrink-0">
        <div className="flex items-center justify-between gap-2">
          <h1 className="text-xl md:text-2xl font-semibold tracking-tight">Agent</h1>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-[11px] md:text-xs rounded-lg border border-border/70 bg-card/60 px-3 py-2">
          <span className="rounded-full bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 px-2 py-0.5 capitalize">
            {status.mode} trading
          </span>
          <span className="text-muted-foreground truncate max-w-[40%]">{status.llm}</span>
          <span className="text-amber-200/90">· Not financial advice</span>
        </div>
      </div>

      <div className="flex-1 min-h-0 rounded-xl border bg-card flex flex-col overflow-hidden shadow-sm">
        <div className="flex-1 overflow-auto space-y-3 p-3 md:p-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={cn(
                  "max-w-[92%] rounded-2xl px-3.5 py-2.5 text-sm whitespace-pre-wrap",
                  m.role === "user" ? "bg-primary text-primary-foreground" : "bg-secondary",
                )}
              >
                {m.content || (busy && i === messages.length - 1 ? "…" : "")}
                <ToolResultCards
                  tools={m.tools}
                  confirmingKey={confirmingKey}
                  onConfirmOrder={confirmOrder}
                  onCancelOrder={cancelOrder}
                />
                {!!m.citations?.length && (
                  <div className="mt-3 space-y-1 border-t border-border/40 pt-2">
                    {m.citations.map((c, j) => (
                      <div key={j} className="text-xs text-primary/90 font-mono">
                        {String(c.symbol || "data")} · {String(c.source || "")} · {String(c.as_of || "")}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          <div ref={bottomRef} />
        </div>

        <div className="border-t bg-background/80 backdrop-blur p-2.5 md:p-3 space-y-2 shrink-0 sticky bottom-0">
          {banner && <p className="text-xs text-muted-foreground px-1">{banner}</p>}
          <div className="flex gap-1.5 overflow-x-auto pb-1 -mx-0.5 px-0.5 scrollbar-thin">
            {CHIPS.map((chip) => (
              <button
                key={chip.label}
                type="button"
                disabled={busy}
                onClick={() => send(chip.prompt)}
                className="shrink-0 rounded-full border border-border bg-muted/40 px-3 py-1.5 text-xs hover:bg-accent disabled:opacity-50"
              >
                {chip.label}
              </button>
            ))}
          </div>
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything — quotes, portfolio, paper trades…"
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              disabled={busy}
              className="h-11 text-base md:text-sm"
            />
            <Button className="h-11 px-5" onClick={() => send()} disabled={busy}>
              Send
            </Button>
          </div>
          <p className="text-[10px] text-muted-foreground px-1 leading-snug">
            Educational tool only. Not investment advice. Past performance ≠ future results. You can lose money.
          </p>
        </div>
      </div>
    </div>
  );
}
