import type { PontoSerie } from "@/lib/fund";

/** Curva acumulada cota × benchmark — SVG autoral, responsivo por viewBox. */
export function PerformanceLine({ serie }: { serie: PontoSerie[] }) {
  const W = 720;
  const H = 240;
  const pad = { t: 16, r: 16, b: 24, l: 34 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  const vals = serie.flatMap((p) => [p.cota, p.bench]);
  const min = Math.min(0, ...vals);
  const max = Math.max(...vals);
  const range = max - min || 1;

  const x = (i: number) => pad.l + (i / (serie.length - 1)) * iw;
  const y = (v: number) => pad.t + ih - ((v - min) / range) * ih;

  const line = (key: "cota" | "bench") =>
    serie.map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p[key]).toFixed(1)}`).join(" ");

  const areaCota = `${line("cota")} L ${x(serie.length - 1).toFixed(1)} ${y(min).toFixed(1)} L ${x(0).toFixed(1)} ${y(min).toFixed(1)} Z`;

  // gridlines horizontais
  const ticks = 4;
  const grid = Array.from({ length: ticks + 1 }, (_, i) => min + (range * i) / ticks);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Curva de rentabilidade acumulada do fundo versus benchmark">
      <defs>
        <linearGradient id="cotaFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.22" />
          <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
        </linearGradient>
      </defs>

      {grid.map((g, i) => (
        <g key={i}>
          <line
            x1={pad.l} x2={W - pad.r} y1={y(g)} y2={y(g)}
            stroke="var(--border)" strokeWidth="1"
          />
          <text x={pad.l - 6} y={y(g) + 3} textAnchor="end" className="fill-[var(--muted-foreground)] text-[9px]">
            {g.toFixed(1)}
          </text>
        </g>
      ))}

      <path d={areaCota} fill="url(#cotaFill)" />
      <path d={line("bench")} fill="none" stroke="var(--muted-foreground)" strokeWidth="1.5" strokeDasharray="4 4" />
      <path d={line("cota")} fill="none" stroke="var(--chart-1)" strokeWidth="2.25" strokeLinejoin="round" strokeLinecap="round" />

      {/* ponto final da cota */}
      <circle cx={x(serie.length - 1)} cy={y(serie[serie.length - 1].cota)} r="3.5" fill="var(--chart-1)" />
    </svg>
  );
}
