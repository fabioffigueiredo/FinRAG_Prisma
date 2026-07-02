"use client";

import { useState } from "react";
import { Zap, Quote } from "lucide-react";
import { gerarNarrativa, NARRATIVA_FALLBACK, type NarrativaResp } from "@/lib/api";
import { useBackend, BACKENDS } from "@/components/app/backend-context";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

export function NarrativeCard() {
  const { backend } = useBackend();
  const [data, setData] = useState<NarrativaResp>(NARRATIVA_FALLBACK);
  const [loading, setLoading] = useState(false);

  async function gerar() {
    setLoading(true);
    const r = await gerarNarrativa(backend);
    setData(r);
    setLoading(false);
  }

  const label = BACKENDS.find((b) => b.id === backend)?.label ?? backend;
  const aoVivo = !data.fallback && data.backend !== "seed";

  return (
    <div className="relative overflow-hidden rounded-xl border border-primary/25 bg-card p-5">
      <span className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-primary/60 to-transparent" />
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Quote className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <h2 className="text-sm font-semibold text-foreground">O que aconteceu</h2>
          <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
            {aoVivo ? `gerado ao vivo · ${label}` : "narrativa · exemplo"}
          </span>
        </div>
        <button
          onClick={gerar}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2.5 py-1 text-xs text-primary transition-colors hover:bg-primary/15 disabled:opacity-50"
        >
          <Zap className={`h-3.5 w-3.5 ${loading ? "animate-pulse" : ""}`} strokeWidth={1.75} />
          {loading ? "Gerando…" : "Gerar ao vivo"}
        </button>
      </div>

      {loading ? (
        <div className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-[92%]" />
          <Skeleton className="h-4 w-[97%]" />
          <Skeleton className="h-4 w-3/4" />
        </div>
      ) : (
        <>
          <p className="text-[15px] leading-relaxed text-foreground/90">{data.texto}</p>
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Fontes</span>
            {data.citacoes.map((c, i) => (
              <Tooltip key={i}>
                <TooltipTrigger
                  render={
                    <span className="cursor-help rounded-md border border-border bg-muted/40 px-2 py-0.5 font-mono text-[11px] text-muted-foreground hover:border-primary/40 hover:text-foreground" />
                  }
                >
                  [{i + 1}] {c.fonte}
                </TooltipTrigger>
                <TooltipContent className="max-w-xs text-xs leading-snug">
                  &ldquo;{c.trecho}&rdquo;
                </TooltipContent>
              </Tooltip>
            ))}
            {aoVivo && data.latency_ms > 0 && (
              <span className="tabular ml-auto text-[11px] text-muted-foreground">
                {(data.latency_ms / 1000).toFixed(1)}s · {label}
              </span>
            )}
          </div>
        </>
      )}
    </div>
  );
}
