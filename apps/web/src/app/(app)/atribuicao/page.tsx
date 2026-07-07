"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight } from "lucide-react";
import { ativosDe, pp, pct, sinalClasse } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { SectionTitle } from "@/components/app/kpi";
import { ContributionBars } from "@/components/charts/contribution-bars";
import { Waterfall } from "@/components/charts/waterfall";
import { PageStagger, Item } from "@/components/app/reveal";
import { Table, TableHeader, TableRow, TableHead, TableCell } from "@/components/ui/table";
import { easeOutQuint } from "@/lib/motion";
import { cn } from "@/lib/utils";

export default function AtribuicaoPage() {
  const { fundo } = useFund();
  const [sel, setSel] = useState(fundo.estrategias[0].nome);
  useEffect(() => {
    setSel(fundo.estrategias[0].nome);
  }, [fundo]);
  const ativos = ativosDe(fundo, sel);

  return (
    <PageStagger className="mx-auto max-w-7xl space-y-6">
      <Item>
        <h1 className="font-display text-2xl font-semibold text-foreground">Atribuição</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Decomposição do retorno da cota por estratégia e ativo · {fundo.fundo.periodo}
        </p>
      </Item>

      <Item className="card-surface p-5">
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
      </Item>

      <Item className="grid gap-4 lg:grid-cols-5">
        <div className="card-surface p-5 lg:col-span-2">
          <SectionTitle hint="clique para detalhar">Contribuição por estratégia</SectionTitle>
          <ContributionBars estrategias={fundo.estrategias} onSelect={setSel} selected={sel} />
        </div>

        <div className="card-surface p-5 lg:col-span-3">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-foreground">Ativos — {sel}</h2>
              <p className="text-[11px] text-muted-foreground">contribuição e peso médio no período</p>
            </div>
            <Link
              href="/copiloto"
              className="group flex items-center gap-1 text-[11px] text-primary/90 transition-colors hover:text-primary"
            >
              Perguntar ao Prisma
              <ArrowUpRight className="h-3.5 w-3.5 transition-transform group-hover:translate-x-0.5 group-hover:-translate-y-0.5" strokeWidth={1.75} />
            </Link>
          </div>

          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="px-0 pb-2 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Ativo</TableHead>
                <TableHead className="px-0 pb-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Peso médio</TableHead>
                <TableHead className="px-0 pb-2 text-right text-[11px] font-medium uppercase tracking-wide text-muted-foreground">Contribuição</TableHead>
              </TableRow>
            </TableHeader>
            <AnimatePresence mode="wait">
              <motion.tbody
                key={sel}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="[&_tr:last-child]:border-0"
              >
                {ativos.map((a, i) => (
                  <motion.tr
                    key={a.ativo}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, ease: easeOutQuint, delay: i * 0.03 }}
                    className="border-b border-border/50 transition-colors hover:bg-muted/20"
                  >
                    <TableCell className="px-0 py-2.5 text-foreground">{a.ativo}</TableCell>
                    <TableCell className="tabular px-0 py-2.5 text-right text-muted-foreground">{pct(a.peso_medio, 1)}</TableCell>
                    <TableCell className={cn("tabular px-0 py-2.5 text-right font-medium", sinalClasse(a.contribuicao_pp))}>
                      {pp(a.contribuicao_pp)}
                    </TableCell>
                  </motion.tr>
                ))}
                {ativos.length === 0 && (
                  <tr>
                    <TableCell colSpan={3} className="py-6 text-center text-sm text-muted-foreground">
                      Estratégia sem ativos detalhados neste exemplo.
                    </TableCell>
                  </tr>
                )}
              </motion.tbody>
            </AnimatePresence>
          </Table>
        </div>
      </Item>
    </PageStagger>
  );
}
