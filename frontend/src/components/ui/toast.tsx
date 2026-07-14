/** Lightweight toast notifications. */

import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Toast = { id: number; message: string; tone?: "info" | "error" | "success" };

type ToastCtx = {
  push: (message: string, tone?: Toast["tone"]) => void;
};

const Ctx = createContext<ToastCtx>({ push: () => undefined });

let seq = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((message: string, tone: Toast["tone"] = "info") => {
    const id = ++seq;
    setItems((t) => [...t, { id, message, tone }]);
    window.setTimeout(() => setItems((t) => t.filter((x) => x.id !== id)), 4500);
  }, []);
  const value = useMemo(() => ({ push }), [push]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <div className="fixed bottom-20 md:bottom-6 right-4 z-[100] flex flex-col gap-2 max-w-sm">
        {items.map((t) => (
          <div
            key={t.id}
            className={cn(
              "rounded-lg border px-3 py-2 text-sm shadow-lg bg-background/95 backdrop-blur",
              t.tone === "error" && "border-red-500/50 text-red-200",
              t.tone === "success" && "border-emerald-500/50 text-emerald-200",
              t.tone === "info" && "border-border text-foreground",
            )}
          >
            {t.message}
          </div>
        ))}
      </div>
    </Ctx.Provider>
  );
}

export function useToast() {
  return useContext(Ctx);
}
