"""Observability da Meta 4: logging estruturado (JSON) + estimativa de
custo por chamada de LLM.

Decidi estimar tokens por `len(texto) / 4` (heurística padrão pra
inglês/português) em vez de exigir que cada client (Groq/Ollama/Mock)
devolva contagem exata, porque notei que só o Groq expõe `usage` de forma
confiável — mudar a assinatura de todo client pra propagar tokens reais
seria um refactor arriscado no meio de um fluxo que já funciona. É uma
ESTIMATIVA, documentada como tal em todo lugar que aparece.
"""
from __future__ import annotations

import json
import logging
import sys
import time

_logger = logging.getLogger("prisma.observability")

# Preço estimado por 1M de tokens (USD) — só pra dar ordem de grandeza de
# custo, não é cobrança real. Local/mock são de graça (rodam na própria máquina).
_PRECO_POR_1M_TOKENS_USD = {
    "groq": {"entrada": 0.59, "saida": 0.79},   # ordem de grandeza do llama-3.3-70b
    "ollama": {"entrada": 0.0, "saida": 0.0},   # local, sem custo de API
    "mock": {"entrada": 0.0, "saida": 0.0},
    "demo": {"entrada": 0.0, "saida": 0.0},
}


class _FormatadorJSON(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "nivel": record.levelname,
            "logger": record.name,
            "mensagem": record.getMessage(),
        }
        campos_extra = getattr(record, "campos_extra", None)
        if campos_extra:
            base.update(campos_extra)
        return json.dumps(base, ensure_ascii=False)


def configurar_logging(nivel: int = logging.INFO) -> None:
    """Chamar uma vez no startup da API — troca o handler default por um
    que emite JSON (mais fácil de agregar/consultar do que texto livre)."""
    raiz = logging.getLogger()
    raiz.setLevel(nivel)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_FormatadorJSON())
    raiz.handlers = [handler]


def estimar_tokens(texto: str) -> int:
    """~4 caracteres por token — a mesma heurística de ordem de grandeza
    que a documentação da OpenAI/Anthropic usa pra estimativas rápidas."""
    return max(1, len(texto or "") // 4)


def estimar_custo_usd(backend: str, tokens_entrada: int, tokens_saida: int) -> float:
    precos = _PRECO_POR_1M_TOKENS_USD.get(backend.lower(), _PRECO_POR_1M_TOKENS_USD["mock"])
    custo = (tokens_entrada * precos["entrada"] + tokens_saida * precos["saida"]) / 1_000_000
    return round(custo, 6)


def registrar_chamada_llm(*, backend: str, modelo: str, prompt: str, resposta: str,
                          latency_ms: int, rota: str = "") -> dict:
    """Loga (JSON estruturado) uma chamada de LLM com tokens/custo
    estimados; devolve o mesmo dict pra quem chamar poder reaproveitar
    (ex.: anexar na auditoria) sem duplicar o cálculo."""
    tokens_entrada = estimar_tokens(prompt)
    tokens_saida = estimar_tokens(resposta)
    evento = {
        "evento": "chamada_llm", "rota": rota, "backend": backend, "modelo": modelo,
        "tokens_entrada_estimado": tokens_entrada, "tokens_saida_estimado": tokens_saida,
        "custo_usd_estimado": estimar_custo_usd(backend, tokens_entrada, tokens_saida),
        "latency_ms": latency_ms,
    }
    _logger.info("chamada_llm", extra={"campos_extra": evento})
    return evento
