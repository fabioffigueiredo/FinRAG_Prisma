import agent


def _fundo(codigo, retorno_cota, retorno_bench, pontos_cota):
    return {
        "fundo": {"nome": f"Fundo {codigo}", "codigo": codigo, "benchmark": "CDI",
                  "periodo": "2T26", "classe": "Teste"},
        "resumo": {"retorno_cota": retorno_cota, "retorno_bench": retorno_bench,
                   "excesso_pp": round(retorno_cota - retorno_bench, 2), "pct_cdi": 0.0,
                   "beta": 0.5, "alpha_pp": round(retorno_cota - retorno_bench, 2),
                   "vol_anual": 1.0, "patrimonio_mm": 1.0, "num_cotistas": 1},
        "estrategias": [{"nome": "Caixa e Over", "contribuicao_pp": retorno_cota,
                        "peso_medio": 100.0, "cor": "neutral"}],
        "serie_diaria": [{"data": f"2026-04-{i:02d}", "cota": v, "bench": 0.0}
                         for i, v in enumerate(pontos_cota, start=1)],
        "ativos": [], "fics": [],
    }


def test_obter_resumo_fundo_com_retorno_negativo():
    fundos = {"DELTA-08": _fundo("DELTA-08", -1.85, 3.05, [0.0, -0.9, -1.85])}
    out = agent._tool_obter_resumo(fundos, {"fundo": "DELTA-08"})
    assert out["resumo"]["retorno_cota"] < 0
    assert out["resumo"]["excesso_pp"] < 0


def test_obter_serie_distingue_fundo_baixa_e_alta_volatilidade():
    fundos = {
        "THETA-52": _fundo("THETA-52", 3.65, 3.05,
                          [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.65]),
        "ZETA-19": _fundo("ZETA-19", 7.80, 3.05,
                         [0.0, 5.0, -2.0, 6.5, -1.0, 8.0, 3.0, 7.80]),
    }
    baixa = agent._tool_obter_serie(fundos, {"fundo": "THETA-52"})
    alta = agent._tool_obter_serie(fundos, {"fundo": "ZETA-19"})

    def amplitude(serie):
        cotas = [p["cota"] for p in serie["serie"]]
        return max(cotas) - min(cotas)

    assert amplitude(alta) > amplitude(baixa)
