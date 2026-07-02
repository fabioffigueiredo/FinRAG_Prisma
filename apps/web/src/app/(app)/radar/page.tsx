"use client";

import { useEffect, useState } from "react";
import { getRadar, type Noticia, type RadarResp } from "@/lib/api";
import { cn } from "@/lib/utils";

const TONS: Record<Noticia["sentimento"], string> = {
  positivo: "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]",
  negativo: "border-[var(--destructive)]/30 bg-[var(--destructive)]/10 text-[var(--destructive)]",
  neutro: "border-border bg-muted/40 text-muted-foreground",
};

export default function RadarPage() {
  const [radar, setRadar] = useState<RadarResp | null>(null);
  const [filtro, setFiltro] = useState<string>("todas");

  useEffect(() => {
    getRadar().then(setRadar);
  }, []);

  const estrategias = radar ? Object.keys(radar.agregado) : [];
  const noticias = (radar?.noticias ?? []).filter(
    (n) => filtro === "todas" || n.estrategia === filtro,
  );

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">Radar de Mercado</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Notícias do período classificadas pelo pipeline de sentimento do FinNLP e indexadas no
          RAG — o copiloto as cita ao explicar o &ldquo;porquê de mercado&rdquo;.
        </p>
      </div>

      {!radar?.ok ? (
        <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Sem notícias indexadas — rode <span className="font-mono">scripts/classificar_noticias.py</span> e
          suba a Prisma API.
        </div>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {["todas", ...estrategias].map((e) => (
              <button
                key={e}
                onClick={() => setFiltro(e)}
                className={cn(
                  "rounded-full border px-3 py-1 text-[12px] transition-colors",
                  filtro === e
                    ? "border-primary/40 bg-primary/10 text-primary"
                    : "border-border bg-card text-muted-foreground hover:text-foreground",
                )}
              >
                {e}
              </button>
            ))}
          </div>

          <ul className="space-y-3">
            {noticias.map((n) => (
              <li key={n.id} className="rounded-xl border border-border bg-card p-4">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-foreground">{n.titulo}</p>
                    <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">{n.corpo}</p>
                  </div>
                  <span className={cn("shrink-0 rounded-md border px-2 py-0.5 text-[11px]", TONS[n.sentimento])}>
                    {n.sentimento}
                  </span>
                </div>
                <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                  <span className="font-mono">{n.data}</span>
                  <span>·</span>
                  <span>{n.estrategia}</span>
                  <span className="font-mono ml-auto">noticia:{n.id}</span>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
