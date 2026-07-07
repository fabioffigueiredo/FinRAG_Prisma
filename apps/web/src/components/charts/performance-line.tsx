"use client";

import { useState } from "react";
import type { PontoSerie } from "@/lib/fund";

const fmtPct = (v: number) => `${v.toFixed(2).replace(".", ",")}%`;

/** Curva acumulada cota × benchmark — SVG autoral, responsivo, com crosshair no hover. */
export function PerformanceLine({ serie }: { serie: PontoSerie[] }) {
  const [hover, setHover] = useState<number | null>(null);

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

  const ticks = 4;
  const grid = Array.from({ length: ticks + 1 }, (_, i) => min + (range * i) / ticks);

  function onMove(e: React.MouseEvent<HTMLDivElement>) {
    const rect = e.currentTarget.getBoundingClientRect();
    const f = (e.clientX - rect.left) / rect.width;
    const i = Math.max(0, Math.min(serie.length - 1, Math.round(f * (serie.length - 1))));
    setHover(i);
  }

  const hoverPt = hover != null ? serie[hover] : null;
  const leftPct = hover != null ? (x(hover) / W) * 100 : 0;

  return (
    <div className="relative h-full w-full" onMouseMove={onMove} onMouseLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} className="h-full w-full" role="img" aria-label="Curva de rentabilidade acumulada do fundo versus benchmark">
        <defs>
          <linearGradient id="cotaFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.22" />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
          </linearGradient>
        </defs>

        {grid.map((g, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(g)} y2={y(g)} stroke="var(--border)" strokeWidth="1" />
            <text x={pad.l - 6} y={y(g) + 3} textAnchor="end" className="fill-[var(--muted-foreground)] text-[9px]">
              {g.toFixed(1)}
            </text>
          </g>
        ))}

        <path d={areaCota} fill="url(#cotaFill)" className="prisma-fade-in" />
        <path
          d={line("bench")}
          pathLength={1}
          fill="none"
          stroke="var(--muted-foreground)"
          strokeWidth="1.5"
          strokeDasharray="4 4"
          className="prisma-fade-in"
        />
        <path
          d={line("cota")}
          pathLength={1}
          fill="none"
          stroke="var(--chart-1)"
          strokeWidth="2.25"
          strokeLinejoin="round"
          strokeLinecap="round"
          className="prisma-draw"
        />

        {/* crosshair + pontos no hover */}
        {hover != null && hoverPt && (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={pad.t}
              y2={H - pad.b}
              stroke="var(--border)"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <circle cx={x(hover)} cy={y(hoverPt.bench)} r="3" fill="var(--background)" stroke="var(--muted-foreground)" strokeWidth="1.5" />
            <circle cx={x(hover)} cy={y(hoverPt.cota)} r="3.5" fill="var(--chart-1)" stroke="var(--background)" strokeWidth="1.5" />
          </g>
        )}

        {/* ponto final da cota (só quando não está em hover) */}
        {hover == null && (
          <circle
            cx={x(serie.length - 1)}
            cy={y(serie[serie.length - 1].cota)}
            r="3.5"
            fill="var(--chart-1)"
            className="prisma-dot-pop"
          />
        )}
      </svg>

      {/* tooltip */}
      {hover != null && hoverPt && (
        <div
          className="pointer-events-none absolute top-0 z-10 -translate-x-1/2 rounded-lg border border-border bg-popover/95 px-2.5 py-1.5 shadow-xl backdrop-blur-sm"
          style={{ left: `${Math.min(Math.max(leftPct, 12), 88)}%` }}
        >
          <div className="mb-1 text-[10px] text-muted-foreground">{hoverPt.data}</div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--chart-1)]" />
            <span className="text-muted-foreground">Cota</span>
            <span className="tabular ml-auto font-medium text-foreground">{fmtPct(hoverPt.cota)}</span>
          </div>
          <div className="flex items-center gap-1.5 text-[11px]">
            <span className="h-1.5 w-1.5 rounded-full bg-[var(--muted-foreground)]" />
            <span className="text-muted-foreground">Bench</span>
            <span className="tabular ml-auto font-medium text-foreground">{fmtPct(hoverPt.bench)}</span>
          </div>
        </div>
      )}
    </div>
  );
}
