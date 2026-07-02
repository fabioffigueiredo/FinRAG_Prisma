"use client";

import { useState } from "react";
import { ChevronDown, Check } from "lucide-react";
import { FUNDS } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { cn } from "@/lib/utils";
import { BACKENDS, useBackend } from "@/components/app/backend-context";
import { PrismaMark } from "@/components/brand/logo";

export function Topbar() {
  const { backend, setBackend } = useBackend();
  const { codigo, fundo, setCodigo } = useFund();
  const [aberto, setAberto] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-4 border-b border-border bg-background/70 px-4 backdrop-blur-xl md:px-6">
      <div className="flex items-center gap-3">
        <div className="md:hidden">
          <PrismaMark />
        </div>

        <div className="relative">
          <button
            onClick={() => setAberto((v) => !v)}
            aria-expanded={aberto}
            className="group flex items-center gap-2 rounded-lg border border-border bg-card px-3 py-1.5 text-left transition-colors hover:border-primary/40"
          >
            <div className="leading-tight">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-foreground">{fundo.fundo.nome}</span>
                <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                  {codigo}
                </span>
              </div>
              <span className="text-[11px] text-muted-foreground">
                {fundo.fundo.classe} · {fundo.fundo.benchmark}
              </span>
            </div>
            <ChevronDown
              className={cn("h-4 w-4 text-muted-foreground transition-transform", aberto && "rotate-180")}
              strokeWidth={1.75}
            />
          </button>

          {aberto && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setAberto(false)} />
              <div className="absolute left-0 top-full z-50 mt-1.5 w-72 rounded-lg border border-border bg-popover p-1 shadow-xl">
                {Object.entries(FUNDS).map(([cod, f]) => (
                  <button
                    key={cod}
                    onClick={() => {
                      setCodigo(cod);
                      setAberto(false);
                    }}
                    className={cn(
                      "flex w-full items-center justify-between rounded-md px-3 py-2 text-left transition-colors hover:bg-muted",
                      cod === codigo && "bg-muted/60",
                    )}
                  >
                    <span className="leading-tight">
                      <span className="block text-sm text-foreground">{f.fundo.nome}</span>
                      <span className="text-[11px] text-muted-foreground">
                        {f.fundo.classe} · {f.fundo.benchmark}
                      </span>
                    </span>
                    {cod === codigo && <Check className="h-4 w-4 text-primary" strokeWidth={2} />}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>

        <div className="hidden items-center gap-2 rounded-lg border border-border bg-card px-3 py-2 lg:flex">
          <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Período</span>
          <span className="text-sm text-foreground">{fundo.fundo.periodo}</span>
        </div>
      </div>

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
