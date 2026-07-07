"use client";

import { motion } from "motion/react";
import { ChevronRight } from "lucide-react";
import { type Estrategia, CHART_COLOR, pp } from "@/lib/fund";
import { cn } from "@/lib/utils";
import { easeOutQuint } from "@/lib/motion";

/** Ranking de contribuição por estratégia — barras HTML nítidas, cor semântica, draw-in escalonado. */
export function ContributionBars({
  estrategias,
  onSelect,
  selected,
}: {
  estrategias: Estrategia[];
  onSelect?: (nome: string) => void;
  selected?: string;
}) {
  const ordenadas = [...estrategias].sort((a, b) => b.contribuicao_pp - a.contribuicao_pp);
  const maxAbs = Math.max(...ordenadas.map((e) => Math.abs(e.contribuicao_pp)));
  const interativo = !!onSelect;

  return (
    <ul className="-mx-2 space-y-0.5">
      {ordenadas.map((e, i) => {
        const negativo = e.contribuicao_pp < 0;
        const largura = (Math.abs(e.contribuicao_pp) / maxAbs) * 100;
        const cor = negativo ? "var(--destructive)" : CHART_COLOR[e.cor] ?? "var(--chart-1)";
        const ativo = selected === e.nome;
        const Comp = interativo ? "button" : "div";
        return (
          <li key={e.nome}>
            <Comp
              {...(interativo ? { onClick: () => onSelect(e.nome) } : {})}
              className={cn(
                "group relative flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors",
                interativo && "cursor-pointer hover:bg-muted/40",
              )}
            >
              {ativo && (
                <motion.span
                  layoutId="contrib-selected"
                  className="absolute inset-0 rounded-lg bg-muted"
                  transition={{ type: "spring", stiffness: 420, damping: 34 }}
                >
                  <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-primary" />
                </motion.span>
              )}

              <span className="relative flex w-40 shrink-0 items-center gap-2">
                <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: cor }} />
                <span className={cn("truncate text-[13px] text-foreground", ativo && "font-medium")} title={e.nome}>
                  {e.nome}
                </span>
              </span>

              <span className="relative h-2 flex-1 overflow-hidden rounded-full bg-muted/50">
                <motion.span
                  className="absolute inset-y-0 left-0 rounded-full"
                  style={{ width: `${largura}%`, backgroundColor: cor, transformOrigin: "left" }}
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: 0.7, ease: easeOutQuint, delay: 0.1 + i * 0.06 }}
                />
              </span>

              <span
                className={cn(
                  "tabular relative w-16 shrink-0 text-right text-[13px] font-semibold",
                  negativo ? "text-[var(--destructive)]" : "text-foreground",
                )}
              >
                {pp(e.contribuicao_pp)}
              </span>

              {interativo && (
                <ChevronRight
                  className={cn(
                    "relative h-3.5 w-3.5 shrink-0 transition-opacity",
                    ativo ? "text-primary opacity-100" : "text-muted-foreground opacity-0 group-hover:opacity-60",
                  )}
                  strokeWidth={2}
                />
              )}
            </Comp>
          </li>
        );
      })}
    </ul>
  );
}
