"""Guardrail anti prompt-injection sobre os trechos recuperados.

Decidi validar o conteúdo recuperado ANTES de montar o prompt aumentado porque
notei que, no RAG, o documento é uma superfície de ataque: um trecho pode conter
'ignore as instruções' e sequestrar o comportamento do modelo.
"""
from __future__ import annotations

import re

from .corpus import Chunk

INJECTION_PATTERNS: list[str] = [
    r"ignore.{0,20}(instru|previous|anterior|rules|regras)",
    r"(esque[çc]a|forget).{0,20}(regras|rules|instru)",
    r"disregard.{0,20}(previous|above|instructions)",
    r"act as (dan|administrador|system|root)",
    r"aja como (administrador|sistema|root)",
    r"reveal.{0,20}(prompt|system)",
    r"revele?.{0,20}(prompt|sistema)",
    r"voc[êe] agora (é|deve|assume|controla)",
]

_COMPILED = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in INJECTION_PATTERNS]


def detect_injection(text: str) -> bool:
    """Retorno True se o texto contém um padrão conhecido de injeção."""
    return any(rx.search(text) for rx in _COMPILED)


def sanitize_chunks(chunks: list[Chunk]) -> tuple[list[Chunk], list[Chunk]]:
    """Separo trechos seguros dos bloqueados, preservando a ordem original."""
    safe, blocked = [], []
    for chunk in chunks:
        (blocked if detect_injection(chunk.text) else safe).append(chunk)
    return safe, blocked
