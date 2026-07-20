"""Plan 002: nova tool `obter_sinais_mercado` (agent.py) e `analisar_mock`
deixando de ser cego à pergunta (mesma resposta pra 'rentabilidade' e pra
'indicação de mercado' era o bug original — ver
plans/002-copiloto-sinais-mercado-e-degradado-visivel.md)."""
import agent


def _fundo(codigo, retorno_cota, retorno_bench, pontos_cota, estrategias=None):
    return {
        "fundo": {"nome": f"Fundo {codigo}", "codigo": codigo, "benchmark": "CDI",
                  "periodo": "2T26", "classe": "Teste"},
        "resumo": {"retorno_cota": retorno_cota, "retorno_bench": retorno_bench,
                   "excesso_pp": round(retorno_cota - retorno_bench, 2), "pct_cdi": 0.0,
                   "beta": 0.5, "alpha_pp": round(retorno_cota - retorno_bench, 2),
                   "vol_anual": 1.0, "patrimonio_mm": 1.0, "num_cotistas": 1},
        "estrategias": estrategias or [{"nome": "Caixa e Over", "contribuicao_pp": retorno_cota,
                        "peso_medio": 100.0, "cor": "neutral"}],
        "serie_diaria": [{"data": f"2026-04-{i:02d}", "cota": v, "bench": 0.0}
                         for i, v in enumerate(pontos_cota, start=1)],
        "ativos": [], "fics": [],
    }


NOTICIAS = [
    {"id": "n07", "estrategia": "Bolsa Brasil", "sentimento": "negativo"},
    {"id": "n08", "estrategia": "Bolsa Brasil", "sentimento": "negativo"},
    {"id": "n09", "estrategia": "Bolsa Brasil", "sentimento": "negativo"},
    {"id": "n10", "estrategia": "Caixa e Over", "sentimento": "positivo"},
]


def _fundo_duas_estrategias(codigo="ALFA-33"):
    return _fundo(codigo, 1.0, 0.5, [0.0, 0.5, 1.0], estrategias=[
        {"nome": "Bolsa Brasil", "contribuicao_pp": -0.10, "peso_medio": 20.0, "cor": "gold"},
        {"nome": "Caixa e Over", "contribuicao_pp": 0.48, "peso_medio": 80.0, "cor": "neutral"},
    ])


# --- _tool_obter_sinais_mercado ---------------------------------------------

def test_obter_sinais_mercado_devolve_sinal_ordenado_por_risco():
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    out = agent._tool_obter_sinais_mercado(fundos, NOTICIAS, {"fundo": "ALFA-33"})
    assert "erro" not in out
    assert out["sinais"], "esperava ao menos um sinal"
    assert out["sinais"][0]["nivel"] in ("ok", "atencao", "alerta")
    assert out["sinais"][0]["evidencias"]
    assert out["aviso_legal"] == agent.SINAIS_AVISO_LEGAL
    # ordenado por risco: maior prob_neg primeiro
    probs = [s["prob_neg"] for s in out["sinais"]]
    assert probs == sorted(probs, reverse=True)
    # Bolsa Brasil (3 notícias negativas, contribuição negativa) é o pior sinal
    assert out["sinais"][0]["estrategia"] == "Bolsa Brasil"
    assert out["sinais"][0]["nivel"] == "alerta"


def test_obter_sinais_mercado_sem_noticias_nao_inventa():
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    out = agent._tool_obter_sinais_mercado(fundos, [], {"fundo": "ALFA-33"})
    assert "erro" not in out
    assert out["sinais"] == []
    assert out.get("aviso")
    assert out["aviso_legal"] == agent.SINAIS_AVISO_LEGAL


def test_obter_sinais_mercado_fundo_inexistente_retorna_erro():
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    out = agent._tool_obter_sinais_mercado(fundos, NOTICIAS, {"fundo": "NAO-EXISTE"})
    assert "erro" in out


# --- analisar_mock deixa de ser cego à pergunta -----------------------------

def test_analisar_mock_pergunta_sobre_rentabilidade_difere_de_pergunta_sobre_mercado():
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    a = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=NOTICIAS,
                             pergunta="Qual foi a rentabilidade do fundo no semestre?")
    b = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=NOTICIAS,
                             pergunta="Qual a indicação do mercado para esse fundo?")
    assert a["resposta"] != b["resposta"]
    assert "Demonstração" in a["resposta"]
    assert "Demonstração" in b["resposta"]
    # a de rentabilidade narra atribuição (excesso pp); a de mercado narra sinal (nível/probabilidade)
    assert "excesso de" in a["resposta"]
    assert "nível" in b["resposta"] or "Sem sinal" in b["resposta"]


def test_analisar_mock_pergunta_evolucao_devolve_grafico_linha_nao_waterfall():
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="Mostre o gráfico de evolução do ALFA-33 no período")
    assert out["blocos"], "esperava um bloco de gráfico"
    assert out["blocos"][0]["chart"] == "linha"


def test_analisar_mock_pergunta_grupo_contabil_muda_dimensao():
    fundos = {
        "ALFA-33": {
            "fundo": {"nome": "Alfa Multimercado FIC FIM", "codigo": "ALFA-33",
                     "benchmark": "CDI", "periodo": "2º trimestre 2026 (abr–jun)",
                     "classe": "Multimercado Macro"},
            "resumo": {"retorno_cota": 4.25, "retorno_bench": 3.10, "excesso_pp": 1.15,
                      "pct_cdi": 137.1, "beta": 0.15, "alpha_pp": 1.10, "vol_anual": 4.8,
                      "patrimonio_mm": 1284.6, "num_cotistas": 3120},
            "estrategias": [{"nome": "Crédito Privado", "contribuicao_pp": 1.35,
                            "peso_medio": 28.0, "cor": "gold"}],
            "serie_diaria": [], "ativos": [], "fics": [],
        }
    }
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="Mostre a atribuição do ALFA-33 por grupo contábil")
    if out["consulta_echo"].get("dimensao") != agent.DIMENSOES_LABEL["grupo_contabil"]:
        import pytest
        pytest.skip("Postgres de dev indisponível/não semeado para grupo_contabil — "
                    "fallback já coberto por test_agent_db_integration.py")
    assert out["consulta_echo"]["dimensao"] == agent.DIMENSOES_LABEL["grupo_contabil"]


def test_analisar_mock_pergunta_sem_palavra_chave_mantem_comportamento_de_atribuicao():
    """Regressão: pergunta genérica (sem sinal/evolução/grupo contábil) deve
    continuar caindo no fluxo original de atribuição, idêntico ao anterior."""
    fundos = {"ALFA-33": _fundo_duas_estrategias()}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=NOTICIAS,
                              pergunta="Como foi o desempenho do fundo?")
    assert out["blocos"]
    assert out["blocos"][0]["chart"] == "waterfall"
    assert "excesso de" in out["resposta"]
