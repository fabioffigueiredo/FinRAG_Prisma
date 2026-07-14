"""Meta 3: busca semântica de fundo — substitui 'precisa saber o código
exato' por busca por significado (embeddings), a dor #1 do sistema real."""
import numpy as np

import agent


def _fake_embed(texts):
    """Mesmo fake bag-of-chars determinístico usado nos testes do FinRAG —
    offline, sem baixar modelo nenhum."""
    vecs = []
    for t in texts:
        v = np.zeros(32, dtype="float32")
        for ch in t.lower():
            v[ord(ch) % 32] += 1.0
        vecs.append(v)
    return np.vstack(vecs)


def _fundos_teste():
    return {
        "ALFA-33": {"fundo": {"nome": "Alfa Multimercado FIC FIM", "classe": "Multimercado Macro",
                             "benchmark": "CDI"}},
        "GAMA-12": {"fundo": {"nome": "Gama Renda Fixa CP", "classe": "Renda Fixa Crédito Privado",
                             "benchmark": "CDI"}},
    }


def test_match_exato_nao_usa_indice_semantico():
    fundos = _fundos_teste()
    indice = agent.construir_indice_semantico_fundos(fundos, embed_fn=_fake_embed)
    assert agent._match_fundo(fundos, "ALFA-33", indice_semantico=indice) == "ALFA-33"


def test_match_semantico_por_classe_quando_nome_nao_bate():
    fundos = _fundos_teste()
    indice = agent.construir_indice_semantico_fundos(fundos, embed_fn=_fake_embed)
    # "renda fixa credito privado" tem MUITO mais sobreposição de caracteres
    # com a classe do Gama do que com a do Alfa — resolve por significado,
    # sem bater substring nenhuma do nome "Gama Renda Fixa CP".
    resultado = agent._match_fundo(fundos, "renda fixa credito privado", indice_semantico=indice)
    assert resultado == "GAMA-12"


def test_sem_indice_semantico_comportamento_antigo_preservado():
    fundos = _fundos_teste()
    assert agent._match_fundo(fundos, "não existe nenhum fundo assim") is None


def test_indice_constroi_um_chunk_por_fundo():
    fundos = _fundos_teste()
    indice = agent.construir_indice_semantico_fundos(fundos, embed_fn=_fake_embed)
    assert len(indice.chunks) == len(fundos)
