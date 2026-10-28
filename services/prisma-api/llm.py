"""Seleção de backend de LLM para o Prisma.

Reusa GroqClient e MockLLM do núcleo FinRAG (sem reescrever) e adiciona um
OllamaClient (local/privado) via endpoint OpenAI-compatível do Ollama. Todos
respeitam o mesmo protocolo LLMClient.generate(prompt, *, temperature, max_tokens).
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
import requests

OLLAMA_BASE = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
# Modelo local capaz e já disponível na máquina do demo (Qwen3 8B).
OLLAMA_MODEL = os.environ.get("PRISMA_OLLAMA_MODEL", "qwen3:8b")

# Decidi trocar o default porque notei que o Groq desligou llama-3.3-70b e
# llama-3.1-8b nos planos free/developer em 16/08/2026 (console.groq.com/docs/deprecations)
# — a IA de produção caiu em modo demo sem nenhum erro visível por causa disso.
GROQ_API_BASE = "https://api.groq.com/openai/v1"
GROQ_MODEL_PADRAO = "openai/gpt-oss-120b"
GROQ_MODEL_LEVE_PADRAO = "openai/gpt-oss-20b"


def groq_model() -> str:
    return os.environ.get("PRISMA_GROQ_MODEL", GROQ_MODEL_PADRAO)


def groq_model_leve() -> str:
    return os.environ.get("PRISMA_GROQ_MODEL_LEVE", GROQ_MODEL_LEVE_PADRAO)


class MotorIndisponivel(RuntimeError):
    """O motor pedido não pode atender (sem chave, chave revogada, modelo
    retirado). Decidi levantar erro em vez de devolver MockLLM calado porque
    notei que o mock silencioso fazia a UI rotular texto enlatado como
    "gerado ao vivo"."""

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL)


def _to_ollama_messages(messages: list[dict]) -> list[dict]:
    """Traduz o formato genérico do agente (arguments como dict, tool_call_id
    presente) para o wire format do Ollama: sem 'type'/'id' no tool_call, sem
    'tool_call_id' na mensagem tool — o parser do Ollama espera arguments como
    objeto puro, não como string JSON (diferente do Groq/OpenAI)."""
    out = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            out.append({
                "role": "assistant",
                "content": m.get("content", ""),
                "tool_calls": [
                    {"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in m["tool_calls"]
                ],
            })
        elif m.get("role") == "tool":
            out.append({"role": "tool", "content": m.get("content", "")})
        else:
            out.append(m)
    return out


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

    def chat(self, messages: list[dict], tools: list[dict] | None = None,
             *, temperature: float = 0.0) -> dict:
        """Uma rodada de chat com tool-calling (Ollama /api/chat suporta `tools`).
        Retorna forma normalizada: {'content': str, 'tool_calls': [{id,name,arguments}]}."""
        body: dict = {
            "model": self.model,
            "think": False,
            "stream": False,
            "options": {"temperature": temperature},
            "messages": _to_ollama_messages(messages),
        }
        if tools:
            body["tools"] = tools
        resp = requests.post(f"{self.base}/api/chat", json=body, timeout=180)
        resp.raise_for_status()
        m = resp.json().get("message", {})
        calls = []
        for tc in m.get("tool_calls", []) or []:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args or "{}")
                except json.JSONDecodeError:
                    args = {}
            calls.append({"id": tc.get("id", ""), "name": fn.get("name", ""), "arguments": args})
        return {"content": _THINK_RE.sub("", m.get("content", "") or "").strip(), "tool_calls": calls}

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
        if not os.environ.get("GROQ_API_KEY"):
            raise MotorIndisponivel("GROQ_API_KEY não configurada")
        from finrag.models import GroqClient  # reuso do núcleo FinRAG
        return GroqClient(model=groq_model())
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


# ---------------------------------------------------------------------------
# Estado real do motor de nuvem (para o /health)
# ---------------------------------------------------------------------------
_GROQ_CHECK_TTL_S = 300
_groq_cache: dict = {"em": 0.0, "status": None}
_ultima_falha: dict = {}
_ultimo_sucesso: dict = {}
_lock_estado = threading.Lock()
# Uma falha real de geração mais nova que o último sucesso, dentro desta
# janela, vence o GET /models: chave válida com cota esgotada ou parâmetro
# recusado responde 200 no /models e mesmo assim não gera texto.
_JANELA_FALHA_S = 300


def registrar_sucesso(motor: str) -> None:
    with _lock_estado:
        _ultimo_sucesso[motor] = time.monotonic()


def registrar_falha(motor: str, erro: Exception) -> None:
    """Guarda a última falha real de geração — o /health mostra isso em vez
    de afirmar "disponível" só porque a variável de ambiente existe."""
    with _lock_estado:
        _ultima_falha[motor] = {"em": time.strftime("%Y-%m-%dT%H:%M:%S"), "_mono": time.monotonic(),
                                "tipo": type(erro).__name__, "detalhe": str(erro)[:160]}


def _checar_groq() -> dict:
    """Consulta GET /models/{modelo}: valida a chave (401) e se o modelo
    ainda existe para esta conta (404), sem gastar tokens."""
    chave = os.environ.get("GROQ_API_KEY")
    modelo = groq_model()
    if not chave:
        return {"estado": "indisponivel", "modelo": modelo, "motivo": "GROQ_API_KEY não configurada"}
    try:
        r = requests.get(f"{GROQ_API_BASE}/models/{modelo}",
                         headers={"Authorization": f"Bearer {chave}"}, timeout=5)
    except requests.RequestException as e:
        return {"estado": "degradado", "modelo": modelo, "motivo": f"sem resposta do Groq ({type(e).__name__})"}
    if r.status_code == 200:
        return {"estado": "disponivel", "modelo": modelo}
    motivos = {401: "chave Groq inválida ou revogada", 403: "chave sem permissão para o modelo",
               404: "modelo indisponível para esta conta"}
    return {"estado": "indisponivel", "modelo": modelo,
            "motivo": motivos.get(r.status_code, f"Groq respondeu HTTP {r.status_code}")}


def status_texto() -> dict:
    """Estado do motor de texto como o usuário vai experimentar (cache 5 min)."""
    agora = time.monotonic()
    with _lock_estado:
        vencido = _groq_cache["status"] is None or agora - _groq_cache["em"] > _GROQ_CHECK_TTL_S
    if vencido:  # rede fora do lock: um /health lento não trava os outros
        novo = _checar_groq()
        with _lock_estado:
            _groq_cache["status"], _groq_cache["em"] = novo, agora
    with _lock_estado:
        # pode ter sido invalidado por registrar_falha entre os dois locks
        groq = dict(_groq_cache["status"] or {"estado": "degradado", "modelo": groq_model(),
                                              "motivo": "verificação em andamento"})
        falha = dict(_ultima_falha.get("groq") or {})
        sucesso = _ultimo_sucesso.get("groq", 0.0)
    falha_recente = bool(falha) and falha["_mono"] > sucesso and agora - falha["_mono"] < _JANELA_FALHA_S
    if groq["estado"] == "disponivel" and falha_recente:
        groq = {**groq, "estado": "degradado",
                "motivo": f"última geração falhou ({falha['tipo']}); modelo responde no catálogo"}
    falha.pop("_mono", None)
    if groq["estado"] == "disponivel":
        out = {"estado": "disponivel", "motor": "groq", "modelo": groq["modelo"]}
    elif ollama_disponivel():
        out = {"estado": "disponivel", "motor": "ollama", "modelo": OLLAMA_MODEL,
               "motivo_nuvem": groq.get("motivo")}
    else:
        out = {"estado": "degradado", "motor": "demo", "motivo": groq.get("motivo")}
    if falha:
        out["ultima_falha"] = falha
    return out
