"use client";

import { pct, pp, brlMM, num } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { Kpi, SectionTitle } from "@/components/app/kpi";
import { NarrativeCard } from "@/components/app/narrative-card";
import { PerformanceLine } from "@/components/charts/performance-line";
import { ContributionBars } from "@/components/charts/contribution-bars";

export default function CockpitPage() {
  const { fundo } = useFund();
  const r = fundo.resumo;
  const bench = fundo.fundo.benchmark;
  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">Cockpit</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {fundo.fundo.nome} · atribuição de performance · {fundo.fundo.periodo}
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Retorno da cota" value={pct(r.retorno_cota)} sub={`Benchmark (${bench}): ${pct(r.retorno_bench)}`} accent />
        <Kpi label={`Excesso vs ${bench}`} value={pp(r.excesso_pp)} sub={`${r.pct_cdi.toLocaleString("pt-BR")}% do ${bench}`} tone="positive" />
        <Kpi label="Alpha" value={pp(r.alpha_pp)} sub={`Beta ${r.beta.toLocaleString("pt-BR")} · vol ${pct(r.vol_anual, 1)} a.a.`} tone="positive" />
        <Kpi label="Patrimônio" value={brlMM(r.patrimonio_mm)} sub={`${num(r.num_cotistas)} cotistas`} />
      </div>

      <NarrativeCard />

      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-2">
          <SectionTitle hint="acumulado no período">Rentabilidade: cota × benchmark</SectionTitle>
          <div className="h-[240px]">
            <PerformanceLine serie={fundo.serie_diaria} />
          </div>
          <div className="mt-2 flex items-center gap-4 text-[11px] text-muted-foreground">
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded bg-[var(--chart-1)]" /> Cota do fundo
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-0.5 w-4 rounded bg-[var(--muted-foreground)]" /> {bench}
            </span>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5">
          <SectionTitle hint="pp no período">Contribuição por estratégia</SectionTitle>
          <ContributionBars estrategias={fundo.estrategias} />
        </div>
      </div>
    </div>
  );
}
