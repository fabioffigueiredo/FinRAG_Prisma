import app


def test_comparativa_por_nomes():
    assert set(app.e_comparativa("Compare o Alfa e o Beta no trimestre")) == {"ALFA-33", "BETA-71"}


def test_comparativa_palavra_compare_sem_nomes_inclui_todos():
    assert set(app.e_comparativa("compare os fundos")) == {"ALFA-33", "BETA-71", "GAMA-12"}


def test_nao_comparativa():
    assert app.e_comparativa("De onde veio o retorno do fundo?") == []
