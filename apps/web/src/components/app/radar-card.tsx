"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Radar as RadarIcon, ArrowUpRight } from "lucide-react";
import { getRadar, type RadarResp } from "@/lib/api";
import { useFund } from "@/components/app/fund-context";
import { SectionTitle } from "@/components/app/kpi";

export function RadarCard() {
  const { codigo } = useFund();
  const [radar, setRadar] = useState<RadarResp | null>(null);

  useEffect(() => {
    getRadar().then(setRadar);
  }, []);

  if (!radar?.ok) return null; // sem notícias -> card se oculta (spec)

  const linhas = Object.entries(radar.agregado).sort((a, b) => b[1].liquido - a[1].liquido);

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="mb-1 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <RadarIcon className="h-4 w-4 text-primary" strokeWidth={1.75} />
          <SectionTitle hint={`${radar.noticias.length} notícias · sentimento FinNLP`}>
            Radar de Mercado
          </SectionTitle>
        </div>
        <Link href="/radar" className="flex items-center gap-1 text-[11px] text-primary/90 hover:text-primary">
          Ver notícias <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.75} />
        </Link>
      </div>
      {codigo !== "ALFA-33" && (
        <p className="mb-2 text-[11px] text-muted-foreground">
          Notícias semeadas referem-se ao Alfa Multimercado (POC).
        </p>
      )}
      <ul className="space-y-2">
        {linhas.map(([estrategia, g]) => (
          <li key={estrategia} className="flex items-center gap-3">
            <span className="w-32 shrink-0 truncate text-[13px] text-foreground">{estrategia}</span>
            <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted/60">
              <span className="absolute inset-y-0 left-1/2 w-px bg-border" />
              <span
                className="absolute inset-y-0 rounded-full"
                style={{
                  left: g.liquido >= 0 ? "50%" : `${50 + g.liquido * 50}%`,
                  width: `${Math.abs(g.liquido) * 50}%`,
                  backgroundColor: g.liquido >= 0 ? "var(--success)" : "var(--destructive)",
                }}
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
