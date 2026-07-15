"""Auth da Meta 4: hash de senha (bcrypt), JWT e RBAC por papel.

Decidi usar bcrypt puro (não passlib) porque notei que passlib vem
arrastando problemas de compatibilidade com bcrypt>=4.1 em vários projetos
recentes — bcrypt direto é mais simples e é o que a lib recomenda hoje.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Usuario

JWT_SECRET = os.environ.get("PRISMA_JWT_SECRET", "dev-secret-troque-em-producao")
JWT_ALGORITHM = "HS256"
JWT_EXPIRA_MINUTOS = 60 * 8  # 8h — turno de trabalho de um gestor

_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha.encode("utf-8"), senha_hash.encode("utf-8"))


def criar_token(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario.matricula,
        "nome": usuario.nome,
        "papel": usuario.papel.value,
        "gestora_id": usuario.gestora_id,
        "iat": agora,
        "exp": agora + timedelta(minutes=JWT_EXPIRA_MINUTOS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decodificar_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="token inválido ou expirado") from exc


def autenticar(db: Session, matricula: str, senha: str) -> Usuario | None:
    """Retorna o usuário se matrícula+senha baterem e a conta estiver ativa;
    None em qualquer outro caso — nunca revelo qual dos dois está errado
    (evita enumeração de matrícula válida)."""
    usuario = db.scalar(
        select(Usuario).where(Usuario.matricula == matricula, Usuario.ativo.is_(True))
    )
    if usuario is None or not verificar_senha(senha, usuario.senha_hash):
        return None
    return usuario


@dataclass(frozen=True)
class UsuarioAtual:
    """O que sobra do JWT depois de decodificado — é isso que as rotas
    protegidas recebem via `Depends(get_usuario_atual)`, nunca a senha."""
    matricula: str
    nome: str
    papel: str
    gestora_id: int


def get_usuario_atual(
    credenciais: "HTTPAuthorizationCredentials | None" = Depends(_bearer),
) -> UsuarioAtual:
    if credenciais is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="não autenticado — envie o header Authorization: Bearer <token>")
    payload = decodificar_token(credenciais.credentials)
    return UsuarioAtual(matricula=payload["sub"], nome=payload.get("nome", payload["sub"]),
                        papel=payload["papel"], gestora_id=payload["gestora_id"])


def exigir_papel(*papeis_permitidos: str):
    """Dependency factory de RBAC — `Depends(exigir_papel("gestor", "compliance"))`
    só deixa passar usuários com um desses papéis; qualquer outro leva 403."""
    def checar(usuario: UsuarioAtual = Depends(get_usuario_atual)) -> UsuarioAtual:
        if usuario.papel not in papeis_permitidos:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"papel '{usuario.papel}' não tem permissão — exige um de {list(papeis_permitidos)}",
            )
        return usuario
    return checar
