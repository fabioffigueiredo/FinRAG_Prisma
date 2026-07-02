from escopo import pede_recomendacao, INSTRUCAO_ESCOPO, RESPOSTA_ESCOPO


def test_detecta_pedidos_de_recomendacao():
    positivos = [
        "Qual fundo devo comprar?",
        "Você recomenda investir no Alfa?",
        "Qual a previsão para o próximo trimestre?",
        "O Beta vai subir?",
        "Qual o melhor fundo para investir agora?",
    ]
    for p in positivos:
        assert pede_recomendacao(p), p


def test_nao_flagra_perguntas_explicativas():
    negativos = [
        "De onde veio o retorno do fundo no período?",
        "Por que o varejo pesou no resultado?",
        "Compare o Alfa e o Beta no trimestre",
        "O que significa o beta baixo?",
    ]
    for n in negativos:
        assert not pede_recomendacao(n), n


def test_constantes_existem():
    assert "não" in RESPOSTA_ESCOPO.lower()
    assert "recomendação" in INSTRUCAO_ESCOPO.lower() or "recomenda" in INSTRUCAO_ESCOPO.lower()
