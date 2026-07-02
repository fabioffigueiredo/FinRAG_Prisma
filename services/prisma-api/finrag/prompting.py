"""Prompt engineering e saída estruturada do FinRAG.

Decidi forçar saída JSON com validação pydantic e temperatura 0 porque notei
que sem schema a LLM varia o formato e quebra o parsing a jusante.
"""
from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import BaseModel

from .models import LLMClient


class FinancialExtraction(BaseModel):
    empresa: str
    evento: str
    sentimento: Literal["positivo", "negativo", "neutro"]
    risco: str
    horizonte: str


_SCHEMA_HINT = (
    'Responda APENAS com um objeto JSON com as chaves exatas: '
    '"empresa", "evento", "sentimento" (positivo|negativo|neutro), '
    '"risco", "horizonte".'
)

_FEW_SHOT = (
    'Exemplo:\n'
    'Texto: "A Beta Corp anunciou recompra recorde de ações."\n'
    '{"empresa":"Beta Corp","evento":"recompra de ações",'
    '"sentimento":"positivo","risco":"baixo","horizonte":"médio"}\n\n'
)


def build_extraction_prompt(text: str, technique: str = "few_shot") -> str:
    """Monto o prompt da técnica escolhida sobre a mesma tarefa de extração."""
    base = f"Você é um analista financeiro. {_SCHEMA_HINT}\n\n"
    tail = f'Texto: "{text}"\n'
    if technique == "zero_shot":
        return base + tail
    if technique == "few_shot":
        return base + _FEW_SHOT + tail
    if technique == "cot":
        return (base + "Pense passo a passo internamente, mas devolva SÓ o JSON.\n"
                + tail)
    if technique == "meta":
        return (base + "Antes de responder, critique mentalmente sua extração "
                "e corrija inconsistências. Devolva SÓ o JSON final.\n" + tail)
    raise ValueError(f"técnica desconhecida: {technique}")


def parse_json_response(raw: str) -> dict:
    """Extraio o primeiro objeto JSON de uma resposta possivelmente suja."""
    cleaned = re.sub(r"```(?:json)?", "", raw).strip()
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if not match:
        raise ValueError("nenhum objeto JSON encontrado na resposta")
    return json.loads(match.group(0))


def validate_extraction(data: dict) -> FinancialExtraction:
    """Valido contra o schema; pydantic levanta se faltar campo ou enum inválido."""
    return FinancialExtraction(**data)


def extract(text: str, llm: LLMClient,
            technique: str = "few_shot") -> FinancialExtraction:
    """Orquestro prompt -> geração -> parse -> validação."""
    prompt = build_extraction_prompt(text, technique)
    raw = llm.generate(prompt, temperature=0.0)
    return validate_extraction(parse_json_response(raw))
