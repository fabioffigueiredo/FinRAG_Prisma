"""Embeddings do Prisma via Ollama bge-m3 (1024-dim, multilíngue SOTA).

Expõe uma função compatível com o *seam* SemanticIndex(embed_fn=...) do FinRAG.
Se o Ollama não estiver disponível, retorna None para que o índice caia no
sentence-transformers padrão do FinRAG.
"""
from __future__ import annotations

import os
import numpy as np
import requests

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
EMBED_MODEL = os.environ.get("PRISMA_EMBED_MODEL", "bge-m3:567m")


def _embed_one(text: str) -> list[float]:
    resp = requests.post(
        f"{OLLAMA_BASE}/api/embeddings",
        json={"model": EMBED_MODEL, "prompt": text},
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["embedding"]


def ollama_embed(texts: list[str]) -> np.ndarray:
    """embed_fn compatível com SemanticIndex: list[str] -> np.ndarray (n, 1024)."""
    vecs = [_embed_one(t) for t in texts]
    return np.asarray(vecs, dtype="float32")


def get_embed_fn():
    """Retorna a função de embedding bge-m3 se o Ollama responder; senão None."""
    try:
        requests.get(f"{OLLAMA_BASE}/api/version", timeout=2).raise_for_status()
        # valida o modelo com uma chamada curta
        _embed_one("teste")
        return ollama_embed
    except Exception:
        return None
