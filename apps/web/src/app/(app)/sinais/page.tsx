"use client";

import { useEffect, useState } from "react";
import { TriangleAlert, ShieldQuestion, CircleCheck, Info } from "lucide-react";
import { getSinais, type SinaisResp, type Sinal } from "@/lib/api";
import { useFund } from "@/components/app/fund-context";
import { pp } from "@/lib/fund";
import { cn } from "@/lib/utils";

const NIVEL = {
  alerta: { label: "Alerta", cor: "var(--destructive)", Icon: TriangleAlert },
  atencao: { label: "Atenção", cor: "var(--chart-5)", Icon: ShieldQuestion },
  ok: { label: "Tranquilo", cor: "var(--success)", Icon: CircleCheck },
} as const;

export default function SinaisPage() {
  const { codigo, fundo } = useFund();
  const [data, setData] = useState<SinaisResp | null>(null);

  useEffect(() => {
    getSinais(codigo).then(setData);
  }, [codigo]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="font-display text-2xl font-semibold text-foreground">Sinais</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Alertas de <strong>apoio à decisão</strong> por estratégia — probabilidade de contribuição
          negativa no próximo período, cruzando o sentimento do radar com o resultado corrente.
          {fundo.fundo.nome !== "Alfa Multimercado FIC FIM" && " (Notícias semeadas referem-se ao Alfa no POC.)"}
        </p>
      </div>

      {/* aviso legal — sempre visível */}
      {data?.aviso && (
        <div className="flex items-start gap-2.5 rounded-lg border border-[var(--chart-5)]/30 bg-[var(--chart-5)]/10 p-3">
          <Info className="mt-0.5 h-4 w-4 shrink-0 text-[var(--chart-5)]" strokeWidth={1.75} />
          <p className="text-[12px] leading-relaxed text-foreground/80">{data.aviso}</p>
        </div>
      )}

      {!data?.ok ? (
        <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          Sem sinais — suba a API e as notícias classificadas do radar.
        </div>
      ) : (
        <ul className="space-y-3">
          {data.sinais.map((s) => (
            <SinalCard key={s.estrategia} s={s} />
          ))}
        </ul>
      )}

      {data?.modelo && (
        <p className="text-[11px] text-muted-foreground">
          Modelo: <span className="font-mono">{data.modelo}</span> · sinal por regras transparentes,
          não por LLM. Validação estatística (backtest) entra no piloto.
        </p>
      )}
    </div>
  );
}

function SinalCard({ s }: { s: Sinal }) {
  const n = NIVEL[s.nivel];
  return (
    <li className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          <span
            className="flex h-10 w-10 items-center justify-center rounded-lg"
            style={{ backgroundColor: `color-mix(in oklab, ${n.cor} 15%, transparent)` }}
          >
            <n.Icon className="h-5 w-5" style={{ color: n.cor }} strokeWidth={1.75} />
          </span>
          <div>
            <p className="text-[15px] font-medium text-foreground">{s.estrategia}</p>
            <p className="text-[12px]" style={{ color: n.cor }}>{n.label}</p>
          </div>
        </div>
        <div className="text-right">
          <p className="tabular font-display text-2xl font-semibold" style={{ color: n.cor }}>
            {s.prob_neg}%
          </p>
          <p className="text-[11px] text-muted-foreground">prob. de contribuição negativa</p>
        </div>
      </div>

      {/* barra de probabilidade */}
      <div className="mt-3 h-2 overflow-hidden rounded-full bg-muted/60">
        <div className="h-full rounded-full" style={{ width: `${s.prob_neg}%`, backgroundColor: n.cor }} />
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-muted-foreground">
        <span>Sentimento líquido: <span className="tabular text-foreground">{s.sentimento_liquido.toFixed(2)}</span></span>
        <span>Contribuição atual: <span className={cn("tabular", s.contribuicao_pp < 0 ? "text-[var(--destructive)]" : "text-foreground")}>{pp(s.contribuicao_pp)}</span></span>
        <span>{s.noticias_no_periodo} notícia(s)</span>
        {s.evidencias.map((e) => (
          <span key={e} className="rounded bg-muted/50 px-1.5 py-0.5 font-mono text-[10px]">{e}</span>
        ))}
      </div>
      <p className="mt-2 text-[11px] text-muted-foreground/80">{s.base_calculo}</p>
    </li>
  );
}
