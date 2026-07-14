import app


def test_comparativa_por_nomes():
    assert set(app.e_comparativa("Compare o Alfa e o Beta no trimestre")) == {"ALFA-33", "BETA-71"}


def test_comparativa_palavra_compare_sem_nomes_inclui_todos():
    assert set(app.e_comparativa("compare os fundos")) == set(app.NOMES_FUNDOS.values())


def test_nao_comparativa():
    assert app.e_comparativa("De onde veio o retorno do fundo?") == []


def test_resumo_texto_usa_benchmark_do_fundo():
    f = {
        "fundo": {"nome": "X", "classe": "Ações", "periodo": "T", "benchmark": "IBOVESPA", "codigo": "X-1"},
        "resumo": {"retorno_cota": 6.4, "retorno_bench": 5.8, "excesso_pp": 0.6,
                   "pct_cdi": 110.3, "beta": 0.92, "alpha_pp": 0.85},
        "estrategias": [{"nome": "Bancos", "contribuicao_pp": 2.6}],
    }
    texto = app._resumo_texto(f)
    assert "% do IBOVESPA" in texto and "% do CDI" not in texto
