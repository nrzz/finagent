import { useEffect, useState } from "react";
import { Command } from "cmdk";
import { useNavigate } from "react-router-dom";
import { api } from "@/lib/api";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<{ symbol: string; name: string }[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!query.trim()) {
      setResults([]);
      return;
    }
    const t = setTimeout(() => {
      api<{ results: { symbol: string; name: string }[] }>(
        `/api/market/search?q=${encodeURIComponent(query)}`,
      )
        .then((r) => setResults(r.results || []))
        .catch(() => setResults([]));
    }, 250);
    return () => clearTimeout(t);
  }, [query]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-start justify-center pt-[15vh]" onClick={() => setOpen(false)}>
      <Command
        className="w-full max-w-lg rounded-xl border bg-card shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <Command.Input
          value={query}
          onValueChange={setQuery}
          placeholder="Search symbols or jump to page…"
          className="w-full border-b bg-transparent px-4 py-3 text-sm outline-none"
        />
        <Command.List className="max-h-80 overflow-auto p-2">
          <Command.Empty className="px-3 py-6 text-sm text-muted-foreground text-center">
            No results
          </Command.Empty>
          <Command.Group heading="Navigate">
            {[
              ["Agent Chat", "/"],
              ["Dashboard", "/dashboard"],
              ["Portfolio", "/portfolio"],
              ["Trade", "/trading"],
              ["F&O", "/trading?mode=fno"],
              ["Automation", "/automation"],
              ["Settings", "/settings"],
            ].map(([label, path]) => (
              <Command.Item
                key={path}
                value={label}
                onSelect={() => {
                  navigate(path);
                  setOpen(false);
                }}
                className="px-3 py-2 rounded-md text-sm cursor-pointer aria-selected:bg-accent"
              >
                {label}
              </Command.Item>
            ))}
          </Command.Group>
          {results.length > 0 && (
            <Command.Group heading="Symbols">
              {results.map((r) => (
                <Command.Item
                  key={r.symbol}
                  value={r.symbol}
                  onSelect={() => {
                    navigate(`/trading?symbol=${encodeURIComponent(r.symbol)}`);
                    setOpen(false);
                  }}
                  className="px-3 py-2 rounded-md text-sm cursor-pointer aria-selected:bg-accent"
                >
                  <span className="font-mono">{r.symbol}</span>
                  <span className="text-muted-foreground ml-2">{r.name}</span>
                </Command.Item>
              ))}
            </Command.Group>
          )}
        </Command.List>
      </Command>
    </div>
  );
}
