"use client";

import { motion } from "motion/react";
import { type Estrategia, CHART_COLOR } from "@/lib/fund";
import { easeOutQuint } from "@/lib/motion";
import { cn } from "@/lib/utils";

/**
 * Waterfall: contribuições construindo o retorno da cota.
 * Layout de colunas (ref. estilo Zentra): cada barra tem seu nome + valor
 * empilhados no topo, alinhados acima dela — leitura imediata de qual dado
 * pertence a qual estratégia. Cores mantidas (paleta Obsidian).
 */
const HEADER_H = 46; // px reservados para o cabeçalho (valor + nome) de cada coluna

function fmt(v: number) {
  return `${v >= 0 ? "+" : "-"}${Math.abs(v).toFixed(2).replace(".", ",")}`;
}

export function Waterfall({
  estrategias,
  total,
  benchmark,
  benchLabel,
}: {
  estrategias: Estrategia[];
  total: number;
  benchmark: number;
  benchLabel: string;
}) {
  const ordenadas = [...estrategias].sort((a, b) => b.contribuicao_pp - a.contribuicao_pp);

  // constrói os segmentos acumulados (start→end em unidades de pp)
  let run = 0;
  const segs = [
    ...ordenadas.map((e) => {
      const start = run;
      run += e.contribuicao_pp;
      return {
        nome: e.nome,
        valor: e.contribuicao_pp,
        start,
        end: run,
        cor: e.contribuicao_pp < 0 ? "var(--destructive)" : CHART_COLOR[e.cor] ?? "var(--chart-1)",
        total: false,
      };
    }),
    { nome: "Retorno da cota", valor: total, start: 0, end: total, cor: "var(--primary)", total: true },
  ];

  const N = segs.length;
  const lo = Math.min(0, benchmark, ...segs.map((s) => Math.min(s.start, s.end)));
  const hi = Math.max(total, benchmark, ...segs.map((s) => Math.max(s.start, s.end)));
  const span = hi - lo || 1;
  const min = lo - span * 0.04;
  const max = hi + span * 0.14;
  const R = max - min;
  const pct = (v: number) => ((v - min) / R) * 100;

  return (
    <div className="relative h-full w-full">
      {/* colunas: cabeçalho (valor + nome) + célula do gráfico */}
      <div className="flex h-full">
        {segs.map((s, i) => {
          const lowV = Math.min(s.start, s.end);
          const highV = Math.max(s.start, s.end);
          const bottom = pct(lowV);
          const height = Math.max(pct(highV) - pct(lowV), 1.4);
          const negativo = s.valor < 0;
          const valorCor = s.total ? "var(--primary)" : negativo ? "var(--destructive)" : "var(--foreground)";
          return (
            <div
              key={s.nome}
              className="group relative flex flex-1 flex-col rounded-lg px-1 transition-colors hover:bg-muted/20"
            >
              <div className="shrink-0 pt-1 text-center" style={{ height: HEADER_H }}>
                <div className="tabular text-[13px] font-semibold leading-none" style={{ color: valorCor }}>
                  {fmt(s.valor)}
                </div>
                <div className="mt-1 line-clamp-2 text-[10px] leading-tight text-muted-foreground group-hover:text-foreground">
                  {s.nome}
                </div>
              </div>
              <div className="relative min-h-0 flex-1">
                <motion.div
                  className={cn(
                    "absolute left-1/2 -translate-x-1/2 rounded-md",
                    s.total ? "w-[62%] ring-1 ring-inset ring-primary/60" : "w-[56%]",
                  )}
                  style={{
                    bottom: `${bottom}%`,
                    height: `${height}%`,
                    backgroundColor: s.cor,
                    transformOrigin: negativo ? "top" : "bottom",
                    boxShadow: s.total
                      ? "0 0 30px -8px color-mix(in oklab, var(--primary) 70%, transparent)"
                      : undefined,
                  }}
                  initial={{ scaleY: 0, opacity: 0 }}
                  animate={{ scaleY: 1, opacity: s.total ? 1 : 0.9 }}
                  transition={{ duration: 0.5, ease: easeOutQuint, delay: 0.12 + i * 0.07 }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* sobreposição de linhas (eixo zero, benchmark, conectores) — alinhada à banda do gráfico */}
      <div className="pointer-events-none absolute inset-x-0" style={{ top: HEADER_H, bottom: 0 }}>
        {/* eixo zero */}
        <div className="absolute inset-x-0 border-t border-border" style={{ bottom: `${pct(0)}%` }} />

        {/* linha do benchmark */}
        <div
          className="absolute inset-x-0 border-t border-dashed border-muted-foreground/60"
          style={{ bottom: `${pct(benchmark)}%` }}
        >
          <span className="absolute left-0 -top-3.5 rounded bg-card/70 px-1 text-[9px] text-muted-foreground">
            {benchLabel} {benchmark.toFixed(2).replace(".", ",")}%
          </span>
        </div>

        {/* divisor: separa as etapas do total/resultado */}
        <div
          className="absolute bottom-0 top-0 border-l border-dashed border-border/70"
          style={{ left: `${((N - 1) / N) * 100}%` }}
        />

        {/* conectores acumulados entre uma barra e a próxima */}
        {segs.slice(0, -1).map((s, i) => (
          <div
            key={`c${i}`}
            className="absolute border-t border-dashed border-border/70"
            style={{
              left: `${((i + 0.5) / N) * 100}%`,
              width: `${(1 / N) * 100}%`,
              bottom: `${pct(s.end)}%`,
            }}
          />
        ))}
      </div>
    </div>
  );
}
