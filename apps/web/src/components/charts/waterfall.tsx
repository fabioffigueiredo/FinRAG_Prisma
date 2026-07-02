"use client";

import { type Estrategia, CHART_COLOR } from "@/lib/fund";

/** Waterfall: contribuições construindo o retorno da cota. SVG autoral. */
export function Waterfall({
  estrategias,
  total,
  benchmark,
}: {
  estrategias: Estrategia[];
  total: number;
  benchmark: number;
}) {
  const ordenadas = [...estrategias].sort((a, b) => b.contribuicao_pp - a.contribuicao_pp);
  const passos = [
    ...ordenadas.map((e) => ({ nome: e.nome, valor: e.contribuicao_pp, cor: e.cor, total: false })),
    { nome: "Retorno da cota", valor: total, cor: "total", total: true },
  ];

  const W = 760;
  const H = 300;
  const pad = { t: 16, r: 16, b: 64, l: 34 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  const max = total * 1.15;
  const min = Math.min(0, ...ordenadas.map((e) => e.contribuicao_pp)) - 0.1;
  const range = max - min || 1;
  const y = (v: number) => pad.t + ih - ((v - min) / range) * ih;

  const bw = (iw / passos.length) * 0.62;
  const gap = iw / passos.length;

  let running = 0;
  const barras = passos.map((p, i) => {
    const x = pad.l + i * gap + (gap - bw) / 2;
    let y0: number, y1: number;
    if (p.total) {
      y0 = y(0);
      y1 = y(total);
    } else {
      const start = running;
      running += p.valor;
      y0 = y(Math.max(start, running));
      y1 = y(Math.min(start, running));
    }
    const cor = p.total
      ? "var(--primary)"
      : p.valor < 0
        ? "var(--destructive)"
        : CHART_COLOR[p.cor] ?? "var(--chart-1)";
    return { ...p, x, top: y0, h: Math.max(2, y1 - y0), cor };
  });

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Waterfall de contribuição por estratégia">
      {/* linha do benchmark */}
      <line x1={pad.l} x2={W - pad.r} y1={y(benchmark)} y2={y(benchmark)} stroke="var(--muted-foreground)" strokeWidth="1" strokeDasharray="4 4" />
      <text x={W - pad.r} y={y(benchmark) - 4} textAnchor="end" className="fill-[var(--muted-foreground)] text-[9px]">
        CDI {benchmark.toFixed(2)}%
      </text>
      {/* eixo zero */}
      <line x1={pad.l} x2={W - pad.r} y1={y(0)} y2={y(0)} stroke="var(--border)" strokeWidth="1" />

      {barras.map((b, i) => (
        <g key={i}>
          <rect x={b.x} y={b.top} width={bw} height={b.h} rx="2.5" fill={b.cor} opacity={b.total ? 1 : 0.85} />
          <text x={b.x + bw / 2} y={b.top - 5} textAnchor="middle" className="fill-[var(--foreground)] text-[9px]">
            {b.valor > 0 ? "+" : ""}{b.valor.toFixed(2)}
          </text>
          <text
            x={b.x + bw / 2}
            y={H - pad.b + 14}
            textAnchor="end"
            transform={`rotate(-35 ${b.x + bw / 2} ${H - pad.b + 14})`}
            className="fill-[var(--muted-foreground)] text-[9px]"
          >
            {b.nome}
          </text>
        </g>
      ))}
    </svg>
  );
}
