import type { Backend } from "@/components/app/backend-context";
import type { Estrategia, PontoSerie } from "@/lib/fund";
import { getCsrfToken } from "@/lib/csrf";

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

/** Bloco de conteúdo estruturado do Copiloto de Análise (gráfico ou KPIs). */
export type BlocoGrafico =
  | { tipo: "grafico"; chart: "waterfall"; titulo: string; dados: { estrategias: Estrategia[]; total: number; benchmark: number; benchLabel: string } }
  | { tipo: "grafico"; chart: "linha"; titulo: string; dados: { serie: PontoSerie[] } }
  | { tipo: "kpis"; chart: null; titulo: string; dados: { resumo: Record<string, number> } };

export type Acao = { label: string; prompt: string };

export type ConsultaEcho = { fundo?: string; periodo?: string; benchmark?: string; dimensao?: string };

export type AnaliseResp = {
  resposta: string;
  consulta_echo: ConsultaEcho;
  blocos: BlocoGrafico[];
  acoes: Acao[];
  avisos: string[];
  citacoes: Citacao[];
  bloqueados: { fonte: string; motivo: string }[];
  backend: string;
  latency_ms: number;
  fallback?: boolean;
  escopo?: boolean;
  injecao?: boolean;
  degradado?: boolean;
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

export function analisar(pergunta: string, backend: Backend, fundo?: string): Promise<AnaliseResp> {
  return post<AnaliseResp>(
    "/analisar",
    { pergunta, backend, fundo },
    {
      resposta:
        "(Sem conexão com a API) O Alfa Multimercado rendeu 4,25% no período, ante 3,10% do CDI — excesso de +1,15 pp, puxado por Crédito Privado e Juros Brasil.",
      consulta_echo: { fundo: fundo ?? "ALFA-33", periodo: "2º trimestre 2026 (abr–jun)", benchmark: "CDI", dimensao: "Estratégia" },
      blocos: [],
      acoes: [
        { label: "Comparar Benchmarks", prompt: "Compare o fundo com o Ibovespa e o IMA-B" },
        { label: "Ver por Grupo Contábil", prompt: "Mostre a atribuição por grupo contábil" },
      ],
      avisos: [],
      citacoes: [],
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
    const res = await fetch(`${BASE}/auditoria?limit=50`, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as { ok: boolean; consultas: Consulta[] };
  } catch {
    return { ok: false, consultas: [] };
  }
}

// --- Autenticação -----------------------------------------------------------

export type MeResp = {
  matricula: string;
  nome: string;
  papel: string;
  gestora_id: number;
  email: string | null;
  avatar_url: string | null;
  totp_ativado: boolean;
  trocar_senha_no_proximo_login: boolean;
};

export type LoginResultado =
  | { ok: true; nome: string; papel: string; gestora_id: number; requer2fa: boolean }
  | { ok: false; erro: string };

export async function getCsrf(): Promise<string | null> {
  try {
    const res = await fetch(`${BASE}/auth/csrf`, { credentials: "include" });
    if (!res.ok) return null;
    return ((await res.json()) as { csrf_token: string }).csrf_token;
  } catch {
    return null;
  }
}

export async function login(gestoraId: number, matricula: string, senha: string): Promise<LoginResultado> {
  const csrf = getCsrfToken();
  try {
    const res = await fetch(`${BASE}/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      body: JSON.stringify({ gestora_id: gestoraId, matricula, senha }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) {
      return { ok: false, erro: corpo.detail ?? "não foi possível entrar" };
    }
    return { ok: true, nome: corpo.nome, papel: corpo.papel, gestora_id: corpo.gestora_id, requer2fa: !!corpo.requer_2fa };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

/** 2ª etapa do login (gestor/compliance com 2FA ativado) — lê o cookie
 * prisma_pre2fa emitido por login() quando requer2fa vier true. */
export async function verificar2fa(codigo: string): Promise<LoginResultado> {
  try {
    const res = await fetch(`${BASE}/auth/2fa/verificar`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify({ codigo }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "código inválido" };
    return { ok: true, nome: corpo.nome, papel: corpo.papel, gestora_id: corpo.gestora_id, requer2fa: !!corpo.requer_2fa };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

/** Simulação de demo — não é OAuth/OIDC real, sempre loga a mesma conta fixa. */
export async function loginMicrosoftDemo(): Promise<LoginResultado> {
  try {
    const res = await fetch(`${BASE}/auth/login-microsoft-demo`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível entrar" };
    return { ok: true, nome: corpo.nome, papel: corpo.papel, gestora_id: corpo.gestora_id, requer2fa: !!corpo.requer_2fa };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export type Iniciar2FAResultado =
  | { ok: true; otpauthUri: string; qrBase64: string }
  | { ok: false; erro: string };

/** `senhaAtual` só é exigido pela API quando já existe um 2FA ativo (troca de
 * dispositivo self-service) — no 1º enrollment é ignorado. */
export async function iniciarEnrollment2FA(senhaAtual?: string): Promise<Iniciar2FAResultado> {
  try {
    const res = await fetch(`${BASE}/auth/2fa/iniciar`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify(senhaAtual ? { senha_atual: senhaAtual } : {}),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível iniciar o 2FA" };
    return { ok: true, otpauthUri: corpo.otpauth_uri, qrBase64: corpo.qr_base64 };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function confirmarEnrollment2FA(codigo: string): Promise<{ ok: boolean; erro?: string }> {
  try {
    const res = await fetch(`${BASE}/auth/2fa/confirmar`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify({ codigo }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "código inválido" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function trocarSenha(senhaAtual: string, senhaNova: string): Promise<{ ok: boolean; erro?: string }> {
  try {
    const res = await fetch(`${BASE}/auth/senha`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify({ senha_atual: senhaAtual, senha_nova: senhaNova }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível trocar a senha" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function uploadAvatar(arquivo: File): Promise<{ ok: boolean; avatarUrl?: string; erro?: string }> {
  // Sem Content-Type manual — o browser gera o boundary multipart sozinho.
  const csrf = getCsrfToken();
  const formData = new FormData();
  formData.append("arquivo", arquivo);
  try {
    const res = await fetch(`${BASE}/auth/avatar`, {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : undefined,
      body: formData,
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível enviar a foto" };
    return { ok: true, avatarUrl: corpo.avatar_url };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function logout(): Promise<void> {
  const csrf = getCsrfToken();
  try {
    await fetch(`${BASE}/auth/logout`, {
      method: "POST",
      credentials: "include",
      headers: csrf ? { "X-CSRF-Token": csrf } : undefined,
    });
  } catch {
    // best-effort — se a API estiver fora, o cookie httpOnly ainda expira sozinho
  }
}

export async function getMe(): Promise<MeResp | null> {
  try {
    const res = await fetch(`${BASE}/auth/me`, { credentials: "include" });
    if (!res.ok) return null;
    return (await res.json()) as MeResp;
  } catch {
    return null;
  }
}

// --- Gestão de usuários (admin) ---------------------------------------------

export type Usuario = {
  id: number;
  matricula: string;
  nome: string;
  papel: "analista" | "gestor" | "compliance";
  gestora_id: number;
  gestora_nome: string;
  ativo: boolean;
  email: string | null;
  telefone: string | null;
  avatar_url: string | null;
  totp_ativado: boolean;
  trocar_senha_no_proximo_login: boolean;
  bloqueado_ate: string | null;
  tentativas_falhas: number;
};

export type UsuarioResultado = { ok: true; usuario: Usuario } | { ok: false; erro: string };

function headersComCsrf(): HeadersInit {
  const csrf = getCsrfToken();
  return { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) };
}

export async function listarUsuarios(): Promise<{ ok: boolean; usuarios: Usuario[] }> {
  try {
    const res = await fetch(`${BASE}/usuarios`, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as { ok: boolean; usuarios: Usuario[] };
  } catch {
    return { ok: false, usuarios: [] };
  }
}

export async function criarUsuario(dados: {
  matricula: string;
  nome: string;
  papel: string;
  senha: string;
  email?: string;
  telefone?: string;
  trocar_senha_no_proximo_login?: boolean;
}): Promise<UsuarioResultado> {
  try {
    const res = await fetch(`${BASE}/usuarios`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify(dados),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível criar o usuário" };
    return { ok: true, usuario: corpo as Usuario };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function atualizarUsuario(
  id: number,
  dados: Partial<{
    nome: string;
    papel: string;
    ativo: boolean;
    senha: string;
    email: string;
    telefone: string;
    trocar_senha_no_proximo_login: boolean;
  }>,
): Promise<UsuarioResultado> {
  try {
    const res = await fetch(`${BASE}/usuarios/${id}`, {
      method: "PATCH",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify(dados),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível atualizar o usuário" };
    return { ok: true, usuario: corpo as Usuario };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function revogarSessao(usuarioId: number): Promise<{ ok: boolean; erro?: string }> {
  try {
    const res = await fetch(`${BASE}/usuarios/${usuarioId}/revogar-sessao`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível revogar a sessão" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function resetar2FA(usuarioId: number): Promise<{ ok: boolean; erro?: string }> {
  try {
    const res = await fetch(`${BASE}/usuarios/${usuarioId}/resetar-2fa`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível resetar o 2FA" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export type EventoAcesso = {
  timestamp: string;
  rota: string;
  pergunta: string;
  ator_matricula?: string;
};

export async function getHistoricoAcessos(usuarioId: number): Promise<{ ok: boolean; eventos: EventoAcesso[] }> {
  try {
    const res = await fetch(`${BASE}/usuarios/${usuarioId}/historico-acessos`, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as { ok: boolean; eventos: EventoAcesso[] };
  } catch {
    return { ok: false, eventos: [] };
  }
}

// --- Cadastro / convite / ativação de conta ---------------------------------
//
// Nunca envia senha por e-mail — os dois fluxos (autocadastro aprovado e
// convite direto do gestor) convergem no mesmo link de ativação de uso
// único (ver services/prisma-api/convite.py e docs/SEGURANCA.md).

export type PendenteCadastro = {
  id: number;
  matricula: string;
  nome: string;
  email: string | null;
  telefone: string | null;
};

export type GestoraPublica = { id: number; nome: string };

export async function listarGestorasPublico(): Promise<{ ok: boolean; gestoras: GestoraPublica[] }> {
  try {
    const res = await fetch(`${BASE}/auth/gestoras`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return { ok: true, gestoras: (await res.json()) as GestoraPublica[] };
  } catch {
    return { ok: false, gestoras: [] };
  }
}

export async function solicitarCadastro(dados: {
  matricula: string;
  nome: string;
  email: string;
  telefone?: string;
  gestora_id: number;
}): Promise<{ ok: boolean; erro?: string }> {
  const csrf = getCsrfToken();
  try {
    const res = await fetch(`${BASE}/auth/cadastro`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      body: JSON.stringify(dados),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível enviar o cadastro" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function listarPendentes(): Promise<{ ok: boolean; usuarios: PendenteCadastro[] }> {
  try {
    const res = await fetch(`${BASE}/usuarios/pendentes`, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return (await res.json()) as { ok: boolean; usuarios: PendenteCadastro[] };
  } catch {
    return { ok: false, usuarios: [] };
  }
}

export type ConviteResultado =
  | { ok: true; linkAtivacao: string; emailEnviado: boolean }
  | { ok: false; erro: string };

export async function aprovarCadastro(usuarioId: number, papel?: string): Promise<ConviteResultado> {
  try {
    const res = await fetch(`${BASE}/usuarios/${usuarioId}/aprovar`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify(papel ? { papel } : {}),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível aprovar o cadastro" };
    return { ok: true, linkAtivacao: corpo.link_ativacao, emailEnviado: corpo.email_enviado };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function rejeitarCadastro(usuarioId: number): Promise<{ ok: boolean; erro?: string }> {
  try {
    const res = await fetch(`${BASE}/usuarios/${usuarioId}/rejeitar`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível rejeitar o cadastro" };
    return { ok: true };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function criarConvite(dados: {
  matricula: string;
  nome: string;
  papel: string;
  email: string;
  telefone?: string;
}): Promise<ConviteResultado> {
  try {
    const res = await fetch(`${BASE}/usuarios/convite`, {
      method: "POST",
      credentials: "include",
      headers: headersComCsrf(),
      body: JSON.stringify(dados),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível criar o convite" };
    return { ok: true, linkAtivacao: corpo.link_ativacao, emailEnviado: corpo.email_enviado };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export type ValidarConviteResultado =
  | { ok: true; nome: string; matricula: string }
  | { ok: false; erro: string };

export async function validarConvite(token: string): Promise<ValidarConviteResultado> {
  try {
    const res = await fetch(`${BASE}/auth/convite/${encodeURIComponent(token)}`);
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "link inválido ou expirado" };
    return { ok: true, nome: corpo.nome, matricula: corpo.matricula };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
  }
}

export async function ativarConta(token: string, novaSenha: string): Promise<LoginResultado> {
  const csrf = getCsrfToken();
  try {
    const res = await fetch(`${BASE}/auth/ativar-conta`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(csrf ? { "X-CSRF-Token": csrf } : {}) },
      body: JSON.stringify({ token, nova_senha: novaSenha }),
    });
    const corpo = await res.json().catch(() => ({}));
    if (!res.ok) return { ok: false, erro: corpo.detail ?? "não foi possível ativar a conta" };
    return { ok: true, nome: corpo.nome, papel: corpo.papel, gestora_id: corpo.gestora_id, requer2fa: !!corpo.requer_2fa };
  } catch {
    return { ok: false, erro: "sem conexão com a API" };
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
