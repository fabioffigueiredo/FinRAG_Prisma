import { type Estrategia, CHART_COLOR, pp } from "@/lib/fund";
import { cn } from "@/lib/utils";

/** Ranking de contribuição por estratégia — barras HTML nítidas, cor semântica. */
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

  return (
    <ul className="space-y-2.5">
      {ordenadas.map((e) => {
        const negativo = e.contribuicao_pp < 0;
        const largura = (Math.abs(e.contribuicao_pp) / maxAbs) * 100;
        const cor = negativo ? "var(--destructive)" : CHART_COLOR[e.cor] ?? "var(--chart-1)";
        const ativo = selected === e.nome;
        const Comp = onSelect ? "button" : "div";
        return (
          <li key={e.nome}>
            <Comp
              {...(onSelect ? { onClick: () => onSelect(e.nome) } : {})}
              className={cn(
                "flex w-full items-center gap-3 rounded-lg px-2 py-1.5 text-left transition-colors",
                onSelect && "hover:bg-muted/50",
                ativo && "bg-muted",
              )}
            >
              <span className="w-32 shrink-0 truncate text-[13px] text-foreground">{e.nome}</span>
              <span className="relative h-2.5 flex-1 overflow-hidden rounded-full bg-muted/60">
                <span
                  className="absolute inset-y-0 left-0 rounded-full transition-all duration-500"
                  style={{ width: `${largura}%`, backgroundColor: cor }}
                />
              </span>
              <span
                className={cn(
                  "tabular w-16 shrink-0 text-right text-[13px] font-medium",
                  negativo ? "text-[var(--destructive)]" : "text-foreground",
                )}
              >
                {pp(e.contribuicao_pp)}
              </span>
            </Comp>
          </li>
        );
      })}
    </ul>
  );
}
