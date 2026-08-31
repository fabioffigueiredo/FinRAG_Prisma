"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { getRadar, type Noticia, type RadarResp } from "@/lib/api";
import { PageStagger, Item } from "@/components/app/reveal";
import { easeOutQuint } from "@/lib/motion";
import { cn } from "@/lib/utils";

const TONS: Record<NonNullable<Noticia["sentimento"]>, string> = {
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
    <PageStagger className="mx-auto max-w-5xl space-y-6">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Radar de Mercado</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manchetes públicas recentes passam por filtros de relevância e classificação experimental.
          Só itens locais com confiança suficiente entram no agregado. O Radar dá contexto, não recomendação.
        </p>
      </Item>

      {!radar ? (
        <Item className="space-y-3">
          <div className="flex gap-2">
            {[64, 88, 72, 80].map((w, i) => (
              <div key={i} className="h-7 animate-pulse rounded-full bg-muted/50" style={{ width: w }} />
            ))}
          </div>
          {[0, 1, 2].map((i) => (
            <div key={i} className="animate-pulse card-surface p-4">
              <div className="h-4 w-2/3 rounded bg-muted/50" />
              <div className="mt-2 h-3 w-full rounded bg-muted/40" />
              <div className="mt-1.5 h-3 w-4/5 rounded bg-muted/40" />
            </div>
          ))}
        </Item>
      ) : !radar.ok ? (
        <Item className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          {radar.motivo ?? "Sem manchetes recentes classificadas com confiança suficiente."}
        </Item>
      ) : (
        <>
          {radar.motivo && (
            <Item className="border-l-2 border-primary bg-muted/30 px-4 py-3 text-sm text-muted-foreground">
              {radar.motivo}
            </Item>
          )}
          <Item className="flex flex-wrap gap-2">
            {["todas", ...estrategias].map((e) => {
              const ativo = filtro === e;
              return (
                <motion.button
                  key={e}
                  onClick={() => setFiltro(e)}
                  whileTap={{ scale: 0.95 }}
                  className={cn(
                    "relative rounded-full border px-3 py-1 text-[12px] transition-colors",
                    ativo
                      ? "border-primary/40 text-primary"
                      : "border-border bg-card text-muted-foreground hover:text-foreground",
                  )}
                >
                  {ativo && (
                    <motion.span
                      layoutId="radar-filtro"
                      className="absolute inset-0 rounded-full bg-primary/10"
                      transition={{ type: "spring", stiffness: 420, damping: 34 }}
                    />
                  )}
                  <span className="relative">{e}</span>
                </motion.button>
              );
            })}
          </Item>

          <motion.ul layout className="space-y-3">
            <AnimatePresence mode="popLayout">
              {noticias.map((n, i) => (
                <motion.li
                  key={n.id}
                  layout
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.97 }}
                  transition={{ duration: 0.35, ease: easeOutQuint, delay: Math.min(i * 0.04, 0.3) }}
                  className="card-surface p-4 transition-colors hover:border-primary/30"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">{n.titulo}</p>
                      <p className="mt-1 text-[13px] leading-relaxed text-muted-foreground">
                        {n.portal} · publicada em {new Date(n.publicada_em).toLocaleString("pt-BR")}
                      </p>
                    </div>
                    <span className={cn("shrink-0 rounded-md border px-2 py-0.5 text-[11px]", n.sentimento ? TONS[n.sentimento] : "border-border bg-muted/40 text-muted-foreground")}>
                      {n.estado === "classificado_local" ? n.sentimento : n.estado === "revisao_assistida" ? "revisão assistida" : "pendente"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                    <a href={n.link} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-foreground">Abrir fonte</a>
                    {n.confianca !== null && <span>confiança {Math.round(n.confianca * 100)}%</span>}
                    <span className="font-mono ml-auto">{n.classificador ?? "sem classificador"}</span>
                  </div>
                </motion.li>
              ))}
            </AnimatePresence>
          </motion.ul>
        </>
      )}
    </PageStagger>
  );
}
