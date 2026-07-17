"""Trilha de auditoria: cada consulta vira um evento no Postgres (Meta 4);
cai pro JSONL local se o banco não estiver acessível — mesmo padrão de
degradação graciosa do resto do código (nunca derruba a resposta por causa
da auditoria). Sem PII e sem armazenar a resposta em claro (só hash).
"""
import hashlib
import json
import time
from pathlib import Path

AUDIT_PATH = Path(__file__).resolve().parents[2] / "data" / "audit" / "consultas.jsonl"

# Testes monkeypatcham isso pra True pra forçar o caminho de arquivo de
# forma determinística, sem depender de o Postgres de dev estar no ar ou
# não nesta máquina.
_FORCAR_ARQUIVO = False


def _registrar_no_banco(reg: dict) -> bool:
    try:
        from db.models import AuditoriaEvento
        from db.session import SessionLocal
        db = SessionLocal()
        try:
            db.add(AuditoriaEvento(
                rota=reg["rota"], fundo=reg["fundo"], pergunta=reg["pergunta"], backend=reg["backend"],
                latency_ms=reg["latency_ms"], fontes_json=json.dumps(reg["fontes"], ensure_ascii=False),
                bloqueados_json=json.dumps(reg["bloqueados"], ensure_ascii=False),
                resposta_hash=reg["resposta_hash"],
                extra_json=json.dumps(reg["extra"], ensure_ascii=False) if reg.get("extra") else None,
                ator_matricula=(reg.get("extra") or {}).get("ator_matricula"),
            ))
            db.commit()
            return True
        finally:
            db.close()
    except Exception:
        return False


def _ler_do_banco(limit: int, ator_matricula: "str | None" = None) -> "list[dict] | None":
    try:
        from sqlalchemy import select
        from db.models import AuditoriaEvento
        from db.session import SessionLocal
        db = SessionLocal()
        try:
            query = select(AuditoriaEvento).order_by(AuditoriaEvento.criado_em.desc()).limit(limit)
            if ator_matricula is not None:
                query = query.where(AuditoriaEvento.ator_matricula == ator_matricula)
            eventos = db.scalars(query)
            return [
                {
                    "timestamp": e.criado_em.isoformat(), "rota": e.rota, "fundo": e.fundo,
                    "pergunta": e.pergunta, "backend": e.backend, "latency_ms": e.latency_ms,
                    "fontes": json.loads(e.fontes_json), "bloqueados": json.loads(e.bloqueados_json),
                    "resposta_hash": e.resposta_hash,
                    **(json.loads(e.extra_json) if e.extra_json else {}),
                }
                for e in eventos
            ]
        finally:
            db.close()
    except Exception:
        return None


def registrar(*, rota: str, fundo: str, pergunta: str, backend: str,
              latency_ms: int, fontes: list, bloqueados: list,
              resposta: str, extra: dict | None = None) -> None:
    reg = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "rota": rota, "fundo": fundo, "pergunta": pergunta, "backend": backend,
        "latency_ms": latency_ms, "fontes": fontes, "bloqueados": bloqueados,
        "resposta_hash": hashlib.sha256((resposta or "").encode("utf-8")).hexdigest()[:16],
    }
    if extra:
        reg["extra"] = extra
    if not _FORCAR_ARQUIVO and _registrar_no_banco(reg):
        return
    try:
        reg_arquivo = {k: v for k, v in reg.items() if k != "extra"}
        if extra:
            reg_arquivo.update(extra)
        AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(reg_arquivo, ensure_ascii=False) + "\n")
    except Exception:
        pass  # auditoria nunca derruba a resposta (log-and-continue)


def ler(limit: int = 50, ator_matricula: "str | None" = None) -> list[dict]:
    if not _FORCAR_ARQUIVO:
        do_banco = _ler_do_banco(limit, ator_matricula=ator_matricula)
        if do_banco is not None:
            return do_banco
    try:
        linhas = AUDIT_PATH.read_text(encoding="utf-8").strip().splitlines()
    except (FileNotFoundError, OSError):
        return []
    out = []
    for ln in linhas[-limit:]:
        try:
            evento = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if ator_matricula is not None and evento.get("ator_matricula") != ator_matricula:
            continue
        out.append(evento)
    return out[::-1]


def registrar_evento(*, rota: str, ator_matricula: str, descricao: str,
                     extra: dict | None = None) -> None:
    """Sibling de `registrar()` pra eventos de auth/admin — sem fundo, sem
    backend LLM, sem citações. Reaproveita o mesmo armazenamento (Postgres
    com fallback JSONL); é isso que faz `historico_acessos` funcionar."""
    registrar(rota=rota, fundo="-", pergunta=descricao, backend="-",
              latency_ms=0, fontes=[], bloqueados=[], resposta="",
              extra={**(extra or {}), "ator_matricula": ator_matricula})
