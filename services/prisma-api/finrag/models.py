"""Camada de modelos do FinRAG.

Decidi unificar modelo remoto (Groq) e local (GPT4All) atrás de uma única
interface `LLMClient` porque notei que isso deixa o pipeline RAG agnóstico ao
backend: troco remoto<->local com uma linha e comparo os dois honestamente.
"""
from __future__ import annotations

import json
import os
from typing import Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Decidi expressar o contrato como Protocol porque notei que assim Groq, GPT4All e Mock ficam intercambiáveis sem herança."""

    def generate(self, prompt: str, *, temperature: float = 0.0,
                 max_tokens: int = 512) -> str:
        ...


class MockLLM:
    """Decidi criar uma classe Mock para testes porque notei que preciso de um fallback determinístico quando chave ou modelo não estão disponíveis."""

    def __init__(self, scripted: "str | list[str]" = "{}") -> None:
        self._scripted = [scripted] if isinstance(scripted, str) else list(scripted)
        self._i = 0

    def generate(self, prompt: str, *, temperature: float = 0.0,
                 max_tokens: int = 512) -> str:
        idx = min(self._i, len(self._scripted) - 1)
        self._i += 1
        return self._scripted[idx]


def _to_openai_messages(messages: list) -> list:
    """Traduz o formato genérico do agente (arguments como dict) para o wire
    format OpenAI/Groq: tool_calls precisa de 'type':'function' e arguments
    como STRING JSON (diferente do Ollama, que quer objeto puro)."""
    out = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content", ""),
                "tool_calls": [
                    {"id": tc["id"], "type": "function",
                     "function": {"name": tc["name"], "arguments": json.dumps(tc["arguments"], ensure_ascii=False)}}
                    for tc in m["tool_calls"]
                ],
            })
        else:
            out.append(m)
    return out


class GroqClient:
    """Decidi encapsular o Groq em uma classe porque notei que precisava de abstração para swapear com GPT4All sem quebrar o pipeline."""

    def __init__(self, model: str = "llama-3.1-8b-instant",
                 api_key: "str | None" = None) -> None:
        from groq import Groq
        self.model = model
        self._client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))

    def generate(self, prompt: str, *, temperature: float = 0.0,
                 max_tokens: int = 512) -> str:
        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""

    def chat(self, messages: list, tools: "list | None" = None,
             *, temperature: float = 0.0) -> dict:
        """Uma rodada de chat com tool-calling (Groq é OpenAI-compatível).
        Retorna forma normalizada: {'content': str, 'tool_calls': [{id,name,arguments}]}."""
        kwargs = dict(model=self.model, messages=_to_openai_messages(messages), temperature=temperature)
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"
        msg = self._client.chat.completions.create(**kwargs).choices[0].message
        calls = []
        for tc in (msg.tool_calls or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            calls.append({"id": tc.id, "name": tc.function.name, "arguments": args})
        return {"content": msg.content or "", "tool_calls": calls}


class GPT4AllClient:
    """Decidi oferecer a alternativa local porque notei que nem sempre há conexão à internet ou chave de API disponível."""

    def __init__(self, model_name: str = "Llama-3.2-3B-Instruct-Q4_0.gguf") -> None:
        from gpt4all import GPT4All
        self._model = GPT4All(model_name)

    def generate(self, prompt: str, *, temperature: float = 0.0,
                 max_tokens: int = 512) -> str:
        return self._model.generate(prompt, temp=temperature, max_tokens=max_tokens)


def get_llm(backend: str = "mock", **kwargs) -> LLMClient:
    """Fábrica de LLM. Decidi cair para MockLLM quando falta credencial/modelo
    porque notei que o professor precisa reproduzir o notebook sem chave."""
    if backend == "mock":
        return MockLLM(kwargs.get("scripted", "{}"))
    if backend == "groq":
        if not os.environ.get("GROQ_API_KEY") and not kwargs.get("api_key"):
            return MockLLM(kwargs.get("scripted", "{}"))
        return GroqClient(**{k: v for k, v in kwargs.items() if k != "scripted"})
    if backend == "local":
        return GPT4AllClient(**{k: v for k, v in kwargs.items() if k != "scripted"})
    raise ValueError(f"backend desconhecido: {backend}")
