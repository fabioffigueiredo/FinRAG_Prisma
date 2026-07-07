"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ChevronDown, Check } from "lucide-react";
import { FUNDS } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { cn } from "@/lib/utils";
import { popover } from "@/lib/motion";
import { BACKENDS, useBackend } from "@/components/app/backend-context";
import { MobileNav } from "@/components/app/mobile-nav";

export function Topbar() {
  const { backend, setBackend } = useBackend();
  const { codigo, fundo, setCodigo } = useFund();
  const [aberto, setAberto] = useState(false);

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between gap-2 border-b border-border bg-background/70 px-3 backdrop-blur-xl sm:gap-4 md:px-6">
      <div className="flex min-w-0 items-center gap-2 sm:gap-3">
        <MobileNav />

        <div className="relative min-w-0">
          <button
            onClick={() => setAberto((v) => !v)}
            aria-expanded={aberto}
            className="group flex min-w-0 items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-left transition-colors hover:border-primary/40 sm:px-3"
          >
            <div className="min-w-0 leading-tight">
              <div className="flex items-center gap-2">
                <span className="max-w-[40vw] truncate text-sm font-medium text-foreground sm:max-w-none">
                  {fundo.fundo.nome}
                </span>
                <span className="hidden rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground sm:inline">
                  {codigo}
                </span>
              </div>
              <span className="hidden truncate text-[11px] text-muted-foreground sm:block">
                {fundo.fundo.classe} · {fundo.fundo.benchmark}
              </span>
            </div>
            <ChevronDown
              className={cn("h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200", aberto && "rotate-180")}
              strokeWidth={1.75}
            />
          </button>

          <AnimatePresence>
            {aberto && (
              <>
                <div className="fixed inset-0 z-40" onClick={() => setAberto(false)} />
                <motion.div
                  variants={popover}
                  initial="hidden"
                  animate="show"
                  exit="exit"
                  style={{ transformOrigin: "top left" }}
                  className="absolute left-0 top-full z-50 mt-1.5 w-72 origin-top-left rounded-lg border border-border bg-popover p-1 shadow-2xl shadow-black/40"
                >
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
                </motion.div>
              </>
            )}
          </AnimatePresence>
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
        <div className="flex items-center gap-0.5 rounded-lg border border-border bg-muted/40 p-1">
          {BACKENDS.map((b) => {
            const ativo = backend === b.id;
            return (
              <button
                key={b.id}
                onClick={() => setBackend(b.id)}
                title={b.hint}
                aria-pressed={ativo}
                className={cn(
                  "relative rounded-md px-3 py-1.5 text-xs font-medium transition-colors duration-200",
                  ativo
                    ? "text-primary-foreground"
                    : "text-muted-foreground hover:bg-card hover:text-foreground",
                )}
              >
                {ativo && (
                  <motion.span
                    layoutId="motor-active"
                    className="absolute inset-0 rounded-md bg-primary shadow-sm shadow-primary/30"
                    transition={{ type: "spring", stiffness: 420, damping: 34 }}
                  />
                )}
                <span className="relative">{b.label}</span>
              </button>
            );
          })}
        </div>
      </div>
    </header>
  );
}
