"""Seleção de backend de LLM para o Prisma.

Reusa GroqClient e MockLLM do núcleo FinRAG (sem reescrever) e adiciona um
OllamaClient (local/privado) via endpoint OpenAI-compatível do Ollama. Todos
respeitam o mesmo protocolo LLMClient.generate(prompt, *, temperature, max_tokens).
"""
from __future__ import annotations

import os
import re
import requests

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
# Modelo local capaz e já disponível na máquina do demo (Qwen3 8B).
OLLAMA_MODEL = os.environ.get("PRISMA_OLLAMA_MODEL", "qwen3:8b")

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


class OllamaClient:
    """LLM local via Ollama (OpenAI-compatível). Privado/offline."""

    def __init__(self, model: str = OLLAMA_MODEL, base: str = OLLAMA_BASE) -> None:
        self.model = model
        self.base = base.rstrip("/")

    def generate(self, prompt: str, *, temperature: float = 0.0, max_tokens: int = 512) -> str:
        resp = requests.post(
            f"{self.base}/api/chat",
            json={
                "model": self.model,
                # desliga o "thinking" do Qwen3 p/ saída limpa e mais rápida na demo
                "think": False,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
                "messages": [{"role": "user", "content": prompt + " /no_think"}],
            },
            timeout=180,
        )
        resp.raise_for_status()
        conteudo = resp.json().get("message", {}).get("content", "")
        # remove qualquer bloco de raciocínio residual
        return _THINK_RE.sub("", conteudo).strip()

    def warmup(self) -> None:
        """Pré-aquece o modelo (evita cold-load na demo ao vivo)."""
        try:
            self.generate("ok", max_tokens=1)
        except Exception:
            pass


def get_backend(name: str):
    """Fábrica de backend. 'ollama' (local) | 'groq' (nuvem) | 'mock' (demo)."""
    name = (name or "ollama").lower()
    if name == "ollama":
        return OllamaClient()
    if name == "groq":
        from finrag.models import get_llm  # reuso do núcleo FinRAG
        # modelo de nuvem mais capaz p/ testers externos (cai em MockLLM sem chave)
        modelo = os.environ.get("PRISMA_GROQ_MODEL", "llama-3.3-70b-versatile")
        return get_llm("groq", model=modelo)
    if name in ("mock", "demo"):
        from finrag.models import MockLLM
        return MockLLM(
            "No período, o resultado do fundo foi sustentado principalmente pelo "
            "carrego das estratégias de Crédito Privado e Juros Brasil."
        )
    raise ValueError(f"backend desconhecido: {name}")


def ollama_disponivel() -> bool:
    try:
        requests.get(f"{OLLAMA_BASE}/api/version", timeout=2).raise_for_status()
        return True
    except Exception:
        return False
