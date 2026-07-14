"""Pipeline RAG: recuperar -> sanear -> aumentar -> gerar.

Decidi montar o prompt aumentado à mão (Python puro) porque notei que o
enunciado valoriza demonstrar domínio do pipeline, não consumir uma chain pronta.
A flag use_context me deixa comparar resposta COM e SEM recuperação no notebook.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .corpus import Chunk
from .embeddings import SemanticIndex, bm25_search, hybrid_search
from .guardrails import detect_injection, sanitize_chunks
from .models import LLMClient

BLOCKED_QUESTION_ANSWER = (
    "Pergunta contém padrão suspeito de instrução; não processada."
)


@dataclass
class RAGResult:
    answer: str
    contexts: list[Chunk] = field(default_factory=list)
    blocked: list[Chunk] = field(default_factory=list)
    used_context: bool = True
    question_blocked: bool = False


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
           guardrail: bool = True, retrieval: str = "hybrid") -> RAGResult:
    """Executo o pipeline; sem contexto, gero direto (baseline para comparação).

    Decidi rodar o guardrail sobre a PERGUNTA antes de decidir use_context
    porque notei que um documento não é a única superfície de ataque: o
    próprio usuário pode digitar uma instrução maliciosa direto na pergunta,
    e o caminho use_context=False não passava por nenhuma sanitização.

    `retrieval` aceita "hybrid" (padrão, RRF semântico+BM25), "semantic" ou
    "lexical" — mantive as opções isoladas porque o notebook já compara os
    três lados a lado e eu não quero quebrar essa comparação.
    """
    if guardrail and detect_injection(question):
        return RAGResult(answer=BLOCKED_QUESTION_ANSWER, contexts=[],
                         blocked=[], used_context=use_context,
                         question_blocked=True)
    if not use_context:
        return RAGResult(answer=llm.generate(question, temperature=0.0),
                         contexts=[], blocked=[], used_context=False)
    if retrieval == "hybrid":
        retrieved = [c for c, _ in hybrid_search(question, index, index.chunks, k=k)]
    elif retrieval == "lexical":
        retrieved = [c for c, _ in bm25_search(question, index.chunks, k=k)]
    elif retrieval == "semantic":
        retrieved = [c for c, _ in index.search(question, k=k)]
    else:
        raise ValueError(f"retrieval desconhecido: {retrieval!r}")
    if guardrail:
        safe, blocked = sanitize_chunks(retrieved)
    else:
        safe, blocked = retrieved, []
    prompt = build_augmented_prompt(question, safe)
    return RAGResult(answer=llm.generate(prompt, temperature=0.0),
                     contexts=safe, blocked=blocked, used_context=True)
