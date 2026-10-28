"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "motion/react";
import { Radar as RadarIcon, ArrowUpRight } from "lucide-react";
import { getRadar, type RadarResp } from "@/lib/api";
import { useFund } from "@/components/app/fund-context";
import { SectionTitle } from "@/components/app/kpi";
import { easeOutQuint } from "@/lib/motion";
import { haQuanto, useFeedRadar } from "@/components/app/use-feed-radar";

export function RadarCard() {
  const { codigo } = useFund();
  const [radar, setRadar] = useState<RadarResp | null>(null);

  useEffect(() => {
    getRadar().then(setRadar);
  }, []);

  const feed = useFeedRadar();

  if (!radar?.ok || !Object.keys(radar.agregado).length) {
    // Sem sinal validado: mostra as manchetes recentes, rotuladas como tal,
    // em vez de o card sumir do cockpit.
    if (!feed?.ok) return null;
    return (
      <div className="card-surface p-5">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <RadarIcon className="h-4 w-4 text-primary" strokeWidth={1.75} />
            <SectionTitle hint="manchetes públicas, sem classificação de sentimento">Radar de Mercado</SectionTitle>
          </div>
          <Link href="/radar" className="flex items-center gap-1 text-[11px] text-primary/90 hover:text-primary">
            Ver todas <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.75} />
          </Link>
        </div>
        <ul className="space-y-2">
          {feed.itens.slice(0, 5).map((m) => (
            <li key={m.id} className="text-[13px] leading-snug">
              <a href={m.link} target="_blank" rel="noreferrer" className="text-foreground hover:underline">
                {m.titulo}
              </a>
              <span className="ml-1 text-[11px] text-muted-foreground">· {m.portal} · {haQuanto(m.publicada_em)}</span>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  const linhas = Object.entries(radar.agregado).sort((a, b) => b[1].liquido - a[1].liquido);

  return (
    <div className="card-surface p-5">
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RadarIcon className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <SectionTitle hint={`${Object.values(radar.agregado).reduce((total, item) => total + item.total, 0)} manchetes classificadas localmente`}>
            Radar de Mercado
          </SectionTitle>
        </div>
        <Link href="/radar" className="flex items-center gap-1 text-[11px] text-primary/90 hover:text-primary">
          Ver notícias <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.75} />
        </Link>
      </div>
      {codigo !== "ALFA-33" && (
        <p className="mb-2 text-[11px] text-muted-foreground">
          Contexto de mercado geral. Não é evidência específica deste fundo.
        </p>
      )}
      <ul className="space-y-2">
        {linhas.map(([estrategia, g], i) => (
          <li key={estrategia} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-[13px] text-foreground">{estrategia}</span>
            <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted/60">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <motion.span
                className="absolute inset-y-0 rounded-full"
                style={{
                  left: g.liquido >= 0 ? "50%" : `${50 + g.liquido * 50}%`,
                  width: `${Math.abs(g.liquido) * 50}%`,
                  backgroundColor: g.liquido >= 0 ? "var(--success)" : "var(--destructive)",
                  transformOrigin: g.liquido >= 0 ? "left" : "right",
                }}
                initial={{ scaleX: 0 }}
                animate={{ scaleX: 1 }}
                transition={{ duration: 0.6, ease: easeOutQuint, delay: 0.15 + i * 0.05 }}
              />
            </span>
            <span className="tabular w-20 shrink-0 text-right text-[12px] text-muted-foreground">
              {g.pos}+ · {g.neg}− · {g.neu}○
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
