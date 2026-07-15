"""Prisma API — camada cognitiva sobre a atribuição de performance.

Envolve o núcleo FinRAG (retrieval + guardrail + prompt aumentado) e expõe:
  POST /narrativa   -> comentário do fundo em linguagem natural (grounded)
  POST /perguntar   -> Q&A RAG fundamentado, com citações e trechos bloqueados
  GET  /health      -> status + backends disponíveis

O pacote finrag (retrieval/guardrails) é vendorizado em ./finrag; adiciona
backend Ollama (local) e embeddings bge-m3.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _load_env() -> None:
    """Carrega variáveis de .env (sem depender de python-dotenv) para a demo/VPS
    ficarem turnkey. Procura em: prisma-api/, raiz do prisma/ e raiz do PD1/.
    Só define chaves ainda não presentes no ambiente."""
    here = Path(__file__).resolve()
    candidatos = [
        here.parent / ".env",
        here.parents[2] / ".env",
        here.parents[3] / "PD1" / ".env",
    ]
    for env in candidatos:
        if not env.is_file():
            continue
        for linha in env.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave and chave not in os.environ:
                os.environ[chave] = valor


_load_env()

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

HERE = Path(__file__).resolve()
PRISMA = HERE.parents[2]          # raiz do projeto prisma
CORPUS_DIR = PRISMA / "data" / "corpus"
SEED_DIR = PRISMA / "data" / "seed"
NOTICIAS_PATH = SEED_DIR / "noticias_alfa_classificadas.json"

from finrag.corpus import load_documents, chunk_corpus  # noqa: E402
from finrag.embeddings import SemanticIndex              # noqa: E402
from finrag.guardrails import sanitize_chunks            # noqa: E402
from finrag.rag import build_augmented_prompt            # noqa: E402

from llm import get_backend, ollama_disponivel, OllamaClient  # noqa: E402
from embed import get_embed_fn                                # noqa: E402
from escopo import (  # noqa: E402
    pede_recomendacao, tenta_injecao, INSTRUCAO_ESCOPO, RESPOSTA_ESCOPO, RESPOSTA_INJECAO,
)
import audit                                                             # noqa: E402
import agent as agente                                                   # noqa: E402
from radar import carregar_noticias, agregar                             # noqa: E402
from sinais import gerar_sinais, AVISO_LEGAL, MODELO_VERSAO              # noqa: E402
import auth                                                              # noqa: E402
from db.session import get_db                                           # noqa: E402
import observability                                                     # noqa: E402

app = FastAPI(title="Prisma API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: dict = {"index": None, "embed": "?", "fundos": None, "noticias": None}

NOMES_FUNDOS = {
    "alfa": "ALFA-33", "beta": "BETA-71", "gama": "GAMA-12",
    "delta": "DELTA-08", "epsilon": "EPSILON-45", "zeta": "ZETA-19", "theta": "THETA-52",
}


def e_comparativa(pergunta: str) -> list[str]:
    """Retorna os códigos de fundos a incluir no contexto de uma pergunta
    comparativa; lista vazia = usar apenas o fundo ativo."""
    q = (pergunta or "").lower()
    citados = [cod for nome, cod in NOMES_FUNDOS.items() if nome in q]
    if "compar" in q and len(citados) < 2:
        return list(NOMES_FUNDOS.values())
    return citados if len(citados) >= 2 else []


def _corpus_docs():
    """Carrega o corpus de regras (.md tratados como .txt pelo FinRAG loader)."""
    # o loader do FinRAG lê *.txt; espelhamos os .md como .txt em tempo de carga
    docs = []
    for md in sorted(CORPUS_DIR.glob("*.md")):
        from finrag.corpus import Document
        docs.append(Document(id=md.stem, text=md.read_text(encoding="utf-8"), source=md.name))
    from finrag.corpus import Document
    for n in carregar_noticias(NOTICIAS_PATH):
        docs.append(Document(
            id=f"noticia_{n['id']}",
            text=(f"Notícia ({n['data']}, estratégia {n['estrategia']}, "
                  f"sentimento {n['sentimento']}): {n['titulo']}. {n['corpo']}"),
            source=f"noticia:{n['id']}",
        ))
    return docs


@app.on_event("startup")
def _startup() -> None:
    observability.configurar_logging()
    import embed as _embed
    embed_fn = get_embed_fn()
    STATE["embed"] = f"{_embed.EMBED_MODEL} (Ollama)" if embed_fn else "sentence-transformers (fallback)"
    idx = SemanticIndex(embed_fn=embed_fn) if embed_fn else SemanticIndex()
    idx.build(chunk_corpus(_corpus_docs()))
    STATE["index"] = idx
    STATE["fundos"] = {}
    for fj in sorted(SEED_DIR.glob("fundo_*.json")):
        d = json.loads(fj.read_text(encoding="utf-8"))
        STATE["fundos"][d["fundo"]["codigo"]] = d
    STATE["noticias"] = carregar_noticias(NOTICIAS_PATH)
    if ollama_disponivel():
        OllamaClient().warmup()


class NarrativaReq(BaseModel):
    fundo: str = "ALFA-33"
    backend: str = "ollama"


class PerguntaReq(BaseModel):
    pergunta: str
    backend: str = "ollama"
    fundo: str = "ALFA-33"


class AnalisarReq(BaseModel):
    pergunta: str
    backend: str = "ollama"
    fundo: str = "ALFA-33"


class IngestReq(BaseModel):
    nome: str = "Export"
    csv: str
    benchmark_pp: float = 3.10


class LoginReq(BaseModel):
    matricula: str
    senha: str


class LoginResp(BaseModel):
    token: str
    nome: str
    papel: str
    gestora_id: int


@app.post("/auth/login", response_model=LoginResp)
def login(req: LoginReq, db=Depends(get_db)):
    usuario = auth.autenticar(db, req.matricula, req.senha)
    if usuario is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="matrícula ou senha inválidas")
    return LoginResp(token=auth.criar_token(usuario), nome=usuario.nome,
                     papel=usuario.papel.value, gestora_id=usuario.gestora_id)


@app.get("/auth/me")
def quem_sou_eu(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual)):
    return {"matricula": usuario.matricula, "nome": usuario.nome,
            "papel": usuario.papel, "gestora_id": usuario.gestora_id}


def _parse_csv_contribuicoes(texto: str) -> list[dict]:
    """Parseia CSV de contribuições: estrategia,contribuicao_pp[,peso_medio]."""
    import csv
    import io

    linhas = []
    reader = csv.DictReader(io.StringIO(texto.strip()))
    cores = ["gold", "blue", "green", "neutral", "violet", "amber", "red"]
    for i, row in enumerate(reader):
        nome = (row.get("estrategia") or row.get("Estrategia") or "").strip()
        if not nome:
            continue
        try:
            contrib = float((row.get("contribuicao_pp") or "0").replace(",", "."))
        except ValueError:
            continue
        try:
            peso = float((row.get("peso_medio") or "0").replace(",", "."))
        except ValueError:
            peso = 0.0
        cor = "red" if contrib < 0 else cores[i % len(cores)]
        linhas.append({"nome": nome, "contribuicao_pp": round(contrib, 2), "peso_medio": peso, "cor": cor})
    return linhas


def _resumo_texto(f: dict) -> str:
    r = f["resumo"]
    estr = "; ".join(f"{e['nome']} {e['contribuicao_pp']:+.2f}pp" for e in f["estrategias"])
    return (
        f"Fundo: {f['fundo']['nome']} ({f['fundo']['classe']}). "
        f"Período: {f['fundo']['periodo']}. Benchmark: {f['fundo']['benchmark']}.\n"
        f"Retorno da cota: {r['retorno_cota']:.2f}%; benchmark: {r['retorno_bench']:.2f}%; "
        f"excesso: {r['excesso_pp']:+.2f}pp ({r['pct_cdi']:.0f}% do {f['fundo']['benchmark']}). "
        f"Beta: {r['beta']}; Alpha: {r['alpha_pp']:+.2f}pp.\n"
        f"Contribuição por estratégia: {estr}."
    )


def _fund_chunk(f: dict):
    from finrag.corpus import Chunk
    cod = f["fundo"]["codigo"]
    return Chunk(doc_id=f"dados_{cod}", chunk_id=0, text=_resumo_texto(f), source=f"dados:{cod}")


def _gerar_seguro(backend: str, prompt: str, rota: str = "", **kw) -> tuple[str, bool]:
    """Gera texto; se o backend falhar (ex.: Ollama ausente na VPS, timeout de
    nuvem), degrada para o MockLLM e sinaliza. Nunca deixa a demo cair.

    Meta 4: registra a chamada em observability (tokens/custo estimados,
    latência) — é o único ponto de saída de texto pro /narrativa e
    /perguntar, então é o lugar certo pra medir sem duplicar em cada rota.
    """
    t0 = time.perf_counter()
    try:
        texto = get_backend(backend).generate(prompt, **kw).strip()
        degradado = False
    except Exception:
        from finrag.models import MockLLM
        texto = MockLLM(
            "No período, o resultado do fundo foi sustentado principalmente pelo "
            "carrego das estratégias de crédito privado e juros."
        ).generate(prompt).strip()
        degradado = True
    latency_ms = int((time.perf_counter() - t0) * 1000)
    observability.registrar_chamada_llm(
        backend=("mock" if degradado else backend), modelo=backend, prompt=prompt,
        resposta=texto, latency_ms=latency_ms, rota=rota,
    )
    return texto, degradado


@app.get("/health")
def health():
    return {
        "status": "ok",
        "embed": STATE["embed"],
        "ollama": ollama_disponivel(),
        "chunks": len(STATE["index"]._chunks) if STATE["index"] else 0,
    }


@app.post("/narrativa")
def narrativa(req: NarrativaReq):
    t0 = time.perf_counter()
    fundos = STATE.get("fundos") or {}
    f = fundos.get(req.fundo) or (next(iter(fundos.values())) if fundos else None)
    if f is None:
        return {"texto": "", "citacoes": [], "backend": req.backend,
                "latency_ms": 0, "erro": "nenhum fundo carregado"}
    idx = STATE["index"]
    retr = idx.search("atribuição contribuição estratégia alpha beta carrego benchmark", k=3)
    regras = "\n".join(f"[{c.source}] {c.text[:280]}" for c, _ in retr)
    prompt = (
        "Você é um analista de performance de fundos. Escreva UM parágrafo objetivo, "
        "em português, explicando o resultado do fundo no período. Baseie-se SOMENTE nos "
        "números e nas regras abaixo; não invente dados. Foque em de onde veio o retorno.\n\n"
        f"NÚMEROS DO FUNDO:\n{_resumo_texto(f)}\n\n"
        f"REGRAS DE ATRIBUIÇÃO (contexto):\n{regras}" + INSTRUCAO_ESCOPO + "\n\nComentário:"
    )
    texto, degradado = _gerar_seguro(req.backend, prompt, rota="/narrativa", temperature=0.1, max_tokens=220)
    lat = int((time.perf_counter() - t0) * 1000)
    fontes = [c.source for c, _ in retr]
    audit.registrar(rota="/narrativa", fundo=f["fundo"]["codigo"], pergunta="(narrativa do período)",
                    backend=req.backend, latency_ms=lat, fontes=fontes, bloqueados=[],
                    resposta=texto)
    return {
        "texto": texto,
        "citacoes": [{"fonte": c.source, "trecho": c.text[:160].strip(), "score": round(float(s), 3)} for c, s in retr],
        "backend": req.backend,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/perguntar")
def perguntar(req: PerguntaReq):
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={"injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={"escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    idx = STATE["index"]
    codigos = e_comparativa(req.pergunta) or [req.fundo]
    fund_chunks = [_fund_chunk(STATE["fundos"][c]) for c in codigos if c in STATE["fundos"]]

    retr = idx.search(req.pergunta, k=4)
    scores = {id(c): s for c, s in retr}
    safe, blocked = sanitize_chunks([c for c, _ in retr])
    contexto = fund_chunks + safe
    prompt = build_augmented_prompt(req.pergunta, contexto) + INSTRUCAO_ESCOPO
    resposta, _deg = _gerar_seguro(req.backend, prompt, rota="/perguntar", temperature=0.1, max_tokens=380)
    lat = int((time.perf_counter() - t0) * 1000)
    citacoes = [
        {"fonte": c.source, "trecho": c.text[:160].strip(),
         "score": round(float(scores.get(id(c), 0)), 3)}
        for c in contexto
    ]
    audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[c["fonte"] for c in citacoes],
                    bloqueados=[c.source for c in blocked], resposta=resposta)
    return {
        "resposta": resposta,
        "citacoes": citacoes,
        "bloqueados": [{"fonte": c.source, "motivo": "prompt injection detectado pelo guardrail"} for c in blocked],
        "backend": req.backend,
        "latency_ms": lat,
    }


@app.post("/analisar")
def analisar_endpoint(req: AnalisarReq):
    """Copiloto de análise conversacional: traduz a pergunta em chamadas de
    ferramenta sobre os dados do fundo (POC sobre o seed) e devolve narrativa +
    gráfico(s) + chips de ação. Mesmos guardrails do /perguntar."""
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={"injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={"escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    fundos = STATE.get("fundos") or {}
    degradado = False
    try:
        cliente = get_backend(req.backend)
        if hasattr(cliente, "chat"):
            resultado = agente.analisar(pergunta=req.pergunta, fundo_ativo=req.fundo,
                                        backend=cliente, fundos=fundos)
        else:
            resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos, pergunta=req.pergunta)
            degradado = True
    except Exception:
        resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos, pergunta=req.pergunta)
        degradado = True

    lat = int((time.perf_counter() - t0) * 1000)
    audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[t["tool"] for t in resultado.get("tool_trace", [])],
                    bloqueados=[], resposta=resultado["resposta"],
                    extra={"consulta_echo": resultado.get("consulta_echo"),
                           "tool_trace": resultado.get("tool_trace")})
    return {
        "resposta": resultado["resposta"],
        "consulta_echo": resultado.get("consulta_echo", {}),
        "blocos": resultado.get("blocos", []),
        "acoes": resultado.get("acoes", []),
        "avisos": resultado.get("avisos", []),
        "citacoes": [],
        "bloqueados": [],
        "backend": req.backend,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/ingerir")
def ingerir(req: IngestReq):
    """Modo standalone: ingere um export (CSV) de contribuições e devolve o resumo.
    Prova o adaptador de arquivo — mesma leitura sem backend ao vivo."""
    estrategias = _parse_csv_contribuicoes(req.csv)
    if not estrategias:
        return {"ok": False, "erro": "CSV sem colunas reconhecidas (estrategia, contribuicao_pp)."}
    retorno = round(sum(e["contribuicao_pp"] for e in estrategias), 2)
    bench = round(req.benchmark_pp, 2)
    return {
        "ok": True,
        "fundo": {"nome": req.nome, "benchmark": "CDI", "periodo": "importado do arquivo"},
        "resumo": {
            "retorno_cota": retorno,
            "retorno_bench": bench,
            "excesso_pp": round(retorno - bench, 2),
            "pct_cdi": round(retorno / bench * 100, 1) if bench else 0.0,
        },
        "estrategias": estrategias,
        "n_estrategias": len(estrategias),
    }


@app.get("/radar")
def radar_endpoint():
    noticias = STATE.get("noticias") or []
    if not noticias:
        return {"ok": False, "noticias": [], "agregado": {}, "degradado": True}
    degradado = not any(n.get("fonte") == "rss" for n in noticias)
    return {"ok": True, "noticias": noticias, "agregado": agregar(noticias), "degradado": degradado}


@app.get("/sinais")
def sinais_endpoint(fundo: str = "ALFA-33"):
    """Alertas probabilísticos de apoio à decisão (modelo de regras auditável)."""
    fundos = STATE.get("fundos") or {}
    f = fundos.get(fundo) or (next(iter(fundos.values())) if fundos else None)
    noticias = STATE.get("noticias") or []
    if not f or not noticias:
        return {"ok": False, "sinais": [], "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}
    sinais = gerar_sinais(f, agregar(noticias), noticias)
    return {"ok": True, "sinais": sinais, "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}


@app.get("/auditoria")
def auditoria(limit: int = 50):
    """RBAC (Meta 4, `auth.exigir_papel("gestor", "compliance")`) foi
    desenhado e testado, mas decidi NÃO aplicar aqui ainda: o frontend não
    tem tela de login (0 wiring de auth no `apps/web`), então proteger essa
    rota deixava a página de Auditoria silenciosamente vazia sem nenhuma
    forma de autenticar pela UI. Fica pra quando o login existir de verdade."""
    return {"ok": True, "consultas": audit.ler(limit=limit)}


@app.get("/fundos")
def listar_fundos(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    """Isolamento multi-tenant: cada gestora só vê os próprios fundos —
    ver `db/repo.py::listar_fundos_da_gestora`."""
    from db.repo import listar_fundos_da_gestora
    fundos = listar_fundos_da_gestora(db, usuario.gestora_id)
    return {"ok": True, "fundos": [
        {"codigo": f.codigo, "nome": f.nome, "classe": f.classe, "benchmark": f.benchmark_padrao}
        for f in fundos
    ]}
