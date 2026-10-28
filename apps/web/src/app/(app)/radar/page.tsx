"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { ExternalLink, Radio } from "lucide-react";
import { getRadar, type Manchete, type Noticia, type RadarResp } from "@/lib/api";
import { haQuanto, useFeedRadar } from "@/components/app/use-feed-radar";
import { PageStagger, Item } from "@/components/app/reveal";
import { easeOutQuint } from "@/lib/motion";
import { cn } from "@/lib/utils";

const TONS: Record<NonNullable<Noticia["sentimento"]>, string> = {
  positivo: "border-[var(--success)]/30 bg-[var(--success)]/10 text-[var(--success)]",
  negativo: "border-[var(--destructive)]/30 bg-[var(--destructive)]/10 text-[var(--destructive)]",
  neutro: "border-border bg-muted/40 text-muted-foreground",
};

function ManchetesAoVivo() {
  const feed = useFeedRadar();

  return (
    <section aria-labelledby="manchetes-titulo" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Radio className="h-4 w-4 text-primary" strokeWidth={1.75} />
        <h2 id="manchetes-titulo" className="text-sm font-semibold text-foreground">Manchetes ao vivo</h2>
        <span className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
          não classificado — sem sinal
        </span>
        {feed?.atualizado_em && (
          <span className="tabular ml-auto text-[11px] text-muted-foreground">
            última coleta {new Date(feed.atualizado_em).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
            {" · "}atualiza a cada minuto
          </span>
        )}
      </div>

      {!feed ? (
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <div key={i} className="h-12 animate-pulse rounded-lg bg-muted/40" />
          ))}
        </div>
      ) : feed.erro ? (
        <p role="alert" className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-[var(--destructive)]">
          {feed.erro}
        </p>
      ) : !feed.ok ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          {feed.motivo ?? "Nenhuma manchete relevante nas últimas 24 horas."}
        </p>
      ) : (
        <>
          <p className="text-[12px] text-muted-foreground">{feed.aviso}</p>
          {feed.desatualizado && (
            <p role="status" className="text-[12px] text-[var(--chart-5)]">
              Não foi possível atualizar agora ({feed.desatualizado}). Mostrando a última lista recebida.
            </p>
          )}
          <ul className="divide-y divide-border overflow-hidden rounded-xl border border-border bg-card">
            <AnimatePresence initial={false}>
              {feed.itens.map((m: Manchete) => (
                <motion.li
                  key={m.id}
                  layout
                  initial={{ opacity: 0, y: -6 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3, ease: easeOutQuint }}
                  className="flex items-start gap-3 px-4 py-3"
                >
                  <div className="min-w-0 flex-1">
                    <a
                      href={m.link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-sm font-medium text-foreground underline-offset-2 hover:underline"
                    >
                      {m.titulo}
                    </a>
                    <p className="mt-0.5 text-[12px] text-muted-foreground">
                      {m.portal} · <time dateTime={m.publicada_em}>{haQuanto(m.publicada_em)}</time>
                    </p>
                  </div>
                  <ExternalLink className="mt-1 h-3.5 w-3.5 shrink-0 text-muted-foreground" strokeWidth={1.75} aria-hidden />
                </motion.li>
              ))}
            </AnimatePresence>
          </ul>
        </>
      )}
    </section>
  );
}

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
    <PageStagger className="mx-auto max-w-5xl space-y-8">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Radar de Mercado</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manchetes públicas recentes de portais financeiros, coletadas automaticamente. O sinal de
          sentimento só aparece quando há classificação local validada. O Radar dá contexto, não recomendação.
        </p>
      </Item>

      <Item>
        <ManchetesAoVivo />
      </Item>

      <Item className="space-y-3">
        <h2 className="text-sm font-semibold text-foreground">Sinal de sentimento (experimental)</h2>
        {!radar ? (
          <div className="h-16 animate-pulse rounded-xl bg-muted/40" />
        ) : !radar.ok ? (
          <p className="rounded-xl border border-dashed border-border p-5 text-sm text-muted-foreground">
            Desligado: nenhuma manchete foi classificada localmente com confiança suficiente. O classificador
            só será habilitado depois da avaliação com manchetes revisadas em português e inglês.
          </p>
        ) : (
          <>
            {radar.motivo && (
              <p className="border-l-2 border-primary bg-muted/30 px-4 py-3 text-sm text-muted-foreground">{radar.motivo}</p>
            )}
            <div className="flex flex-wrap gap-2">
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
            </div>
            <ul className="space-y-3">
              {noticias.map((n) => (
                <li key={n.id} className="card-surface p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-medium text-foreground">{n.titulo}</p>
                      <p className="mt-1 text-[13px] text-muted-foreground">
                        {n.portal} · publicada em {new Date(n.publicada_em).toLocaleString("pt-BR")}
                      </p>
                    </div>
                    <span className={cn("shrink-0 rounded-md border px-2 py-0.5 text-[11px]", n.sentimento ? TONS[n.sentimento] : "border-border bg-muted/40 text-muted-foreground")}>
                      {n.sentimento ?? "pendente"}
                    </span>
                  </div>
                  <div className="mt-2 flex items-center gap-3 text-[11px] text-muted-foreground">
                    <a href={n.link} target="_blank" rel="noreferrer" className="underline underline-offset-2 hover:text-foreground">Abrir fonte</a>
                    {n.confianca !== null && <span>confiança {Math.round(n.confianca * 100)}%</span>}
                    <span className="font-mono ml-auto">{n.classificador ?? "sem classificador"}</span>
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </Item>
    </PageStagger>
  );
}
