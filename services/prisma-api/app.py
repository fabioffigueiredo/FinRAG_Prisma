"""Prisma API — camada cognitiva sobre a atribuição de performance.

Envolve o núcleo FinRAG (retrieval + guardrail + prompt aumentado) e expõe:
  POST /narrativa   -> comentário do fundo em linguagem natural (grounded)
  POST /perguntar   -> Q&A RAG fundamentado, com citações e trechos bloqueados
  GET  /health      -> status + backends disponíveis

Reusa o FinRAG sem reescrevê-lo; adiciona backend Ollama (local) e embeddings bge-m3.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

HERE = Path(__file__).resolve()
PRISMA = HERE.parents[2]          # .../PD1/prisma
PD1 = HERE.parents[3]             # .../PD1
FINRAG_SRC = PD1 / "Finrag" / "src"
CORPUS_DIR = PRISMA / "data" / "corpus"
SEED = PRISMA / "data" / "seed" / "fundo_alfa.json"

sys.path.insert(0, str(FINRAG_SRC))

from finrag.corpus import load_documents, chunk_corpus  # noqa: E402
from finrag.embeddings import SemanticIndex              # noqa: E402
from finrag.guardrails import sanitize_chunks            # noqa: E402
from finrag.rag import build_augmented_prompt            # noqa: E402

from llm import get_backend, ollama_disponivel, OllamaClient  # noqa: E402
from embed import get_embed_fn                                # noqa: E402

app = FastAPI(title="Prisma API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

STATE: dict = {"index": None, "embed": "?", "fundo": None}


def _corpus_docs():
    """Carrega o corpus de regras (.md tratados como .txt pelo FinRAG loader)."""
    # o loader do FinRAG lê *.txt; espelhamos os .md como .txt em tempo de carga
    docs = []
    for md in sorted(CORPUS_DIR.glob("*.md")):
        from finrag.corpus import Document
        docs.append(Document(id=md.stem, text=md.read_text(encoding="utf-8"), source=md.name))
    return docs


@app.on_event("startup")
def _startup() -> None:
    embed_fn = get_embed_fn()
    STATE["embed"] = "bge-m3 (Ollama)" if embed_fn else "sentence-transformers (fallback)"
    idx = SemanticIndex(embed_fn=embed_fn) if embed_fn else SemanticIndex()
    idx.build(chunk_corpus(_corpus_docs()))
    STATE["index"] = idx
    STATE["fundo"] = json.loads(SEED.read_text(encoding="utf-8"))
    if ollama_disponivel():
        OllamaClient().warmup()


class NarrativaReq(BaseModel):
    fundo: str = "ALFA-33"
    backend: str = "ollama"


class PerguntaReq(BaseModel):
    pergunta: str
    backend: str = "ollama"


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
        f"excesso: {r['excesso_pp']:+.2f}pp ({r['pct_cdi']:.0f}% do CDI). "
        f"Beta: {r['beta']}; Alpha: {r['alpha_pp']:+.2f}pp.\n"
        f"Contribuição por estratégia: {estr}."
    )


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
    f = STATE["fundo"]
    idx = STATE["index"]
    # RAG: recupera regras relevantes para fundamentar a leitura
    retr = idx.search("atribuição contribuição estratégia alpha beta carrego benchmark", k=3)
    regras = "\n".join(f"[{c.source}] {c.text[:280]}" for c, _ in retr)
    prompt = (
        "Você é um analista de performance de fundos. Escreva UM parágrafo objetivo, "
        "em português, explicando o resultado do fundo no período. Baseie-se SOMENTE nos "
        "números e nas regras abaixo; não invente dados. Foque em de onde veio o retorno.\n\n"
        f"NÚMEROS DO FUNDO:\n{_resumo_texto(f)}\n\n"
        f"REGRAS DE ATRIBUIÇÃO (contexto):\n{regras}\n\nComentário:"
    )
    llm = get_backend(req.backend)
    texto = llm.generate(prompt, temperature=0.1, max_tokens=220).strip()
    return {
        "texto": texto,
        "citacoes": [{"fonte": c.source, "trecho": c.text[:160].strip(), "score": round(float(s), 3)} for c, s in retr],
        "backend": req.backend,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
    }


@app.post("/perguntar")
def perguntar(req: PerguntaReq):
    t0 = time.perf_counter()
    idx = STATE["index"]
    retr = idx.search(req.pergunta, k=4)
    scores = {id(c): s for c, s in retr}
    chunks = [c for c, _ in retr]
    safe, blocked = sanitize_chunks(chunks)
    prompt = build_augmented_prompt(req.pergunta, safe)
    llm = get_backend(req.backend)
    resposta = llm.generate(prompt, temperature=0.1, max_tokens=380).strip()
    return {
        "resposta": resposta,
        "citacoes": [
            {"fonte": c.source, "trecho": c.text[:160].strip(), "score": round(float(scores.get(id(c), 0)), 3)}
            for c in safe
        ],
        "bloqueados": [{"fonte": c.source, "motivo": "prompt injection detectado pelo guardrail"} for c in blocked],
        "backend": req.backend,
        "latency_ms": int((time.perf_counter() - t0) * 1000),
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
