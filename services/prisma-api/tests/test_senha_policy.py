"""Política de senha (Stage 3, hardening) — puramente unitário, sem banco."""
from senha_policy import validar_senha


def test_senha_valida_nao_tem_violacoes():
    assert validar_senha("Senha-Forte-123!") == []


def test_senha_curta_e_rejeitada():
    violacoes = validar_senha("Ab1!")
    assert any("caracteres" in v for v in violacoes)


def test_senha_sem_maiuscula_e_rejeitada():
    violacoes = validar_senha("senha-forte-123!")
    assert any("maiúscula" in v for v in violacoes)


def test_senha_sem_minuscula_e_rejeitada():
    violacoes = validar_senha("SENHA-FORTE-123!")
    assert any("minúscula" in v for v in violacoes)


def test_senha_sem_digito_e_rejeitada():
    violacoes = validar_senha("Senha-Forte-Sem-Numero!")
    assert any("dígito" in v for v in violacoes)


def test_senha_sem_caractere_especial_e_rejeitada():
    violacoes = validar_senha("SenhaForte123")
    assert any("especial" in v for v in violacoes)


def test_senha_valida_no_limite_do_minimo():
    assert validar_senha("Ab1!ab1!ab") == []


def test_senha_vazia_acumula_todas_as_violacoes():
    violacoes = validar_senha("")
    assert len(violacoes) == 5
