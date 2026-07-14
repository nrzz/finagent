import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Bot,
  Briefcase,
  LayoutDashboard,
  LineChart,
  LogOut,
  Settings,
  Sparkles,
  Zap,
  CandlestickChart,
  Bell,
} from "lucide-react";
import { clearToken } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { CommandPalette } from "@/components/CommandPalette";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Agent", icon: Bot },
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { to: "/portfolio", label: "Portfolio", icon: Briefcase },
  { to: "/markets", label: "Markets", icon: LineChart },
  { to: "/trading", label: "Trading", icon: Zap },
  { to: "/fno", label: "F&O", icon: CandlestickChart },
  { to: "/automation", label: "Auto", icon: Bell },
  { to: "/settings", label: "Settings", icon: Settings },
];

export function AppShell() {
  const navigate = useNavigate();
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
        {nav.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                isActive ? "bg-accent text-foreground" : "text-muted-foreground hover:bg-accent/60",
              )
            }
          >
            <item.icon className="h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
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
        <header className="sticky top-0 z-20 border-b border-border bg-background/80 backdrop-blur px-4 py-3 flex items-center justify-between shrink-0">
          <div className="text-sm text-muted-foreground">
            Press <kbd className="px-1.5 py-0.5 rounded border text-xs">Ctrl K</kbd> to search
          </div>
          <CommandPalette />
        </header>
        <div className="p-3 md:p-6 max-w-7xl mx-auto w-full flex-1">
          <Outlet />
        </div>
        <footer className="border-t border-border/60 px-4 py-2 text-center text-[10px] md:text-[11px] text-muted-foreground leading-relaxed shrink-0 hidden md:block">
          FinAgent is an educational, self-hosted tool — <strong>not financial, investment, tax, or
          legal advice</strong>. Trading involves risk of loss. Past performance does not guarantee
          future results. You are solely responsible for your decisions.
        </footer>
      </main>

      <nav className="md:hidden fixed bottom-0 inset-x-0 border-t border-border bg-card/95 backdrop-blur flex justify-around py-2 z-30 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
        {nav.filter((i) => ["/", "/portfolio", "/markets", "/trading", "/settings"].includes(i.to)).map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              cn(
                "flex flex-col items-center gap-0.5 text-[10px] px-2 min-w-[3.25rem]",
                isActive ? "text-primary" : "text-muted-foreground",
              )
            }
          >
            <item.icon className="h-5 w-5" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
