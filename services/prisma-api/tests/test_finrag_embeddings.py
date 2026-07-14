import numpy as np
from finrag.corpus import Chunk
from finrag.embeddings import SemanticIndex, bm25_search, hybrid_search


def _fake_embed(texts):
    vecs = []
    for t in texts:
        v = np.zeros(32, dtype="float32")
        for ch in t.lower():
            v[ord(ch) % 32] += 1.0
        vecs.append(v)
    return np.vstack(vecs)


def _hybrid_scenario():
    # chunk 0 só vence por SEMÂNTICA (char-histograma próximo da query, mas
    # nenhum token igual a "netuno" -> BM25 = 0 pra ele).
    semantic_only = Chunk(doc_id="d", chunk_id=0, text="netun o", source="s")
    # chunk 1 só vence por BM25 (contém o token exato "netuno", mas diluído
    # por muito texto irrelevante -> cosseno baixo pro fake embedder).
    lexical_only = Chunk(doc_id="d", chunk_id=1,
                         text="netuno " + "abcdefghijklmnopqrstuvwxyz" * 10,
                         source="s")
    irrelevant_a = Chunk(doc_id="d", chunk_id=2,
                        text="o gato dorme tranquilo no sofa macio da sala", source="s")
    irrelevant_b = Chunk(doc_id="d", chunk_id=3,
                        text="cachorro late alto no quintal vazio", source="s")
    return [semantic_only, lexical_only, irrelevant_a, irrelevant_b]


def test_hybrid_search_combines_semantic_and_lexical():
    chunks = _hybrid_scenario()
    idx = SemanticIndex(embed_fn=_fake_embed)
    idx.build(chunks)
    query = "netuno"

    semantic_top1 = {c.chunk_id for c, _ in idx.search(query, k=1)}
    lexical_top1 = {c.chunk_id for c, _ in bm25_search(query, chunks, k=1)}
    assert semantic_top1 == {0}
    assert lexical_top1 == {1}

    hybrid_top2 = {c.chunk_id for c, _ in hybrid_search(query, idx, chunks, k=2)}
    assert hybrid_top2 == {0, 1}


def test_hybrid_search_respects_k():
    chunks = _hybrid_scenario()
    idx = SemanticIndex(embed_fn=_fake_embed)
    idx.build(chunks)
    res = hybrid_search("netuno", idx, chunks, k=2)
    assert len(res) <= 2
