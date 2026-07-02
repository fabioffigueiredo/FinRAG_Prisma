"""Trilha de auditoria: cada consulta vira uma linha JSONL, sem PII e sem
armazenar a resposta em claro (apenas hash)."""
import hashlib
import json
import time
from pathlib import Path

AUDIT_PATH = Path(__file__).resolve().parents[2] / "data" / "audit" / "consultas.jsonl"


def registrar(*, rota: str, fundo: str, pergunta: str, backend: str,
              latency_ms: int, fontes: list, bloqueados: list,
              resposta: str, extra: dict | None = None) -> None:
    try:
        reg = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "rota": rota,
            "fundo": fundo,
            "pergunta": pergunta,
            "backend": backend,
            "latency_ms": latency_ms,
            "fontes": fontes,
            "bloqueados": bloqueados,
            "resposta_hash": hashlib.sha256((resposta or "").encode("utf-8")).hexdigest()[:16],
        }
        if extra:
            reg.update(extra)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
    except Exception:
        # auditoria nunca derruba a resposta (log-and-continue)
        pass


def ler(limit: int = 50) -> list[dict]:
    try:
        linhas = AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
    except (FileNotFoundError, OSError):
        return []
    out = []
    for ln in linhas[-limit:]:
        try:
            out.append(json.loads(ln))
        except json.JSONDecodeError:
            continue
    return out[::-1]
