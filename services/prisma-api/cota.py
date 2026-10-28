"""Cota de uso de IA por usuário autenticado.

Decidi separar a cota do rate limiter do slowapi porque notei que o limiter
conta por IP e vive em memória: protege login contra força bruta, mas não
impede um usuário logado de consumir sozinho o limite diário de tokens do
Groq (o plano gratuito tem teto de tokens por dia para a organização
inteira). Aqui a conta é por usuário: requisições por minuto em memória
(janela curta, perder no restart é aceitável) e tokens por dia no Postgres.
"""
from __future__ import annotations

import os
import threading
import time
from collections import deque
from datetime import date

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

import auth
from db.session import SessionLocal, get_db


def _rpm() -> int:
    return int(os.environ.get("PRISMA_COTA_RPM", "8"))


def _tokens_dia() -> int:
    return int(os.environ.get("PRISMA_COTA_TOKENS_DIA", "60000"))


_janelas: dict[int, deque] = {}
_lock = threading.Lock()


def _checar_rpm(usuario_id: int) -> None:
    agora = time.monotonic()
    with _lock:
        janela = _janelas.setdefault(usuario_id, deque())
        while janela and agora - janela[0] > 60:
            janela.popleft()
        if len(janela) >= _rpm():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Muitas perguntas em sequência. Aguarde um minuto e tente de novo.",
            )
        janela.append(agora)


def tokens_hoje(db: Session, usuario_id: int) -> int:
    from db.models import UsoIA
    valor = db.scalar(select(UsoIA.tokens).where(UsoIA.usuario_id == usuario_id, UsoIA.dia == date.today()))
    return int(valor or 0)


def somar_uso(db: Session, usuario_id: int, gestora_id: int, tokens: int) -> None:
    """Upsert atômico (INSERT … ON CONFLICT) — duas abas do mesmo usuário
    não perdem incremento uma da outra."""
    from db.models import UsoIA
    stmt = insert(UsoIA).values(usuario_id=usuario_id, gestora_id=gestora_id, dia=date.today(),
                                requisicoes=1, tokens=max(0, tokens))
    stmt = stmt.on_conflict_do_update(
        constraint="uq_uso_ia_usuario_dia",
        set_={"requisicoes": UsoIA.requisicoes + 1, "tokens": UsoIA.tokens + max(0, tokens)},
    )
    db.execute(stmt)
    db.commit()


def usuario_com_csrf(request: Request,
                     usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual)) -> auth.UsuarioAtual:
    """Sessão primeiro, CSRF depois. Decidi encadear assim porque notei que,
    com o CSRF no decorator da rota, quem estava SEM sessão levava 403
    ("recarregue a página") em vez de 401 ("entre de novo")."""
    # CSRF só existe contra credencial AMBIENTE (cookie, que o navegador
    # anexa sozinho). Cliente com Authorization: Bearer manda o token de
    # propósito e não tem cookie de CSRF — exigir o double-submit dele só
    # quebrava scripts como scripts/avaliar_rag.py.
    if request.cookies.get(auth.COOKIE_SESSAO):
        auth.verificar_csrf(request)
    return usuario


def usuario_ia(usuario: auth.UsuarioAtual = Depends(usuario_com_csrf),
               db: Session = Depends(get_db)) -> auth.UsuarioAtual:
    """Dependency das rotas que chamam LLM: sessão válida, CSRF e cota livre.

    O teto diário é aproximado: requisições simultâneas do mesmo usuário
    podem passar juntas e ultrapassar o saldo em poucas chamadas — o limite
    por minuto restringe esse excesso. Aceito porque o objetivo é impedir o
    esgotamento da cota da organização, não cobrar por token."""
    _checar_rpm(usuario.id)
    consumido = tokens_hoje(db, usuario.id)
    # Devolve a conexão ao pool AGORA: senão ela fica presa ("idle in
    # transaction") durante toda a chamada ao LLM, que pode levar 60 s+.
    db.close()
    if consumido >= _tokens_dia():
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Limite diário de uso da IA atingido para o seu usuário. Volta a liberar amanhã.",
        )
    return usuario


def registrar(usuario: auth.UsuarioAtual, tokens: int) -> None:
    """Contabiliza o consumo depois da resposta. Falha de banco não derruba a
    resposta já gerada (mesmo princípio da auditoria)."""
    try:
        with SessionLocal() as db:
            somar_uso(db, usuario.id, usuario.gestora_id, tokens)
    except Exception:  # noqa: BLE001
        pass
