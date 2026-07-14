"""Embeddings semânticos (FAISS) e baseline lexical (BM25).

Decidi tornar o embedder injetável porque notei que assim os testes rodam
offline (embedding fake) e o notebook usa o sentence-transformers real — mesma
classe, sem duplicar lógica de índice.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Callable

import faiss
import numpy as np

from .corpus import Chunk

_DEFAULT_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _normalize(mat: np.ndarray) -> np.ndarray:
    """Normalizo L2 para que produto interno = similaridade de cosseno."""
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return (mat / norms).astype("float32")


class SemanticIndex:
    """Decidi encapsular o índice FAISS numa classe porque notei que assim
    guardo os chunks junto com os vetores e troco o embedder sem mexer na
    busca."""
    def __init__(self, model_name: str = _DEFAULT_MODEL,
                 embed_fn: "Callable[[list[str]], np.ndarray] | None" = None) -> None:
        self.model_name = model_name
        self._embed_fn = embed_fn
        self._index: "faiss.Index | None" = None
        self._chunks: list[Chunk] = []

    def _embed(self, texts: list[str]) -> np.ndarray:
        if self._embed_fn is not None:
            return _normalize(np.asarray(self._embed_fn(texts), dtype="float32"))
        from sentence_transformers import SentenceTransformer
        if not hasattr(self, "_model"):
            self._model = SentenceTransformer(self.model_name)
        vecs = self._model.encode(texts, convert_to_numpy=True)
        return _normalize(vecs.astype("float32"))

    def build(self, chunks: list[Chunk]) -> None:
        """Construo o índice: gero os embeddings normalizados dos chunks e
        adiciono ao FAISS."""
        self._chunks = list(chunks)
        mat = self._embed([c.text for c in self._chunks])
        self._index = faiss.IndexFlatIP(mat.shape[1])
        self._index.add(mat)

    def search(self, query: str, k: int = 4) -> list[tuple[Chunk, float]]:
        """Busco os k chunks mais similares à query por produto interno
        (= cosseno, pois normalizei)."""
        assert self._index is not None, "índice não construído"
        qv = self._embed([query])
        scores, idxs = self._index.search(qv, min(k, len(self._chunks)))
        return [(self._chunks[i], float(s))
                for s, i in zip(scores[0], idxs[0]) if i >= 0]

    def save(self, folder: "str | Path") -> None:
        """Salvo o índice FAISS e a lista de chunks lado a lado para reuso
        sem reindexar."""
        assert self._index is not None, "índice não construído"
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._index, str(folder / "index.faiss"))
        with open(folder / "chunks.pkl", "wb") as fh:
            pickle.dump(self._chunks, fh)

    def load(self, folder: "str | Path") -> None:
        """Carrego o índice FAISS e os chunks persistidos."""
        folder = Path(folder)
        self._index = faiss.read_index(str(folder / "index.faiss"))
        with open(folder / "chunks.pkl", "rb") as fh:
            self._chunks = pickle.load(fh)

    @property
    def chunks(self) -> list[Chunk]:
        """Exponho os chunks indexados porque notei que hybrid_search
        precisa da mesma lista pra rodar o BM25 lado a lado do FAISS."""
        return self._chunks


def bm25_search(query: str, chunks: list[Chunk], k: int = 4) -> list[tuple[Chunk, float]]:
    """Uso BM25 como baseline lexical para contrastar com a busca semântica."""
    from rank_bm25 import BM25Okapi
    corpus_tokens = [c.text.lower().split() for c in chunks]
    bm25 = BM25Okapi(corpus_tokens)
    scores = bm25.get_scores(query.lower().split())
    ranked = sorted(zip(chunks, scores), key=lambda p: p[1], reverse=True)
    return [(c, float(s)) for c, s in ranked[:k]]


def hybrid_search(query: str, index: SemanticIndex, chunks: list[Chunk],
                  k: int = 4) -> list[tuple[Chunk, float]]:
    """Fundo semântica (FAISS) e lexical (BM25) por Reciprocal Rank Fusion.

    Decidi fundir por RANKING (RRF), não por soma de scores brutos, porque
    notei que cosseno normalizado (0-1) e BM25 (escala aberta, sem teto) não
    são comparáveis diretamente — somar os dois distorceria a fusão a favor
    de qualquer um que tenha escala maior.
    """
    n = len(chunks)
    if n == 0:
        return []
    semantic_ranked = [c for c, _ in index.search(query, k=n)]
    lexical_ranked = [c for c, _ in bm25_search(query, chunks, k=n)]

    def _key(c: Chunk) -> tuple[str, int]:
        return (c.doc_id, c.chunk_id)

    scores: dict[tuple[str, int], float] = {}
    lookup: dict[tuple[str, int], Chunk] = {}
    for ranked in (semantic_ranked, lexical_ranked):
        for rank, chunk in enumerate(ranked, start=1):
            ck = _key(chunk)
            lookup[ck] = chunk
            scores[ck] = scores.get(ck, 0.0) + 1.0 / (60 + rank)

    ordered = sorted(scores.items(), key=lambda item: item[1], reverse=True)
    return [(lookup[ck], score) for ck, score in ordered[:k]]
