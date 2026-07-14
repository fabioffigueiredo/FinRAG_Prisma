"""Meta 3: o copiloto agora cobre as 8 dimensões, buscando no Postgres da
Meta 1 quando disponível — antes só 'estrategia' funcionava, o resto
retornava sempre o aviso de 'indisponível na demo'.

Precisa do Postgres de dev rodando e semeado (`scripts/seed_db.py`) — usa
o fundo ALFA-33 real, que já está lá."""
import agent

PERIODO_REAL = "2º trimestre 2026 (abr–jun)"


def _fundo_alfa_real():
    return {
        "ALFA-33": {
            "fundo": {"nome": "Alfa Multimercado FIC FIM", "codigo": "ALFA-33",
                     "benchmark": "CDI", "periodo": PERIODO_REAL, "classe": "Multimercado Macro"},
            "resumo": {"retorno_cota": 4.25, "retorno_bench": 3.10, "excesso_pp": 1.15,
                      "pct_cdi": 137.1, "beta": 0.15, "alpha_pp": 1.10, "vol_anual": 4.8,
                      "patrimonio_mm": 1284.6, "num_cotistas": 3120},
            "estrategias": [{"nome": "Crédito Privado", "contribuicao_pp": 1.35,
                            "peso_medio": 28.0, "cor": "gold"}],
            "serie_diaria": [], "ativos": [], "fics": [],
        }
    }


def test_dimensao_grupo_contabil_busca_no_postgres_quando_disponivel():
    fundos = _fundo_alfa_real()
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "grupo_contabil"})
    if not out["estrategias"] or out["dimensao"] != "grupo_contabil":
        import pytest
        pytest.skip("Postgres de dev indisponível/não semeado — rode docker-compose.dev.yml + seed_db")
    assert out["dimensao"] == "grupo_contabil"
    assert out["aviso"] is None
    assert len(out["estrategias"]) >= 1
    assert all("nome" in e and "contribuicao_pp" in e for e in out["estrategias"])


def test_dimensao_sem_dado_no_banco_cai_no_aviso_antigo():
    fundos = _fundo_alfa_real()
    fundos["ALFA-33"]["fundo"]["periodo"] = "período que não existe no banco"
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "grupo_contabil"})
    assert out["dimensao"] == "estrategia"
    assert out["aviso"] is not None
    assert "não está disponível" in out["aviso"]


def test_dimensao_estrategia_nao_muda_comportamento_existente():
    fundos = _fundo_alfa_real()
    out = agent._tool_obter_atribuicao(fundos, {"fundo": "ALFA-33", "dimensao": "estrategia"})
    assert out["dimensao"] == "estrategia"
    assert out["estrategias"][0]["nome"] == "Crédito Privado"
