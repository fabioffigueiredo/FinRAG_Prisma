"""Política de senha compartilhada — mesma regra validada no cliente
(apps/web/src/lib/senha.ts, feedback imediato) e aqui (o que de fato conta;
nunca confiar só na validação client-side).
"""
from __future__ import annotations

import re

MIN_LEN = 10


def validar_senha(senha: str) -> list[str]:
    """Retorna a lista de violações — vazia significa senha válida."""
    violacoes = []
    if len(senha) < MIN_LEN:
        violacoes.append(f"mínimo de {MIN_LEN} caracteres")
    if not re.search(r"[A-Z]", senha):
        violacoes.append("pelo menos 1 letra maiúscula")
    if not re.search(r"[a-z]", senha):
        violacoes.append("pelo menos 1 letra minúscula")
    if not re.search(r"\d", senha):
        violacoes.append("pelo menos 1 dígito")
    if not re.search(r"[^A-Za-z0-9]", senha):
        violacoes.append("pelo menos 1 caractere especial")
    return violacoes
