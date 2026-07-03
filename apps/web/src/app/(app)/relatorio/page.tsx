"use client";

import { pct, pp } from "@/lib/fund";
import { useFund } from "@/components/app/fund-context";
import { NarrativeCard } from "@/components/app/narrative-card";
import { ApprovalFlow } from "@/components/app/approval-flow";
import { SectionTitle } from "@/components/app/kpi";

export default function RelatorioPage() {
  const { fundo } = useFund();
  const r = fundo.resumo;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="font-display text-2xl font-semibold text-foreground">Relatório</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Comentário de gestão gerado a partir da atribuição · {fundo.fundo.periodo}
          </p>
        </div>
      </div>

      <ApprovalFlow />

      {/* pré-visualização estilo documento */}
      <div className="rounded-xl border border-border bg-card p-8">
        <div className="border-b border-border pb-4">
          <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
            Comentário de performance
          </p>
          <h2 className="font-display mt-1 text-xl font-semibold text-foreground">{fundo.fundo.nome}</h2>
          <p className="text-sm text-muted-foreground">
            {fundo.fundo.classe} · benchmark {fundo.fundo.benchmark} · {fundo.fundo.periodo}
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4 py-5">
          <Stat label="Retorno da cota" value={pct(r.retorno_cota)} />
          <Stat label="Excesso vs CDI" value={pp(r.excesso_pp)} />
          <Stat label="Alpha" value={pp(r.alpha_pp)} />
        </div>

        <SectionTitle>Síntese</SectionTitle>
        <NarrativeCard />

        <p className="mt-6 text-[11px] leading-relaxed text-muted-foreground">
          Documento gerado pelo Prisma a partir dos dados de atribuição do período. As afirmações
          são fundamentadas nos trechos citados; números conferem com a soma das contribuições por
          estratégia. Uso interno — dados fictícios neste exemplo.
        </p>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="font-display tabular mt-1 text-2xl font-semibold text-foreground">{value}</p>
    </div>
  );
}
