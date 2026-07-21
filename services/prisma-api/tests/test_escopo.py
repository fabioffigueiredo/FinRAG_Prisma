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


def test_cobre_fraseado_coloquial_de_recomendacao():
    """Achado de plans/005-fechar-lacunas-guardrail-recomendacao.md — cada
    frase aqui falhava antes deste plano. Loop coleta TODAS as falhas antes
    de assertar (não para na primeira), pra nunca mais esconder um segundo
    gap como aconteceu na execução do plano 004."""
    positivos = [
        "vale a pena resgatar agora?",
        "qual o melhor fundo pra investir esse mês?",
        "compensa resgatar agora?",
        "é bom momento pra sair do fundo?",
        "o que eu compro agora?",
        "devo sair desse fundo?",
        "devo aportar mais agora?",
    ]
    falhas = [p for p in positivos if not pede_recomendacao(p)]
    assert not falhas, f"não recusadas: {falhas}"


def test_nao_flagra_explicativas_proximas_do_novo_vocabulario():
    """Perguntas legítimas que usam palavras parecidas com as novas do
    guardrail (sair/entrar/melhor/momento) mas não pedem recomendação."""
    negativos = [
        "Por que o fundo saiu da faixa de volatilidade esperada?",
        "Quando o gestor entrou nessa posição?",
        "Qual foi o melhor mês do fundo em 2026?",
        "Em que momento do trimestre o retorno virou positivo?",
        "Quanto o fundo vendeu em cotas de Bolsa Brasil no período?",
    ]
    falhas = [n for n in negativos if pede_recomendacao(n)]
    assert not falhas, f"falsos positivos: {falhas}"
