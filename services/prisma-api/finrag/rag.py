"""Pipeline RAG: recuperar -> sanear -> aumentar -> gerar.

Decidi montar o prompt aumentado à mão (Python puro) porque notei que o
enunciado valoriza demonstrar domínio do pipeline, não consumir uma chain pronta.
A flag use_context me deixa comparar resposta COM e SEM recuperação no notebook.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Chunk
from .embeddings import SemanticIndex
from .guardrails import sanitize_chunks
from .models import LLMClient


@dataclass
class RAGResult:
    answer: str
    contexts: list[Chunk] = field(default_factory=list)
    blocked: list[Chunk] = field(default_factory=list)
    used_context: bool = True


def build_augmented_prompt(question: str, contexts: list[Chunk]) -> str:
    """Monto o prompt com papel, contexto recuperado e instrução de fundamentar."""
    trechos = "\n\n".join(f"[Trecho {i + 1} | {c.source}]\n{c.text}"
                          for i, c in enumerate(contexts))
    return (
        "Você é um assistente da Gestora. Responda à pergunta usando APENAS os "
        "trechos abaixo. Se a resposta não estiver neles, diga que não há base "
        "documental.\n\n"
        f"=== CONTEXTO ===\n{trechos}\n\n"
        f"=== PERGUNTA ===\n{question}\n\n=== RESPOSTA ==="
    )


def answer(question: str, index: SemanticIndex, llm: LLMClient, *,
           k: int = 4, use_context: bool = True,
           guardrail: bool = True) -> RAGResult:
    """Executo o pipeline; sem contexto, gero direto (baseline para comparação)."""
    if not use_context:
        return RAGResult(answer=llm.generate(question, temperature=0.0),
                         contexts=[], blocked=[], used_context=False)
    retrieved = [c for c, _ in index.search(question, k=k)]
    if guardrail:
        safe, blocked = sanitize_chunks(retrieved)
    else:
        safe, blocked = retrieved, []
    prompt = build_augmented_prompt(question, safe)
    return RAGResult(answer=llm.generate(prompt, temperature=0.0),
                     contexts=safe, blocked=blocked, used_context=True)
