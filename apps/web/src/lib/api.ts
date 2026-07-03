import type { Backend } from "@/components/app/backend-context";

const BASE = process.env.NEXT_PUBLIC_PRISMA_API ?? "http://localhost:8000";

export type Citacao = { fonte: string; trecho: string; score?: number };

export type NarrativaResp = {
  texto: string;
  citacoes: Citacao[];
  backend: string;
  latency_ms: number;
  fallback?: boolean;
};

export type PerguntaResp = {
  resposta: string;
  citacoes: Citacao[];
  bloqueados: { fonte: string; motivo: string }[];
  backend: string;
  latency_ms: number;
  fallback?: boolean;
  escopo?: boolean;
};

async function post<T>(path: string, body: unknown, fallback: T): Promise<T> {
  try {
    const res = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as T;
  } catch {
    return { ...fallback, fallback: true } as T;
  }
}

export const NARRATIVA_FALLBACK: NarrativaResp = {
  texto:
    "No 2º trimestre de 2026 o Alfa Multimercado rendeu 4,25%, ante 3,10% do CDI — um excesso de +1,15 pp (137% do CDI). O resultado veio principalmente de duas frentes de carrego: Crédito Privado (+1,35 pp), puxado pela debênture de infraestrutura, e Juros Brasil (+1,05 pp), com ganho concentrado na NTN-B 2030. A Bolsa Brasil somou +0,85 pp, com destaque para os setores bancário e de energia, parcialmente compensados pela posição em varejo (-0,10 pp). Custos e despesas subtraíram -0,25 pp. Com beta de 0,15 frente ao CDI, o retorno é majoritariamente alpha (+1,10 pp): veio de seleção e carrego, não de exposição ao índice.",
  citacoes: [
    { fonte: "01_metodologia_atribuicao.md", trecho: "a soma das contribuições ajustadas de todos os ativos é igual ao retorno da cota no período" },
    { fonte: "03_glossario_benchmark.md", trecho: "Alpha é o retorno que não é explicado pela exposição ao benchmark" },
  ],
  backend: "seed",
  latency_ms: 0,
  fallback: true,
};

export function gerarNarrativa(backend: Backend, fundo: string): Promise<NarrativaResp> {
  return post<NarrativaResp>("/narrativa", { fundo, backend }, {
    ...NARRATIVA_FALLBACK,
    backend,
  });
}

export type IngestResp = {
  ok: boolean;
  erro?: string;
  fundo?: { nome: string; benchmark: string; periodo: string };
  resumo?: { retorno_cota: number; retorno_bench: number; excesso_pp: number; pct_cdi: number };
  estrategias?: { nome: string; contribuicao_pp: number; peso_medio: number; cor: string }[];
  n_estrategias?: number;
  fallback?: boolean;
};

export async function ingerir(nome: string, csv: string): Promise<IngestResp> {
  try {
    const res = await fetch(`${BASE}/ingerir`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome, csv }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as IngestResp;
  } catch {
    // fallback: parseia o CSV no cliente (demo resiliente sem API)
    return parseCsvLocal(nome, csv);
  }
}

function parseCsvLocal(nome: string, csv: string): IngestResp {
  const linhas = csv.trim().split(/\r?\n/).slice(1);
  const cores = ["gold", "blue", "green", "neutral", "violet", "amber", "red"];
  const estrategias = linhas
    .map((l, i) => {
      const [e, c, p] = l.split(",");
      if (!e) return null;
      const contrib = parseFloat((c ?? "0").replace(",", "."));
      return {
        nome: e.trim(),
        contribuicao_pp: Math.round(contrib * 100) / 100,
        peso_medio: parseFloat((p ?? "0").replace(",", ".")) || 0,
        cor: contrib < 0 ? "red" : cores[i % cores.length],
      };
    })
    .filter(Boolean) as NonNullable<IngestResp["estrategias"]>;
  const retorno = Math.round(estrategias.reduce((s, e) => s + e.contribuicao_pp, 0) * 100) / 100;
  const bench = 3.1;
  return {
    ok: true,
    fallback: true,
    fundo: { nome, benchmark: "CDI", periodo: "importado do arquivo" },
    resumo: { retorno_cota: retorno, retorno_bench: bench, excesso_pp: Math.round((retorno - bench) * 100) / 100, pct_cdi: Math.round((retorno / bench) * 1000) / 10 },
    estrategias,
    n_estrategias: estrategias.length,
  };
}

export function perguntar(pergunta: string, backend: Backend, fundo?: string): Promise<PerguntaResp> {
  return post<PerguntaResp>(
    "/perguntar",
    { pergunta, backend, fundo },
    {
      resposta:
        "Com base nos trechos recuperados: o resultado do fundo no período foi sustentado sobretudo pelo carrego das estratégias de Crédito Privado e Juros Brasil, que juntas somaram +2,40 pp. O beta baixo (0,15) indica que o ganho não veio de exposição ao CDI, e sim de seleção — o que a atribuição registra como alpha (+1,10 pp).",
      citacoes: [
        { fonte: "02_taxonomia_estrategias.md", trecho: "Crédito Privado: o retorno vem do carrego (juros acima do CDI) e da variação de spread", score: 0.79 },
        { fonte: "03_glossario_benchmark.md", trecho: "carrego (posições que rendem acima do CDI) e acertos direcionais", score: 0.71 },
      ],
      bloqueados: [],
      backend,
      latency_ms: 0,
    },
  );
}

export type Noticia = {
  id: string;
  titulo: string;
  corpo: string;
  estrategia: string;
  data: string;
  sentimento: "positivo" | "negativo" | "neutro";
  confianca: number;
};

export type RadarResp = {
  ok: boolean;
  noticias: Noticia[];
  agregado: Record<string, { pos: number; neg: number; neu: number; total: number; liquido: number }>;
};

export async function getRadar(): Promise<RadarResp> {
  try {
    const res = await fetch(`${BASE}/radar`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as RadarResp;
  } catch {
    return { ok: false, noticias: [], agregado: {} };
  }
}

export type Consulta = {
  timestamp: string;
  rota: string;
  fundo: string;
  pergunta: string;
  backend: string;
  latency_ms: number;
  fontes: string[];
  bloqueados: string[];
  escopo?: boolean;
};

export async function getAuditoria(): Promise<{ ok: boolean; consultas: Consulta[] }> {
  try {
    const res = await fetch(`${BASE}/auditoria?limit=50`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as { ok: boolean; consultas: Consulta[] };
  } catch {
    return { ok: false, consultas: [] };
  }
}

export type Sinal = {
  estrategia: string;
  nivel: "ok" | "atencao" | "alerta";
  prob_neg: number;
  sentimento_liquido: number;
  noticias_no_periodo: number;
  contribuicao_pp: number;
  evidencias: string[];
  base_calculo: string;
  validacao: string;
  modelo_versao: string;
};

export type SinaisResp = {
  ok: boolean;
  sinais: Sinal[];
  aviso: string;
  modelo: string;
};

export async function getSinais(fundo: string): Promise<SinaisResp> {
  try {
    const res = await fetch(`${BASE}/sinais?fundo=${encodeURIComponent(fundo)}`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as SinaisResp;
  } catch {
    return { ok: false, sinais: [], aviso: "", modelo: "" };
  }
}
