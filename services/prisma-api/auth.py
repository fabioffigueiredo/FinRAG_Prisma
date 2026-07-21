"""Auth da Meta 4: hash de senha (bcrypt), JWT e RBAC por papel.

Decidi usar bcrypt puro (não passlib) porque notei que passlib vem
arrastando problemas de compatibilidade com bcrypt>=4.1 em vários projetos
recentes — bcrypt direto é mais simples e é o que a lib recomenda hoje.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import Usuario
from db.session import get_db

# PRISMA_ENV controla o fail-fast do secret e o flag `secure` dos cookies —
# nunca deixamos o fallback de dev valer silenciosamente em produção.
PRISMA_ENV = os.environ.get("PRISMA_ENV", "dev")
JWT_SECRET = os.environ.get("PRISMA_JWT_SECRET")
if not JWT_SECRET:
    if PRISMA_ENV == "production":
        raise RuntimeError(
            "PRISMA_JWT_SECRET não definido com PRISMA_ENV=production — "
            "defina a variável de ambiente antes de subir o serviço."
        )
    JWT_SECRET = "dev-secret-troque-em-producao"
JWT_ALGORITHM = "HS256"
JWT_EXPIRA_MINUTOS = 60 * 8  # 8h — turno de trabalho de um gestor

COOKIE_SESSAO = "prisma_session"
COOKIE_CSRF = "prisma_csrf"
COOKIE_PRE2FA = "prisma_pre2fa"
CSRF_HEADER = "x-csrf-token"
PRE2FA_EXPIRA_MINUTOS = 5

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


MAX_TENTATIVAS_FALHAS = 5
BLOQUEIO_MINUTOS = 15


def verificar_senha_com_lockout(usuario: Usuario, senha: "str | None") -> bool:
    """Confere a senha respeitando o mesmo lockout do login (MAX_TENTATIVAS_FALHAS
    erros seguidos bloqueiam por BLOQUEIO_MINUTOS) — qualquer rota que
    reverifica a senha de uma sessão já autenticada (step-up) deve usar
    isso em vez de `verificar_senha` puro, senão vira um oráculo de senha
    sem custo pra quem já tem o cookie de sessão (ver docs/SEGURANCA.md).

    Muta `usuario.tentativas_falhas`/`usuario.bloqueado_ate` — quem chama
    decide quando commitar (precisa commitar mesmo em falha, pra manter o
    contador)."""
    agora = datetime.now(timezone.utc)
    bloqueado_ate = usuario.bloqueado_ate
    if bloqueado_ate is not None and bloqueado_ate.tzinfo is None:
        bloqueado_ate = bloqueado_ate.replace(tzinfo=timezone.utc)
    if bloqueado_ate is not None and bloqueado_ate > agora:
        # conta bloqueada — nem checa a senha, mas devolve o mesmo False genérico
        return False

    if not senha or not verificar_senha(senha, usuario.senha_hash):
        usuario.tentativas_falhas += 1
        if usuario.tentativas_falhas >= MAX_TENTATIVAS_FALHAS:
            usuario.bloqueado_ate = agora + timedelta(minutes=BLOQUEIO_MINUTOS)
            usuario.tentativas_falhas = 0
        return False

    usuario.tentativas_falhas = 0
    usuario.bloqueado_ate = None
    return True


def autenticar(db: Session, matricula: str, senha: str, gestora_id: "int | None" = None) -> Usuario | None:
    """Retorna o usuário se matrícula(+gestora)+senha baterem e a conta
    estiver ativa; None em qualquer outro caso — nunca revelo qual está
    errado (evita enumeração de matrícula válida), e conta bloqueada usa a
    MESMA mensagem genérica (revelar o estado de bloqueio também é
    enumeração de conta — ver docs/SEGURANCA.md).

    Matrícula só é única DENTRO da gestora, não globalmente (achado #15 —
    ver plans/009-*.md). `gestora_id` desambigua quando informado (a tela
    de login sempre manda); se vier `None` (chamadores antigos, testes),
    cai pro caminho por matrícula só — funciona sem ambiguidade enquanto
    ninguém tiver a mesma matrícula em duas gestoras diferentes, e devolve
    None (nunca uma exceção) se a matrícula existir em mais de uma.

    Não commita — quem chama decide quando persistir (a rota de login
    precisa commitar mesmo em falha, pra manter o contador)."""
    filtros = [Usuario.matricula == matricula, Usuario.ativo.is_(True)]
    if gestora_id is not None:
        filtros.append(Usuario.gestora_id == gestora_id)
        usuario = db.scalar(select(Usuario).where(*filtros))
    else:
        candidatos = db.scalars(select(Usuario).where(*filtros)).all()
        usuario = candidatos[0] if len(candidatos) == 1 else None

    if usuario is None:
        return None

    if not verificar_senha_com_lockout(usuario, senha):
        return None

    return usuario


@dataclass(frozen=True)
class UsuarioAtual:
    """O que sobra do JWT depois de decodificado — é isso que as rotas
    protegidas recebem via `Depends(get_usuario_atual)`, nunca a senha.
    Campos novos vêm com default pra não quebrar as construções diretas já
    existentes em tests/test_auth.py e tests/test_e2e_meta4.py."""
    matricula: str
    nome: str
    papel: str
    gestora_id: int
    id: int = 0
    email: "str | None" = None
    avatar_url: "str | None" = None
    totp_ativado: bool = False
    trocar_senha_no_proximo_login: bool = False


def _cookie_kwargs() -> dict:
    """Atributos comuns aos 2 cookies de sessão. Sem `domain=` de propósito:
    cookie host-only é escopado por (Domain, Path) — nunca por porta — então
    o mesmo cookie setado por localhost:8000 já chega em requests para
    localhost:3100 em dev, e em produção API/web já dividem o mesmo domínio
    (wiki.ioi.ia.br/prisma + /prisma/api via Caddy). Nenhum proxy necessário."""
    return {
        "max_age": JWT_EXPIRA_MINUTOS * 60,
        "path": "/",
        "samesite": "lax",
        "secure": PRISMA_ENV == "production",
    }


def emitir_csrf_cookie(response: Response) -> str:
    """Gera e seta um novo token CSRF — precisa ser legível por JS
    (httponly=False), é isso que torna o double-submit possível."""
    token = secrets.token_urlsafe(32)
    response.set_cookie(COOKIE_CSRF, token, httponly=False, **_cookie_kwargs())
    return token


def emitir_cookies_sessao(response: Response, usuario: Usuario) -> None:
    """Chamar no login: seta o cookie de sessão (JWT, httpOnly) + renova o CSRF."""
    response.set_cookie(COOKIE_SESSAO, criar_token(usuario), httponly=True, **_cookie_kwargs())
    emitir_csrf_cookie(response)


def limpar_cookies_sessao(response: Response) -> None:
    """Chamar no logout."""
    response.delete_cookie(COOKIE_SESSAO, path="/")
    response.delete_cookie(COOKIE_CSRF, path="/")


def criar_token_pre2fa(usuario: Usuario) -> str:
    agora = datetime.now(timezone.utc)
    payload = {
        "sub": usuario.matricula,
        "gestora_id": usuario.gestora_id,
        "pre2fa": True,
        "iat": agora,
        "exp": agora + timedelta(minutes=PRE2FA_EXPIRA_MINUTOS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def emitir_cookie_pre2fa(response: Response, usuario: Usuario) -> None:
    """Emitido no login em vez da sessão real quando o usuário tem 2FA
    ativado. Cookie SEPARADO de prisma_session — é o nome diferente que
    garante que um token pendente de 2FA não abre nenhuma outra rota
    protegida (get_usuario_atual só olha COOKIE_SESSAO, nunca este)."""
    response.set_cookie(
        COOKIE_PRE2FA, criar_token_pre2fa(usuario), httponly=True,
        max_age=PRE2FA_EXPIRA_MINUTOS * 60, path="/", samesite="lax",
        secure=PRISMA_ENV == "production",
    )


def limpar_cookie_pre2fa(response: Response) -> None:
    response.delete_cookie(COOKIE_PRE2FA, path="/")


def obter_usuario_pre2fa(request: Request, db: Session) -> Usuario:
    """Lê e valida o cookie pre-2FA (claim `pre2fa: true`) — usado só pela
    2ª etapa do login (`/auth/2fa/verificar`). 401 genérico em qualquer
    falha, mesmo padrão de get_usuario_atual."""
    token = request.cookies.get(COOKIE_PRE2FA)
    if token is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="sessão de 2FA pendente não encontrada — faça login novamente")
    payload = decodificar_token(token)
    if not payload.get("pre2fa"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="sessão de 2FA pendente não encontrada — faça login novamente")
    usuario = db.scalar(select(Usuario).where(
        Usuario.matricula == payload["sub"],
        Usuario.gestora_id == payload.get("gestora_id"),
    ))
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="sessão de 2FA pendente não encontrada — faça login novamente")
    return usuario


def verificar_csrf(request: Request) -> None:
    """Double-submit cookie: o header X-CSRF-Token precisa bater com o cookie
    prisma_csrf. Um atacante cross-origin não lê o cookie (same-origin
    policy) nem consegue mandar o header customizado sem passar pelo CORS —
    que já não é mais `allow_origins=["*"]`."""
    cookie_token = request.cookies.get(COOKIE_CSRF)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token or cookie_token != header_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="CSRF token ausente ou inválido")


def get_usuario_atual(
    request: Request,
    credenciais: "HTTPAuthorizationCredentials | None" = Depends(_bearer),
    db: Session = Depends(get_db),
) -> UsuarioAtual:
    """Cookie de sessão primeiro (fluxo do navegador), Bearer header como
    fallback (mantém compatibilidade com qualquer chamador não-browser).

    Passa a consultar o banco (antes era só decode do JWT) — é o custo
    mínimo de dar revogação de sessão a um JWT hoje totalmente stateless:
    uma consulta indexada a mais por request autenticada, aceitável nessa
    escala. De brinde, cobre também o caso "admin desativou uma sessão já
    aberta" (usuario.ativo é checado abaixo)."""
    token = request.cookies.get(COOKIE_SESSAO)
    if token is None:
        if credenciais is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="não autenticado — envie o cookie de sessão ou o header Authorization: Bearer <token>")
        token = credenciais.credentials
    payload = decodificar_token(token)

    usuario = db.scalar(select(Usuario).where(
        Usuario.matricula == payload["sub"],
        Usuario.gestora_id == payload.get("gestora_id"),
    ))
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="não autenticado — envie o cookie de sessão ou o header Authorization: Bearer <token>")
    if usuario.sessao_revogada_em is not None:
        emitido_em = datetime.fromtimestamp(payload["iat"], tz=timezone.utc)
        revogado_em = usuario.sessao_revogada_em
        if revogado_em.tzinfo is None:
            revogado_em = revogado_em.replace(tzinfo=timezone.utc)
        if emitido_em < revogado_em:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="sessão revogada — faça login novamente")

    return UsuarioAtual(matricula=usuario.matricula, nome=usuario.nome, papel=usuario.papel.value,
                        gestora_id=usuario.gestora_id, id=usuario.id, email=usuario.email,
                        avatar_url=usuario.avatar_url, totp_ativado=usuario.totp_ativado,
                        trocar_senha_no_proximo_login=usuario.trocar_senha_no_proximo_login)


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
