import fundoAlfa from "@/data/fundo_alfa.json";
import fundoBeta from "@/data/fundo_beta.json";
import fundoGama from "@/data/fundo_gama.json";
import fundoDelta from "@/data/fundo_delta.json";
import fundoEpsilon from "@/data/fundo_epsilon.json";
import fundoZeta from "@/data/fundo_zeta.json";
import fundoTheta from "@/data/fundo_theta.json";

export type Estrategia = {
  nome: string;
  contribuicao_pp: number;
  peso_medio: number;
  cor: string;
};

export type Ativo = {
  estrategia: string;
  ativo: string;
  contribuicao_pp: number;
  peso_medio: number;
};

export type PontoSerie = { data: string; cota: number; bench: number };

export type Fic = { nome: string; resultado_pp: number; diferencial_pp: number };

export type Fundo = {
  fundo: {
    nome: string;
    codigo: string;
    cnpj: string;
    benchmark: string;
    periodo: string;
    classe: string;
  };
  resumo: {
    retorno_cota: number;
    retorno_bench: number;
    excesso_pp: number;
    pct_cdi: number;
    beta: number;
    alpha_pp: number;
    vol_anual: number;
    patrimonio_mm: number;
    num_cotistas: number;
  };
  estrategias: Estrategia[];
  ativos: Ativo[];
  serie_diaria: PontoSerie[];
  fics: Fic[];
};

export const FUNDS: Record<string, Fundo> = {
  "ALFA-33": fundoAlfa as Fundo,
  "BETA-71": fundoBeta as Fundo,
  "GAMA-12": fundoGama as Fundo,
  "DELTA-08": fundoDelta as Fundo,
  "EPSILON-45": fundoEpsilon as Fundo,
  "ZETA-19": fundoZeta as Fundo,
  "THETA-52": fundoTheta as Fundo,
};

export const FUND_PADRAO = "ALFA-33";

/** Mapa de cor semântica -> variável CSS de chart (identidade Obsidian). */
export const CHART_COLOR: Record<string, string> = {
  gold: "var(--chart-1)",
  blue: "var(--chart-2)",
  green: "var(--chart-3)",
  violet: "var(--chart-4)",
  amber: "var(--chart-5)",
  neutral: "var(--muted-foreground)",
  red: "var(--destructive)",
};

// ---- Formatadores PT-BR ----
export function pp(v: number, casas = 2): string {
  const s = v.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  });
  return `${v > 0 ? "+" : ""}${s} pp`;
}

export function pct(v: number, casas = 2): string {
  return `${v.toLocaleString("pt-BR", {
    minimumFractionDigits: casas,
    maximumFractionDigits: casas,
  })}%`;
}

export function brlMM(v: number): string {
  return `R$ ${v.toLocaleString("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 })} mi`;
}

export function num(v: number): string {
  return v.toLocaleString("pt-BR");
}

export function sinalClasse(v: number): string {
  if (v > 0) return "text-[var(--success)]";
  if (v < 0) return "text-[var(--destructive)]";
  return "text-muted-foreground";
}

/** Ativos de uma estratégia do fundo dado, ordenados por contribuição desc. */
export function ativosDe(f: Fundo, nome: string): Ativo[] {
  return f.ativos
    .filter((a) => a.estrategia === nome)
    .sort((a, b) => b.contribuicao_pp - a.contribuicao_pp);
}
