"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight } from "lucide-react";
import { ativosDe, pp, pct, sinalClasse } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { SectionTitle } from "@/components/app/kpi";
import { ContributionBars } from "@/components/charts/contribution-bars";
import { Waterfall } from "@/components/charts/waterfall";
import { cn } from "@/lib/utils";

export default function AtribuicaoPage() {
  const { fundo } = useFund();
  const [sel, setSel] = useState(fundo.estrategias[0].nome);
  useEffect(() => {
    setSel(fundo.estrategias[0].nome);
  }, [fundo]);
  const ativos = ativosDe(fundo, sel);

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">Atribuição</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Decomposição do retorno da cota por estratégia e ativo · {fundo.fundo.periodo}
        </p>
      </div>

      <div className="rounded-xl border border-border bg-card p-5">
        <SectionTitle hint="cada barra soma ao retorno da cota">
          Como o retorno foi construído
        </SectionTitle>
        <div className="h-[300px]">
          <Waterfall
            estrategias={fundo.estrategias}
            total={fundo.resumo.retorno_cota}
            benchmark={fundo.resumo.retorno_bench}
            benchLabel={fundo.fundo.benchmark}
          />
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-2">
          <SectionTitle hint="clique para detalhar">Contribuição por estratégia</SectionTitle>
          <ContributionBars estrategias={fundo.estrategias} onSelect={setSel} selected={sel} />
        </div>

        <div className="rounded-xl border border-border bg-card p-5 lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Ativos — {sel}</h2>
              <p className="text-[11px] text-muted-foreground">contribuição e peso médio no período</p>
            </div>
            <Link
              href="/copiloto"
              className="flex items-center gap-1 text-[11px] text-primary/90 transition-colors hover:text-primary"
            >
              Perguntar ao Prisma <ArrowUpRight className="h-3.5 w-3.5" strokeWidth={1.75} />
            </Link>
          </div>

          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-[11px] uppercase tracking-wide text-muted-foreground">
                <th className="pb-2 text-left font-medium">Ativo</th>
                <th className="pb-2 text-right font-medium">Peso médio</th>
                <th className="pb-2 text-right font-medium">Contribuição</th>
              </tr>
            </thead>
            <tbody>
              {ativos.map((a) => (
                <tr key={a.ativo} className="border-b border-border/50 last:border-0">
                  <td className="py-2.5 text-foreground">{a.ativo}</td>
                  <td className="tabular py-2.5 text-right text-muted-foreground">{pct(a.peso_medio, 1)}</td>
                  <td className={cn("tabular py-2.5 text-right font-medium", sinalClasse(a.contribuicao_pp))}>
                    {pp(a.contribuicao_pp)}
                  </td>
                </tr>
              ))}
              {ativos.length === 0 && (
                <tr>
                  <td colSpan={3} className="py-6 text-center text-sm text-muted-foreground">
                    Estratégia sem ativos detalhados neste exemplo.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
