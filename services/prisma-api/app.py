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
import time
from pathlib import Path

from fastapi import FastAPI
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
from radar import carregar_noticias, agregar                             # noqa: E402
from sinais import gerar_sinais, AVISO_LEGAL, MODELO_VERSAO              # noqa: E402

app = FastAPI(title="Prisma API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: dict = {"index": None, "embed": "?", "fundos": None, "noticias": None}

NOMES_FUNDOS = {"alfa": "ALFA-33", "beta": "BETA-71", "gama": "GAMA-12"}


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


class IngestReq(BaseModel):
    nome: str = "Export"
    csv: str
    benchmark_pp: float = 3.10


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


def _gerar_seguro(backend: str, prompt: str, **kw) -> tuple[str, bool]:
    """Gera texto; se o backend falhar (ex.: Ollama ausente na VPS, timeout de
    nuvem), degrada para o MockLLM e sinaliza. Nunca deixa a demo cair."""
    try:
        return get_backend(backend).generate(prompt, **kw).strip(), False
    except Exception:
        from finrag.models import MockLLM
        texto = MockLLM(
            "No período, o resultado do fundo foi sustentado principalmente pelo "
            "carrego das estratégias de crédito privado e juros."
        ).generate(prompt).strip()
        return texto, True


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
    texto, degradado = _gerar_seguro(req.backend, prompt, temperature=0.1, max_tokens=220)
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
    resposta, _deg = _gerar_seguro(req.backend, prompt, temperature=0.1, max_tokens=380)
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
        return {"ok": False, "noticias": [], "agregado": {}}
    return {"ok": True, "noticias": noticias, "agregado": agregar(noticias)}


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
    return {"ok": True, "consultas": audit.ler(limit=limit)}
