from atribuicao.reconciliacao import validar_batimento


def test_batimento_ok_dentro_da_tolerancia():
    r = validar_batimento(soma_contribuicoes_pp=4.25, retorno_cota_pp=4.25)
    assert r.ok is True
    assert r.divergencia_pp == 0.0
    assert "OK" in r.mensagem


def test_batimento_ok_com_pequena_divergencia_dentro_da_tolerancia():
    r = validar_batimento(soma_contribuicoes_pp=4.255, retorno_cota_pp=4.25, tolerancia_pp=0.01)
    assert r.ok is True


def test_batimento_diverge_acima():
    r = validar_batimento(soma_contribuicoes_pp=4.50, retorno_cota_pp=4.25, tolerancia_pp=0.01)
    assert r.ok is False
    assert r.divergencia_pp == 0.25
    assert "acima" in r.mensagem


def test_batimento_diverge_abaixo():
    r = validar_batimento(soma_contribuicoes_pp=4.00, retorno_cota_pp=4.25, tolerancia_pp=0.01)
    assert r.ok is False
    assert r.divergencia_pp == -0.25
    assert "abaixo" in r.mensagem


def test_mensagem_inclui_contexto_quando_fornecido():
    r = validar_batimento(4.00, 4.25, contexto="ALFA-33 · 2º trimestre 2026")
    assert "ALFA-33" in r.mensagem


def test_mensagem_lista_causas_provaveis_nao_e_apenas_stack_trace():
    r = validar_batimento(4.00, 4.25)
    assert "classificada" in r.mensagem or "período" in r.mensagem or "peso médio" in r.mensagem
