"use client";

import { ChevronDown } from "lucide-react";
import { fundo } from "@/lib/fund";
import { cn } from "@/lib/utils";
import { BACKENDS, useBackend } from "@/components/app/backend-context";
import { PrismaMark } from "@/components/brand/logo";

export function Topbar() {
  const { backend, setBackend } = useBackend();

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-border bg-background/70 px-4 backdrop-blur-xl md:px-6">
      <div className="flex items-center gap-3">
        <div className="md:hidden">
          <PrismaMark />
        </div>
        {/* seletor de fundo (visual no POC) */}
        <button className="group flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-left transition-colors hover:border-primary/40">
          <div className="leading-tight">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-foreground">{fundo.fundo.nome}</span>
              <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                {fundo.fundo.codigo}
              </span>
            </div>
            <span className="text-[11px] text-muted-foreground">
              {fundo.fundo.classe} · {fundo.fundo.benchmark}
            </span>
          </div>
          <ChevronDown className="h-4 w-4 text-muted-foreground" strokeWidth={1.75} />
        </button>

        <div className="hidden items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 lg:flex">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Período</span>
          <span className="text-sm text-foreground">{fundo.fundo.periodo}</span>
        </div>
      </div>

      {/* seletor de backend do modelo */}
      <div className="flex items-center gap-3">
        <span className="hidden text-[11px] uppercase tracking-wide text-muted-foreground sm:inline">
          Motor
        </span>
        <div className="flex items-center rounded-lg border border-border bg-card p-0.5">
          {BACKENDS.map((b) => (
            <button
              key={b.id}
              onClick={() => setBackend(b.id)}
              title={b.hint}
              className={cn(
                "rounded-md px-2.5 py-1.5 text-xs font-medium transition-colors duration-150",
                backend === b.id
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              {b.label}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
