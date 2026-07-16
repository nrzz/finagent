import { Link, NavLink, Outlet, useLocation, useNavigate, type To } from "react-router-dom";
import { useEffect, useState } from "react";
import {
  Bot,
  Briefcase,
  LayoutDashboard,
  LogOut,
  Settings,
  Sparkles,
  Zap,
  CandlestickChart,
  Bell,
} from "lucide-react";
import { api, clearToken } from "@/lib/api";
import { getApiBase, setApiBase } from "@/lib/native";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/CommandPalette";
import { cn } from "@/lib/utils";

type NavItem = {
  id: string;
  to: To;
  label: string;
  icon: typeof Bot;
  kind?: "trade" | "fno";
};

const nav: NavItem[] = [
  { id: "agent", to: "/", label: "Agent", icon: Bot },
  { id: "dashboard", to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { id: "portfolio", to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { id: "trade", to: "/trading", label: "Trade", icon: Zap, kind: "trade" },
  // Object form: RR must not treat "?mode=fno" as part of the pathname
  {
    id: "fno",
    to: { pathname: "/trading", search: "?mode=fno" },
    label: "F&O",
    icon: CandlestickChart,
    kind: "fno",
  },
  { id: "automation", to: "/automation", label: "Auto", icon: Bell },
  { id: "settings", to: "/settings", label: "Settings", icon: Settings },
];

function navActive(item: NavItem, pathname: string, search: string, isActive: boolean): boolean {
  const mode = new URLSearchParams(search).get("mode");
  const onTrading = pathname.includes("trading");
  if (item.kind === "fno") return onTrading && mode === "fno";
  if (item.kind === "trade") return onTrading && mode !== "fno";
  return isActive;
}

export function AppShell() {
  const navigate = useNavigate();
  const location = useLocation();
  const [unread, setUnread] = useState(0);
  const [apiDown, setApiDown] = useState(false);
  const isTrading = location.pathname.includes("trading");

  useEffect(() => {
    let cancelled = false;
    const tick = () => {
      api<{ items: { read: boolean }[] }>("/api/notifications")
        .then((res) => {
          if (!cancelled) setUnread((res.items || []).filter((i) => !i.read).length);
        })
        .catch(() => undefined);
    };
    tick();
    const id = window.setInterval(tick, 30000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    const check = () => {
      const base = getApiBase();
      fetch(`${base}/api/health`, { method: "GET" })
        .then((r) => {
          if (!cancelled) setApiDown(!r.ok);
        })
        .catch(() => {
          if (!cancelled) setApiDown(true);
        });
    };
    check();
    const id = window.setInterval(check, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, []);

  return (
    <div className="min-h-screen flex flex-col md:flex-row bg-background">
      <aside className="hidden md:flex md:w-60 flex-col border-r border-border p-4 gap-2">
        <div className="flex items-center gap-2 px-2 py-3 mb-4">
          <Sparkles className="h-6 w-6 text-primary" />
          <div>
            <div className="font-semibold tracking-tight">FinAgent</div>
            <div className="text-xs text-muted-foreground">Self-hosted · Zero telemetry</div>
          </div>
        </div>
        {nav.map((item) => {
          const tradeLike = item.kind === "trade" || item.kind === "fno";
          const active = navActive(item, location.pathname, location.search, false);
          const className = cn(
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
            active ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/60",
          );
          const content = (
            <>
              <item.icon className="h-4 w-4" />
              <span className="flex-1">{item.label}</span>
              {item.id === "automation" && unread > 0 && (
                <span className="text-[10px] rounded-full bg-primary/90 text-primary-foreground px-1.5 min-w-[1.25rem] text-center">
                  {unread > 9 ? "9+" : unread}
                </span>
              )}
            </>
          );
          if (tradeLike) {
            return (
              <Link
                key={item.id}
                to={item.to}
                className={className}
                aria-current={active ? "page" : undefined}
              >
                {content}
              </Link>
            );
          }
          return (
            <NavLink
              key={item.id}
              to={item.to}
              end={item.id === "agent"}
              className={({ isActive }) => {
                const linkActive = navActive(item, location.pathname, location.search, isActive);
                return cn(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                  linkActive
                    ? "bg-accent text-foreground"
                    : "text-muted-foreground hover:bg-accent/60",
                );
              }}
            >
              {content}
            </NavLink>
          );
        })}
        <div className="mt-auto pt-4 space-y-3">
          <p className="text-[11px] text-muted-foreground px-2 leading-relaxed">
            Not financial advice. Educational tool only. Markets involve risk of loss. Paper trading
            by default.
          </p>
          <Button
            variant="ghost"
            className="w-full justify-start"
            onClick={() => {
              clearToken();
              navigate("/login");
            }}
          >
            <LogOut className="h-4 w-4" /> Sign out
          </Button>
        </div>
      </aside>

      <main className="flex-1 overflow-auto pb-24 md:pb-10 flex flex-col min-h-0">
        {apiDown && (
          <div className="shrink-0 border-b border-amber-500/40 bg-amber-500/10 px-4 py-2 text-sm text-amber-100 flex flex-wrap items-center gap-2 justify-between">
            <span>
              Cannot reach the FinAgent API. Keep START.bat running, or clear a wrong phone/APK server
              URL.
            </span>
            <Button
              size="sm"
              variant="outline"
              className="border-amber-500/50"
              onClick={() => {
                setApiBase("");
                window.location.reload();
              }}
            >
              Clear API URL & reload
            </Button>
          </div>
        )}
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur px-4 py-3 flex items-center justify-between shrink-0 gap-2">
          <div className="text-sm text-muted-foreground">
            Press <kbd className="px-1.5 py-0.5 rounded border text-xs">Ctrl K</kbd> to search
          </div>
          <div className="flex items-center gap-2">
            <Button
              size="sm"
              variant="destructive"
              title="Blocks all orders instantly"
              onClick={async () => {
                try {
                  await api("/api/settings", {
                    method: "PUT",
                    body: JSON.stringify({ settings: { trading: { kill_switch: true } } }),
                  });
                } catch {
                  /* ignore */
                }
              }}
            >
              Panic Stop
            </Button>
            <CommandPalette />
          </div>
        </header>
        <div
          className={cn(
            "p-3 md:p-6 mx-auto w-full flex-1",
            isTrading ? "max-w-none" : "max-w-7xl",
          )}
        >
          <Outlet />
        </div>
        <footer className="border-t border-border/60 px-4 py-2 text-center text-[10px] md:text-[11px] text-muted-foreground leading-relaxed shrink-0 hidden md:block">
          FinAgent is an educational, self-hosted tool — <strong>not financial, investment, tax, or
          legal advice</strong>. Trading involves risk of loss. Past performance does not guarantee
          future results. You are solely responsible for your decisions.
        </footer>
      </main>

      <nav className="md:hidden fixed bottom-0 inset-x-0 border-t border-border bg-card/95 backdrop-blur z-30 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        <div className="flex justify-start gap-1 overflow-x-auto px-1 py-2 scrollbar-none">
          {nav.map((item) => {
            const tradeLike = item.kind === "trade" || item.kind === "fno";
            const active = navActive(item, location.pathname, location.search, false);
            const className = cn(
              "flex flex-col items-center gap-0.5 text-[10px] px-2 min-w-[3.25rem] shrink-0",
              active ? "text-primary" : "text-muted-foreground",
            );
            if (tradeLike) {
              return (
                <Link
                  key={item.id}
                  to={item.to}
                  className={className}
                  aria-current={active ? "page" : undefined}
                >
                  <item.icon className="h-5 w-5" />
                  {item.label}
                </Link>
              );
            }
            return (
              <NavLink
                key={item.id}
                to={item.to}
                end={item.id === "agent"}
                className={({ isActive }) => {
                  const linkActive = navActive(item, location.pathname, location.search, isActive);
                  return cn(
                    "flex flex-col items-center gap-0.5 text-[10px] px-2 min-w-[3.25rem] shrink-0",
                    linkActive ? "text-primary" : "text-muted-foreground",
                  );
                }}
              >
                <item.icon className="h-5 w-5" />
                {item.label}
              </NavLink>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
