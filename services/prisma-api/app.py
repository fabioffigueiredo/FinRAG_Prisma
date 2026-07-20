"""Prisma API — camada cognitiva sobre a atribuição de performance.

Envolve o núcleo FinRAG (retrieval + guardrail + prompt aumentado) e expõe:
  POST /narrativa   -> comentário do fundo em linguagem natural (grounded)
  POST /perguntar   -> Q&A RAG fundamentado, com citações e trechos bloqueados
  GET  /health      -> status + backends disponíveis

O pacote finrag (retrieval/guardrails) é vendorizado em ./finrag; adiciona
backend Ollama (local) e embeddings bge-m3.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path


def _load_env() -> None:
    """Carrega variáveis de .env (sem depender de python-dotenv) para a demo/VPS
    ficarem turnkey. Procura em: prisma-api/, raiz do prisma/ e raiz do PD1/.
    Só define chaves ainda não presentes no ambiente."""
    here = Path(__file__).resolve()
    candidatos = [
        here.parent / ".env",
        here.parents[2] / ".env",
        here.parents[3] / "PD1" / ".env",
    ]
    for env in candidatos:
        if not env.is_file():
            continue
        for linha in env.read_text(encoding="utf-8").splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("#") or "=" not in linha:
                continue
            chave, _, valor = linha.partition("=")
            chave = chave.strip()
            valor = valor.strip().strip('"').strip("'")
            if chave and chave not in os.environ:
                os.environ[chave] = valor


_load_env()

from fastapi import Depends, FastAPI, File, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from security_headers import SecurityHeadersMiddleware

HERE = Path(__file__).resolve()
PRISMA = HERE.parents[2]          # raiz do projeto prisma
CORPUS_DIR = PRISMA / "data" / "corpus"
SEED_DIR = PRISMA / "data" / "seed"
NOTICIAS_PATH = SEED_DIR / "noticias_alfa_classificadas.json"

from finrag.corpus import load_documents, chunk_corpus  # noqa: E402
from finrag.embeddings import SemanticIndex              # noqa: E402
from finrag.guardrails import sanitize_chunks            # noqa: E402
from finrag.rag import build_augmented_prompt            # noqa: E402

from llm import get_backend, ollama_disponivel, OllamaClient  # noqa: E402
from embed import get_embed_fn                                # noqa: E402
from escopo import (  # noqa: E402
    pede_recomendacao, tenta_injecao, INSTRUCAO_ESCOPO, RESPOSTA_ESCOPO, RESPOSTA_INJECAO,
)
import audit                                                             # noqa: E402
import agent as agente                                                   # noqa: E402
from radar import carregar_noticias, agregar                             # noqa: E402
from sinais import gerar_sinais, AVISO_LEGAL, MODELO_VERSAO              # noqa: E402
import auth                                                              # noqa: E402
from db.session import get_db                                           # noqa: E402
import observability                                                     # noqa: E402

app = FastAPI(title="Prisma API", version="0.1.0")

# Rate limiting (Meta 5) — backend em memória por padrão; produção
# multi-instância precisaria de storage_uri="redis://..." compartilhado
# (limitação de POC documentada em docs/SEGURANCA.md). Só registra o
# state/exception-handler aqui; o middleware entra depois do CORS abaixo.
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Allowlist explícita (nunca "*") — obrigatório para cookies credenciados:
# navegador rejeita Set-Cookie combinado com allow_origins wildcard.
_CORS_ORIGENS = [o.strip() for o in os.environ.get(
    "PRISMA_CORS_ORIGINS", "http://localhost:3100"
).split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGENS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Registrados depois do CORS de propósito — no Starlette o middleware
# registrado PRIMEIRO fica mais externo (envolve todo o resto), então o CORS
# continua sendo o mais externo da pilha (preflight OPTIONS nunca passa por
# rate-limit/headers de segurança antes do CORS resolver).
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Mount depois dos middlewares de propósito — CORS/headers de segurança
# também devem valer pros arquivos estáticos (avatares).
app.mount("/static", StaticFiles(directory=str(HERE.parent / "static")), name="static")

STATE: dict = {"index": None, "embed": "?", "fundos": None, "noticias": None}

NOMES_FUNDOS = {
    "alfa": "ALFA-33", "beta": "BETA-71", "gama": "GAMA-12",
    "delta": "DELTA-08", "epsilon": "EPSILON-45", "zeta": "ZETA-19", "theta": "THETA-52",
}


def e_comparativa(pergunta: str) -> list[str]:
    """Retorna os códigos de fundos a incluir no contexto de uma pergunta
    comparativa; lista vazia = usar apenas o fundo ativo."""
    q = (pergunta or "").lower()
    citados = [cod for nome, cod in NOMES_FUNDOS.items() if nome in q]
    if "compar" in q and len(citados) < 2:
        return list(NOMES_FUNDOS.values())
    return citados if len(citados) >= 2 else []


def _corpus_docs():
    """Carrega o corpus de regras (.md tratados como .txt pelo FinRAG loader)."""
    # o loader do FinRAG lê *.txt; espelhamos os .md como .txt em tempo de carga
    docs = []
    for md in sorted(CORPUS_DIR.glob("*.md")):
        from finrag.corpus import Document
        docs.append(Document(id=md.stem, text=md.read_text(encoding="utf-8"), source=md.name))
    from finrag.corpus import Document
    for n in carregar_noticias(NOTICIAS_PATH):
        docs.append(Document(
            id=f"noticia_{n['id']}",
            text=(f"Notícia ({n['data']}, estratégia {n['estrategia']}, "
                  f"sentimento {n['sentimento']}): {n['titulo']}. {n['corpo']}"),
            source=f"noticia:{n['id']}",
        ))
    return docs


@app.on_event("startup")
def _startup() -> None:
    observability.configurar_logging()
    import embed as _embed
    embed_fn = get_embed_fn()
    STATE["embed"] = f"{_embed.EMBED_MODEL} (Ollama)" if embed_fn else "sentence-transformers (fallback)"
    idx = SemanticIndex(embed_fn=embed_fn) if embed_fn else SemanticIndex()
    idx.build(chunk_corpus(_corpus_docs()))
    STATE["index"] = idx
    STATE["fundos"] = {}
    for fj in sorted(SEED_DIR.glob("fundo_*.json")):
        d = json.loads(fj.read_text(encoding="utf-8"))
        STATE["fundos"][d["fundo"]["codigo"]] = d
    STATE["noticias"] = carregar_noticias(NOTICIAS_PATH)
    if ollama_disponivel():
        OllamaClient().warmup()


class NarrativaReq(BaseModel):
    fundo: str = "ALFA-33"
    backend: str = "ollama"


class PerguntaReq(BaseModel):
    pergunta: str
    backend: str = "ollama"
    fundo: str = "ALFA-33"


class AnalisarReq(BaseModel):
    pergunta: str
    backend: str = "ollama"
    fundo: str = "ALFA-33"


class IngestReq(BaseModel):
    nome: str = "Export"
    csv: str
    benchmark_pp: float = 3.10


class LoginReq(BaseModel):
    matricula: str
    senha: str


class LoginResp(BaseModel):
    token: "str | None" = None
    nome: str
    papel: str
    gestora_id: int
    requer_2fa: bool = False


@app.get("/auth/csrf")
def obter_csrf(response: Response):
    """Bootstrap do cookie CSRF antes do login (resolve login-CSRF — a
    própria página de login chama isso ao montar, antes de existir sessão)."""
    return {"csrf_token": auth.emitir_csrf_cookie(response)}


@app.post("/auth/login", response_model=LoginResp, dependencies=[Depends(auth.verificar_csrf)])
def login(request: Request, req: LoginReq, response: Response, db=Depends(get_db)):
    """Fininho de propósito: `@limiter.limit` usa `functools.wraps`, e como
    este arquivo tem `from __future__ import annotations` (PEP 563), o
    FastAPI resolveria a anotação string "LoginReq" usando o `__globals__`
    do módulo `slowapi.extension` (onde a classe não existe) se o decorator
    fosse aplicado direto aqui — vira 422 tratando `req` como query param.
    Isolar a lógica de verdade numa função só do módulo Python evita que o
    FastAPI precise introspectar a versão decorada."""
    return _login_com_rate_limit(request, req, response, db)


@limiter.limit("5/minute")
def _login_com_rate_limit(request: Request, req: LoginReq, response: Response, db) -> LoginResp:
    from sqlalchemy import select as _select

    from db.models import Usuario as _Usuario
    usuario = auth.autenticar(db, req.matricula, req.senha)
    # Sempre commita — mesmo em falha — pra persistir o contador de
    # tentativas/bloqueio que `autenticar()` só marcou no objeto, sem commitar.
    db.commit()
    if usuario is None:
        alvo = db.scalar(_select(_Usuario).where(_Usuario.matricula == req.matricula))
        bloqueado = alvo is not None and alvo.bloqueado_ate is not None
        audit.registrar_evento(
            rota="/auth/login", ator_matricula=req.matricula,
            descricao="login falhou — conta bloqueada" if bloqueado else "login falhou",
            extra={"bloqueado": True} if bloqueado else None,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="matrícula ou senha inválidas")

    if usuario.papel.value in ("gestor", "compliance") and usuario.totp_ativado:
        # 2FA só é obrigatório pra gestor/compliance, e só depois de
        # matriculado (totp_ativado) — sem isso, primeiro login nunca
        # travaria antes de dar chance de configurar (ver Stage 16/ativar-2fa).
        # Cookie separado, sem token utilizável: é isso que torna a 2ª etapa
        # obrigatória de verdade, não só uma UX opcional.
        auth.emitir_cookie_pre2fa(response, usuario)
        audit.registrar_evento(rota="/auth/login", ator_matricula=usuario.matricula,
                               descricao="login etapa 1/2 — aguardando código 2FA")
        return LoginResp(nome=usuario.nome, papel=usuario.papel.value,
                         gestora_id=usuario.gestora_id, requer_2fa=True)

    auth.emitir_cookies_sessao(response, usuario)
    audit.registrar_evento(rota="/auth/login", ator_matricula=usuario.matricula, descricao="login bem-sucedido")
    return LoginResp(token=auth.criar_token(usuario), nome=usuario.nome,
                     papel=usuario.papel.value, gestora_id=usuario.gestora_id)


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    # Não exige sessão válida (get_usuario_atual dá 401 nesse caso) — logout
    # sem sessão continua sendo um no-op gracioso. Só tenta decodificar o
    # cookie/Bearer, sem lançar, pra saber quem saiu na auditoria.
    ator_matricula = None
    try:
        token = request.cookies.get(auth.COOKIE_SESSAO)
        if token:
            ator_matricula = auth.decodificar_token(token)["sub"]
    except HTTPException:
        pass
    auth.limpar_cookies_sessao(response)
    auth.limpar_cookie_pre2fa(response)
    if ator_matricula:
        audit.registrar_evento(rota="/auth/logout", ator_matricula=ator_matricula, descricao="logout")
    return {"ok": True}


@app.get("/auth/me")
def quem_sou_eu(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual)):
    return {"matricula": usuario.matricula, "nome": usuario.nome,
            "papel": usuario.papel, "gestora_id": usuario.gestora_id,
            "email": usuario.email, "avatar_url": usuario.avatar_url,
            "totp_ativado": usuario.totp_ativado,
            "trocar_senha_no_proximo_login": usuario.trocar_senha_no_proximo_login}


class TrocarSenhaReq(BaseModel):
    senha_atual: str
    senha_nova: str


@app.post("/auth/senha", dependencies=[Depends(auth.verificar_csrf)])
def trocar_senha_rota(req: TrocarSenhaReq, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                      db=Depends(get_db)):
    """Serve tanto a troca voluntária (Meu Perfil) quanto a obrigatória
    (temp senha/`trocar_senha_no_proximo_login`) — mesmo contrato, dois
    pontos de entrada no frontend."""
    from db.models import Usuario as _Usuario
    from senha_policy import validar_senha
    alvo = db.get(_Usuario, usuario.id)
    if alvo is None or not auth.verificar_senha(req.senha_atual, alvo.senha_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="senha atual incorreta")
    violacoes = validar_senha(req.senha_nova)
    if violacoes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"senha não atende à política: {', '.join(violacoes)}")
    alvo.senha_hash = auth.hash_senha(req.senha_nova)
    alvo.trocar_senha_no_proximo_login = False
    db.commit()
    audit.registrar_evento(rota="/auth/senha", ator_matricula=usuario.matricula, descricao="senha alterada")
    return {"ok": True}


AVATAR_MAX_BYTES = 2 * 1024 * 1024  # 2MB — cap de propósito, sem resize (POC)


def _detectar_extensao_imagem(cabecalho: bytes) -> str | None:
    """Confere magic bytes, não Content-Type (fácil de forjar) — sem
    dependência nova. Cobre só os 3 formatos que o upload aceita."""
    if cabecalho[:3] == b"\xff\xd8\xff":
        return "jpg"
    if cabecalho[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if cabecalho[:4] == b"RIFF" and cabecalho[8:12] == b"WEBP":
        return "webp"
    return None


@app.post("/auth/avatar", dependencies=[Depends(auth.verificar_csrf)])
async def upload_avatar(arquivo: UploadFile = File(...),
                        usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                        db=Depends(get_db)):
    """Sem resize/processamento — simplificação de POC, documentada em
    docs/SEGURANCA.md. Sobrescreve o arquivo anterior: 'trocar minha foto'
    deve substituir, não acumular."""
    import re

    from db.models import Usuario as _Usuario

    conteudo = await arquivo.read(AVATAR_MAX_BYTES + 1)
    if len(conteudo) > AVATAR_MAX_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail="imagem maior que 2MB")
    extensao = _detectar_extensao_imagem(conteudo[:12])
    if extensao is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="formato inválido — use JPEG, PNG ou WEBP")

    # Matrícula é definida pelo admin (não pelo próprio usuário), mas nunca
    # confiamos em texto externo dentro de um path — mantém só caracteres
    # seguros pra montar o nome do arquivo.
    matricula_segura = re.sub(r"[^A-Za-z0-9_-]", "_", usuario.matricula)
    diretorio = HERE.parent / "static" / "avatars"
    diretorio.mkdir(parents=True, exist_ok=True)
    for antigo in diretorio.glob(f"{matricula_segura}.*"):
        antigo.unlink()
    destino = diretorio / f"{matricula_segura}.{extensao}"
    destino.write_bytes(conteudo)

    alvo = db.get(_Usuario, usuario.id)
    alvo.avatar_url = f"/static/avatars/{matricula_segura}.{extensao}"
    db.commit()
    audit.registrar_evento(rota="/auth/avatar", ator_matricula=usuario.matricula,
                           descricao="avatar atualizado")
    return {"avatar_url": alvo.avatar_url}


class Iniciar2FAResp(BaseModel):
    otpauth_uri: str
    qr_base64: str


class Iniciar2FAReq(BaseModel):
    senha_atual: "str | None" = None


@app.post("/auth/2fa/iniciar", response_model=Iniciar2FAResp, dependencies=[Depends(auth.verificar_csrf)])
def iniciar_2fa(req: Iniciar2FAReq = Iniciar2FAReq(),
                usuario: auth.UsuarioAtual = Depends(auth.exigir_papel("gestor", "compliance")),
                db=Depends(get_db)):
    """Gera o segredo e devolve o QR — NÃO ativa ainda. Só
    /auth/2fa/confirmar ativa, depois de provar que o usuário configurou
    certo num app autenticador de verdade.

    Step-up: se já existe um 2FA ativo (troca de dispositivo self-service),
    exige a senha atual antes de sobrescrever o segredo — sem isso, um
    cookie de sessão roubado sozinho bastaria pra sequestrar o 2FA (ver
    docs/SEGURANCA.md). Primeiro enrollment (totp_ativado=False) não exige
    nada além do papel."""
    import base64
    import io

    import pyotp
    import qrcode

    from db.models import Usuario as _Usuario

    alvo = db.get(_Usuario, usuario.id)
    if alvo.totp_ativado:
        if not req.senha_atual or not auth.verificar_senha(req.senha_atual, alvo.senha_hash):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="senha atual incorreta")

    segredo = pyotp.random_base32()
    alvo.totp_secret = segredo
    alvo.totp_ativado = False
    db.commit()

    uri = pyotp.totp.TOTP(segredo).provisioning_uri(name=usuario.matricula, issuer_name="Prisma")
    imagem = qrcode.make(uri)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    audit.registrar_evento(rota="/auth/2fa/iniciar", ator_matricula=usuario.matricula,
                           descricao="2FA — enrollment iniciado")
    return Iniciar2FAResp(otpauth_uri=uri, qr_base64=qr_base64)


class Confirmar2FAReq(BaseModel):
    codigo: str


@app.post("/auth/2fa/confirmar", dependencies=[Depends(auth.verificar_csrf)])
def confirmar_2fa(req: Confirmar2FAReq,
                  usuario: auth.UsuarioAtual = Depends(auth.exigir_papel("gestor", "compliance")),
                  db=Depends(get_db)):
    import pyotp

    from db.models import Usuario as _Usuario
    alvo = db.get(_Usuario, usuario.id)
    if not alvo.totp_secret:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="nenhum enrollment de 2FA em andamento — chame /auth/2fa/iniciar primeiro")
    if not pyotp.TOTP(alvo.totp_secret).verify(req.codigo, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="código inválido")
    alvo.totp_ativado = True
    db.commit()
    audit.registrar_evento(rota="/auth/2fa/confirmar", ator_matricula=usuario.matricula,
                           descricao="2FA ativado")
    return {"ok": True}


class Verificar2FAReq(BaseModel):
    codigo: str


@app.post("/auth/2fa/verificar", response_model=LoginResp, dependencies=[Depends(auth.verificar_csrf)])
def verificar_2fa(request: Request, req: Verificar2FAReq, response: Response, db=Depends(get_db)):
    """Fininho, mesmo motivo do /auth/login (ver skill
    fastapi-slowapi-future-annotations): @limiter.limit direto numa rota
    registrada quebraria a resolução do Pydantic model `Verificar2FAReq`."""
    return _verificar_2fa_com_rate_limit(request, req, response, db)


@limiter.limit("5/minute")
def _verificar_2fa_com_rate_limit(request: Request, req: Verificar2FAReq, response: Response, db) -> LoginResp:
    """Um TOTP de 6 dígitos é alvo de força bruta se não limitado — rate
    limit próprio, separado do /auth/login."""
    import pyotp

    usuario = auth.obter_usuario_pre2fa(request, db)
    if not usuario.totp_secret or not pyotp.TOTP(usuario.totp_secret).verify(req.codigo, valid_window=1):
        audit.registrar_evento(rota="/auth/2fa/verificar", ator_matricula=usuario.matricula,
                               descricao="código 2FA inválido")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="código inválido")

    auth.limpar_cookie_pre2fa(response)
    auth.emitir_cookies_sessao(response, usuario)
    audit.registrar_evento(rota="/auth/2fa/verificar", ator_matricula=usuario.matricula,
                           descricao="login etapa 2/2 — 2FA confirmado")
    return LoginResp(token=auth.criar_token(usuario), nome=usuario.nome,
                     papel=usuario.papel.value, gestora_id=usuario.gestora_id)


PRISMA_DEMO_MATRICULA = os.environ.get("PRISMA_DEMO_MATRICULA", "DEMO-MS")


@app.post("/auth/login-microsoft-demo", response_model=LoginResp, dependencies=[Depends(auth.verificar_csrf)])
def login_microsoft_demo(request: Request, response: Response, db=Depends(get_db)):
    """Fininho, mesmo motivo das outras rotas com rate limit (ver skill
    fastapi-slowapi-future-annotations)."""
    return _login_microsoft_demo_com_rate_limit(request, response, db)


@limiter.limit("5/minute")
def _login_microsoft_demo_com_rate_limit(request: Request, response: Response, db) -> LoginResp:
    """NÃO é OAuth/OIDC real — não fala com Azure AD, não valida credencial
    nenhuma. Sempre loga a MESMA conta demo fixa (get-or-create idempotente),
    só pra mostrar o botão "Entrar com Microsoft" na demo. papel=ANALISTA de
    propósito: mantém o clique único simples e nunca aciona 2FA."""
    import secrets as _secrets

    from sqlalchemy import select as _select

    from db.models import Gestora as _Gestora
    from db.models import Papel as _Papel
    from db.models import Usuario as _Usuario
    from db.repo import criar_usuario as _criar_usuario

    usuario = db.scalar(_select(_Usuario).where(_Usuario.matricula == PRISMA_DEMO_MATRICULA))
    if usuario is None:
        gestora = db.scalar(_select(_Gestora).order_by(_Gestora.id).limit(1))
        if gestora is None:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                                detail="nenhuma gestora cadastrada — não é possível criar a conta demo")
        senha_inutilizavel = auth.hash_senha(_secrets.token_urlsafe(32))
        usuario = _criar_usuario(db, gestora_id=gestora.id, matricula=PRISMA_DEMO_MATRICULA,
                                 nome="Conta Demo Microsoft", senha_hash=senha_inutilizavel,
                                 papel=_Papel.ANALISTA)
        db.commit()
    elif not usuario.ativo:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="conta demo desativada")

    auth.emitir_cookies_sessao(response, usuario)
    audit.registrar_evento(rota="/auth/login-microsoft-demo", ator_matricula=usuario.matricula,
                           descricao="login via Microsoft (simulação de demo)")
    return LoginResp(token=auth.criar_token(usuario), nome=usuario.nome,
                     papel=usuario.papel.value, gestora_id=usuario.gestora_id)


# --- Cadastro / convite / ativação de conta ---------------------------------
#
# Nunca envia senha por e-mail (temporária ou não) — padrão de mercado (OWASP
# Forgot-Password Cheat Sheet): um token de uso único, expiração curta,
# embutido num link; o usuário define a própria senha ao abrir o link. Dois
# fluxos convergem no mesmo `convite_token`/`ativar-conta`:
#   1. autocadastro público (`/auth/cadastro`) + aprovação de um gestor;
#   2. convite direto do gestor (`/usuarios/convite`), sem etapa de aprovação.

PRISMA_WEB_URL = os.environ.get("PRISMA_WEB_URL", "http://localhost:3100")


def _link_ativacao(token: str) -> str:
    return f"{PRISMA_WEB_URL}/ativar-conta/{token}"


class CadastroReq(BaseModel):
    matricula: str
    nome: str
    email: str
    telefone: "str | None" = None


@app.post("/auth/cadastro", status_code=status.HTTP_201_CREATED, dependencies=[Depends(auth.verificar_csrf)])
def solicitar_cadastro(request: Request, req: CadastroReq, db=Depends(get_db)):
    """Fininho, mesmo motivo das outras rotas com rate limit (ver skill
    fastapi-slowapi-future-annotations)."""
    return _solicitar_cadastro_com_rate_limit(request, req, db)


@limiter.limit("5/minute")
def _solicitar_cadastro_com_rate_limit(request: Request, req: CadastroReq, db):
    """Rota pública — sempre cria `papel=analista` (decisão de produto: o
    formulário nem pergunta o papel; um gestor eleva na aprovação se quiser).
    `ativo=False` até aprovação — mesmo em teoria não daria pra logar sem
    senha utilizável, mas fica explícito."""
    import secrets as _secrets
    from sqlalchemy import select as _select
    from sqlalchemy.exc import IntegrityError

    from db.models import Gestora as _Gestora
    from db.models import Papel as _Papel
    from db.models import StatusCadastro as _StatusCadastro
    from db.models import Usuario as _Usuario

    gestora = db.scalar(_select(_Gestora).order_by(_Gestora.id).limit(1))
    if gestora is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="nenhuma gestora cadastrada — não é possível processar o cadastro")

    senha_inutilizavel = auth.hash_senha(_secrets.token_urlsafe(32))
    novo = _Usuario(matricula=req.matricula, nome=req.nome, senha_hash=senha_inutilizavel,
                    papel=_Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                    email=req.email, telefone=req.telefone, status_cadastro=_StatusCadastro.PENDENTE)
    db.add(novo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="matrícula já cadastrada")

    audit.registrar_evento(rota="/auth/cadastro", ator_matricula=req.matricula,
                           descricao="autocadastro solicitado — aguardando aprovação")
    return {"ok": True}


class ConviteValidoResp(BaseModel):
    nome: str
    matricula: str


@app.get("/auth/convite/{token}", response_model=ConviteValidoResp)
def validar_convite_rota(token: str, db=Depends(get_db)):
    """Pública de propósito (o usuário ainda não tem sessão) — só devolve o
    mínimo pra saudação da tela (nome/matrícula), nunca papel/e-mail/etc."""
    from datetime import timezone as _timezone
    from sqlalchemy import select as _select

    from db.models import Usuario as _Usuario

    alvo = db.scalar(_select(_Usuario).where(_Usuario.convite_token == token))
    if alvo is None or alvo.convite_expira_em is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link inválido ou já utilizado")
    expira_em = alvo.convite_expira_em
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=_timezone.utc)
    if expira_em < datetime.now(_timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="link expirado — peça um novo convite")
    return ConviteValidoResp(nome=alvo.nome, matricula=alvo.matricula)


class AtivarContaReq(BaseModel):
    token: str
    nova_senha: str


@app.post("/auth/ativar-conta", response_model=LoginResp, dependencies=[Depends(auth.verificar_csrf)])
def ativar_conta_rota(request: Request, req: AtivarContaReq, response: Response, db=Depends(get_db)):
    """Fininho, mesmo motivo das outras rotas com rate limit (ver skill
    fastapi-slowapi-future-annotations)."""
    return _ativar_conta_com_rate_limit(request, req, response, db)


@limiter.limit("5/minute")
def _ativar_conta_com_rate_limit(request: Request, req: AtivarContaReq, response: Response, db) -> LoginResp:
    """Valida o token (existe, não expirado — token é sempre de uso único:
    consumido/limpo aqui mesmo em caso de novo pedido de troca de senha
    futuro), seta a senha escolhida pelo usuário e já emite sessão — cai
    direto no mesmo fluxo pós-login normal (inclusive `/ativar-2fa` se o
    papel exigir)."""
    from datetime import timezone as _timezone
    from sqlalchemy import select as _select

    from db.models import Usuario as _Usuario
    from senha_policy import validar_senha

    alvo = db.scalar(_select(_Usuario).where(_Usuario.convite_token == req.token))
    if alvo is None or alvo.convite_expira_em is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="link inválido ou já utilizado")
    expira_em = alvo.convite_expira_em
    if expira_em.tzinfo is None:
        expira_em = expira_em.replace(tzinfo=_timezone.utc)
    if expira_em < datetime.now(_timezone.utc):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="link expirado — peça um novo convite")

    violacoes = validar_senha(req.nova_senha)
    if violacoes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"senha não atende à política: {', '.join(violacoes)}")

    alvo.senha_hash = auth.hash_senha(req.nova_senha)
    alvo.trocar_senha_no_proximo_login = False
    alvo.ativo = True
    alvo.convite_token = None
    alvo.convite_expira_em = None
    db.commit()

    auth.emitir_cookies_sessao(response, alvo)
    audit.registrar_evento(rota="/auth/ativar-conta", ator_matricula=alvo.matricula, descricao="conta ativada")
    return LoginResp(token=auth.criar_token(alvo), nome=alvo.nome, papel=alvo.papel.value,
                     gestora_id=alvo.gestora_id)


def _parse_csv_contribuicoes(texto: str) -> list[dict]:
    """Parseia CSV de contribuições: estrategia,contribuicao_pp[,peso_medio]."""
    import csv
    import io

    linhas = []
    reader = csv.DictReader(io.StringIO(texto.strip()))
    cores = ["gold", "blue", "green", "neutral", "violet", "amber", "red"]
    for i, row in enumerate(reader):
        nome = (row.get("estrategia") or row.get("Estrategia") or "").strip()
        if not nome:
            continue
        try:
            contrib = float((row.get("contribuicao_pp") or "0").replace(",", "."))
        except ValueError:
            continue
        try:
            peso = float((row.get("peso_medio") or "0").replace(",", "."))
        except ValueError:
            peso = 0.0
        cor = "red" if contrib < 0 else cores[i % len(cores)]
        linhas.append({"nome": nome, "contribuicao_pp": round(contrib, 2), "peso_medio": peso, "cor": cor})
    return linhas


def _resumo_texto(f: dict) -> str:
    r = f["resumo"]
    estr = "; ".join(f"{e['nome']} {e['contribuicao_pp']:+.2f}pp" for e in f["estrategias"])
    return (
        f"Fundo: {f['fundo']['nome']} ({f['fundo']['classe']}). "
        f"Período: {f['fundo']['periodo']}. Benchmark: {f['fundo']['benchmark']}.\n"
        f"Retorno da cota: {r['retorno_cota']:.2f}%; benchmark: {r['retorno_bench']:.2f}%; "
        f"excesso: {r['excesso_pp']:+.2f}pp ({r['pct_cdi']:.0f}% do {f['fundo']['benchmark']}). "
        f"Beta: {r['beta']}; Alpha: {r['alpha_pp']:+.2f}pp.\n"
        f"Contribuição por estratégia: {estr}."
    )


def _fund_chunk(f: dict):
    from finrag.corpus import Chunk
    cod = f["fundo"]["codigo"]
    return Chunk(doc_id=f"dados_{cod}", chunk_id=0, text=_resumo_texto(f), source=f"dados:{cod}")


def _gerar_seguro(backend: str, prompt: str, rota: str = "", **kw) -> tuple[str, bool]:
    """Gera texto; se o backend falhar (ex.: Ollama ausente na VPS, timeout de
    nuvem), degrada para o MockLLM e sinaliza. Nunca deixa a demo cair.

    Meta 4: registra a chamada em observability (tokens/custo estimados,
    latência) — é o único ponto de saída de texto pro /narrativa e
    /perguntar, então é o lugar certo pra medir sem duplicar em cada rota.
    """
    t0 = time.perf_counter()
    try:
        texto = get_backend(backend).generate(prompt, **kw).strip()
        degradado = False
    except Exception:
        from finrag.models import MockLLM
        texto = MockLLM(
            "No período, o resultado do fundo foi sustentado principalmente pelo "
            "carrego das estratégias de crédito privado e juros."
        ).generate(prompt).strip()
        degradado = True
    latency_ms = int((time.perf_counter() - t0) * 1000)
    observability.registrar_chamada_llm(
        backend=("mock" if degradado else backend), modelo=backend, prompt=prompt,
        resposta=texto, latency_ms=latency_ms, rota=rota,
    )
    return texto, degradado


@app.get("/health")
def health():
    return {
        "status": "ok",
        "embed": STATE["embed"],
        "ollama": ollama_disponivel(),
        "chunks": len(STATE["index"]._chunks) if STATE["index"] else 0,
    }


@app.post("/narrativa")
def narrativa(req: NarrativaReq):
    t0 = time.perf_counter()
    fundos = STATE.get("fundos") or {}
    f = fundos.get(req.fundo) or (next(iter(fundos.values())) if fundos else None)
    if f is None:
        return {"texto": "", "citacoes": [], "backend": req.backend,
                "latency_ms": 0, "erro": "nenhum fundo carregado"}
    idx = STATE["index"]
    retr = idx.search("atribuição contribuição estratégia alpha beta carrego benchmark", k=3)
    regras = "\n".join(f"[{c.source}] {c.text[:280]}" for c, _ in retr)
    prompt = (
        "Você é um analista de performance de fundos. Escreva UM parágrafo objetivo, "
        "em português, explicando o resultado do fundo no período. Baseie-se SOMENTE nos "
        "números e nas regras abaixo; não invente dados. Foque em de onde veio o retorno.\n\n"
        f"NÚMEROS DO FUNDO:\n{_resumo_texto(f)}\n\n"
        f"REGRAS DE ATRIBUIÇÃO (contexto):\n{regras}" + INSTRUCAO_ESCOPO + "\n\nComentário:"
    )
    texto, degradado = _gerar_seguro(req.backend, prompt, rota="/narrativa", temperature=0.1, max_tokens=220)
    lat = int((time.perf_counter() - t0) * 1000)
    fontes = [c.source for c, _ in retr]
    audit.registrar(rota="/narrativa", fundo=f["fundo"]["codigo"], pergunta="(narrativa do período)",
                    backend=req.backend, latency_ms=lat, fontes=fontes, bloqueados=[],
                    resposta=texto)
    return {
        "texto": texto,
        "citacoes": [{"fonte": c.source, "trecho": c.text[:160].strip(), "score": round(float(s), 3)} for c, s in retr],
        "backend": req.backend,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/perguntar")
def perguntar(req: PerguntaReq):
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={"injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={"escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    idx = STATE["index"]
    codigos = e_comparativa(req.pergunta) or [req.fundo]
    fund_chunks = [_fund_chunk(STATE["fundos"][c]) for c in codigos if c in STATE["fundos"]]

    retr = idx.search(req.pergunta, k=4)
    scores = {id(c): s for c, s in retr}
    safe, blocked = sanitize_chunks([c for c, _ in retr])
    contexto = fund_chunks + safe
    prompt = build_augmented_prompt(req.pergunta, contexto) + INSTRUCAO_ESCOPO
    resposta, _deg = _gerar_seguro(req.backend, prompt, rota="/perguntar", temperature=0.1, max_tokens=380)
    lat = int((time.perf_counter() - t0) * 1000)
    citacoes = [
        {"fonte": c.source, "trecho": c.text[:160].strip(),
         "score": round(float(scores.get(id(c), 0)), 3)}
        for c in contexto
    ]
    audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[c["fonte"] for c in citacoes],
                    bloqueados=[c.source for c in blocked], resposta=resposta)
    return {
        "resposta": resposta,
        "citacoes": citacoes,
        "bloqueados": [{"fonte": c.source, "motivo": "prompt injection detectado pelo guardrail"} for c in blocked],
        "backend": req.backend,
        "latency_ms": lat,
    }


@app.post("/analisar")
def analisar_endpoint(req: AnalisarReq):
    """Copiloto de análise conversacional: traduz a pergunta em chamadas de
    ferramenta sobre os dados do fundo (POC sobre o seed) e devolve narrativa +
    gráfico(s) + chips de ação. Mesmos guardrails do /perguntar."""
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={"injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={"escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    fundos = STATE.get("fundos") or {}
    noticias = STATE.get("noticias") or []
    degradado = False
    try:
        cliente = get_backend(req.backend)
        if hasattr(cliente, "chat"):
            resultado = agente.analisar(pergunta=req.pergunta, fundo_ativo=req.fundo,
                                        backend=cliente, fundos=fundos, noticias=noticias)
        else:
            resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos,
                                             noticias=noticias, pergunta=req.pergunta)
            degradado = True
    except Exception:
        resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos,
                                         noticias=noticias, pergunta=req.pergunta)
        degradado = True

    lat = int((time.perf_counter() - t0) * 1000)
    audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[t["tool"] for t in resultado.get("tool_trace", [])],
                    bloqueados=[], resposta=resultado["resposta"],
                    extra={"consulta_echo": resultado.get("consulta_echo"),
                           "tool_trace": resultado.get("tool_trace"),
                           "degradado": degradado})
    return {
        "resposta": resultado["resposta"],
        "consulta_echo": resultado.get("consulta_echo", {}),
        "blocos": resultado.get("blocos", []),
        "acoes": resultado.get("acoes", []),
        "avisos": resultado.get("avisos", []),
        "citacoes": [],
        "bloqueados": [],
        "backend": req.backend,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/ingerir")
def ingerir(req: IngestReq):
    """Modo standalone: ingere um export (CSV) de contribuições e devolve o resumo.
    Prova o adaptador de arquivo — mesma leitura sem backend ao vivo."""
    estrategias = _parse_csv_contribuicoes(req.csv)
    if not estrategias:
        return {"ok": False, "erro": "CSV sem colunas reconhecidas (estrategia, contribuicao_pp)."}
    retorno = round(sum(e["contribuicao_pp"] for e in estrategias), 2)
    bench = round(req.benchmark_pp, 2)
    return {
        "ok": True,
        "fundo": {"nome": req.nome, "benchmark": "CDI", "periodo": "importado do arquivo"},
        "resumo": {
            "retorno_cota": retorno,
            "retorno_bench": bench,
            "excesso_pp": round(retorno - bench, 2),
            "pct_cdi": round(retorno / bench * 100, 1) if bench else 0.0,
        },
        "estrategias": estrategias,
        "n_estrategias": len(estrategias),
    }


@app.get("/radar")
def radar_endpoint():
    noticias = STATE.get("noticias") or []
    if not noticias:
        return {"ok": False, "noticias": [], "agregado": {}, "degradado": True}
    degradado = not any(n.get("fonte") == "rss" for n in noticias)
    return {"ok": True, "noticias": noticias, "agregado": agregar(noticias), "degradado": degradado}


@app.get("/sinais")
def sinais_endpoint(fundo: str = "ALFA-33"):
    """Alertas probabilísticos de apoio à decisão (modelo de regras auditável)."""
    fundos = STATE.get("fundos") or {}
    f = fundos.get(fundo) or (next(iter(fundos.values())) if fundos else None)
    noticias = STATE.get("noticias") or []
    if not f or not noticias:
        return {"ok": False, "sinais": [], "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}
    sinais = gerar_sinais(f, agregar(noticias), noticias)
    return {"ok": True, "sinais": sinais, "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}


@app.get("/auditoria", dependencies=[Depends(auth.exigir_papel("gestor", "compliance"))])
def auditoria(limit: int = 50):
    """RBAC reativado — o frontend já tem login de verdade (cookie de
    sessão + middleware/admin gate). Só gestor/compliance auditam."""
    return {"ok": True, "consultas": audit.ler(limit=limit)}


@app.get("/fundos")
def listar_fundos(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    """Isolamento multi-tenant: cada gestora só vê os próprios fundos —
    ver `db/repo.py::listar_fundos_da_gestora`."""
    from db.repo import listar_fundos_da_gestora
    fundos = listar_fundos_da_gestora(db, usuario.gestora_id)
    return {"ok": True, "fundos": [
        {"codigo": f.codigo, "nome": f.nome, "classe": f.classe, "benchmark": f.benchmark_padrao}
        for f in fundos
    ]}


class UsuarioResp(BaseModel):
    id: int
    matricula: str
    nome: str
    papel: str
    gestora_id: int
    gestora_nome: str
    ativo: bool
    email: "str | None" = None
    telefone: "str | None" = None
    avatar_url: "str | None" = None
    totp_ativado: bool = False
    trocar_senha_no_proximo_login: bool = False
    bloqueado_ate: "datetime | None" = None
    tentativas_falhas: int = 0


class CriarUsuarioReq(BaseModel):
    matricula: str
    nome: str
    papel: str
    senha: str
    trocar_senha_no_proximo_login: bool = False
    email: "str | None" = None
    telefone: "str | None" = None


class AtualizarUsuarioReq(BaseModel):
    """Update parcial — `matricula` e `gestora_id` de propósito não existem
    aqui: são imutáveis por essa rota (ver Stage 3 do plano)."""
    nome: str | None = None
    papel: str | None = None
    ativo: bool | None = None
    senha: str | None = None
    trocar_senha_no_proximo_login: bool | None = None
    email: "str | None" = None
    telefone: "str | None" = None


def _usuario_resp(u) -> UsuarioResp:
    return UsuarioResp(id=u.id, matricula=u.matricula, nome=u.nome,
                       papel=u.papel.value, gestora_id=u.gestora_id,
                       gestora_nome=u.gestora.nome, ativo=u.ativo,
                       email=u.email, telefone=u.telefone, avatar_url=u.avatar_url,
                       totp_ativado=u.totp_ativado,
                       trocar_senha_no_proximo_login=u.trocar_senha_no_proximo_login,
                       bloqueado_ate=u.bloqueado_ate, tentativas_falhas=u.tentativas_falhas)


@app.get("/usuarios", dependencies=[Depends(auth.exigir_papel("gestor", "compliance"))])
def listar_usuarios(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    """Só gestor/compliance administram usuários — nunca serializa
    `senha_hash` (ver `_usuario_resp`)."""
    from db.repo import listar_usuarios_da_gestora
    usuarios = listar_usuarios_da_gestora(db, usuario.gestora_id)
    return {"ok": True, "usuarios": [_usuario_resp(u) for u in usuarios]}


@app.post("/usuarios", status_code=status.HTTP_201_CREATED,
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def criar_usuario_rota(req: CriarUsuarioReq, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                       db=Depends(get_db)):
    """`gestora_id` NUNCA vem do payload — sempre o da gestora de quem está
    logado, senão um gestor mal-intencionado (ou um bug de cliente) poderia
    criar usuário em outro tenant."""
    from sqlalchemy.exc import IntegrityError

    from db.models import Papel
    from db.repo import criar_usuario
    from senha_policy import validar_senha
    try:
        papel = Papel(req.papel)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"papel inválido — use um de {[p.value for p in Papel]}")
    violacoes = validar_senha(req.senha)
    if violacoes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"senha não atende à política: {', '.join(violacoes)}")
    try:
        novo = criar_usuario(db, gestora_id=usuario.gestora_id, matricula=req.matricula,
                             nome=req.nome, senha_hash=auth.hash_senha(req.senha), papel=papel,
                             trocar_senha_no_proximo_login=req.trocar_senha_no_proximo_login,
                             email=req.email, telefone=req.telefone)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="matrícula já cadastrada")
    audit.registrar_evento(rota="/usuarios", ator_matricula=usuario.matricula,
                           descricao=f"usuário criado: {novo.matricula}")
    return _usuario_resp(novo)


class PendenteResp(BaseModel):
    id: int
    matricula: str
    nome: str
    email: "str | None" = None
    telefone: "str | None" = None


@app.get("/usuarios/pendentes", dependencies=[Depends(auth.exigir_papel("gestor", "compliance"))])
def listar_pendentes_rota(usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    from sqlalchemy import select as _select

    from db.models import StatusCadastro as _StatusCadastro
    from db.models import Usuario as _Usuario
    pendentes = db.scalars(
        _select(_Usuario).where(_Usuario.gestora_id == usuario.gestora_id,
                                _Usuario.status_cadastro == _StatusCadastro.PENDENTE)
        .order_by(_Usuario.nome)
    )
    return {"ok": True, "usuarios": [
        PendenteResp(id=p.id, matricula=p.matricula, nome=p.nome, email=p.email, telefone=p.telefone)
        for p in pendentes
    ]}


class AprovarReq(BaseModel):
    papel: "str | None" = None


class AprovarResp(BaseModel):
    ok: bool = True
    link_ativacao: str
    email_enviado: bool


@app.post("/usuarios/{usuario_id}/aprovar", response_model=AprovarResp,
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def aprovar_cadastro_rota(usuario_id: int, req: AprovarReq = AprovarReq(),
                          usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    """Gera o token de ativação + dispara o e-mail — SEMPRE devolve o link
    também na resposta (rede de segurança se o e-mail falhar/não estiver
    configurado; não é o caminho principal)."""
    from datetime import timedelta, timezone as _timezone

    import convite as _convite

    from db.models import Papel as _Papel
    from db.models import StatusCadastro as _StatusCadastro
    from db.repo import buscar_usuario_por_id

    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    if alvo.status_cadastro != _StatusCadastro.PENDENTE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cadastro não está pendente")

    if req.papel is not None:
        try:
            alvo.papel = _Papel(req.papel)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"papel inválido — use um de {[p.value for p in _Papel]}")

    token = _convite.gerar_token()
    alvo.convite_token = token
    alvo.convite_expira_em = datetime.now(_timezone.utc) + timedelta(hours=_convite.TOKEN_EXPIRA_HORAS)
    alvo.status_cadastro = _StatusCadastro.APROVADO
    alvo.ativo = True
    db.commit()

    link = _link_ativacao(token)
    email_enviado = _convite.enviar_email_ativacao(alvo.email, alvo.nome, link) if alvo.email else False

    audit.registrar_evento(rota="/usuarios/aprovar", ator_matricula=usuario.matricula,
                           descricao=f"cadastro aprovado: {alvo.matricula}")
    return AprovarResp(link_ativacao=link, email_enviado=email_enviado)


@app.post("/usuarios/{usuario_id}/rejeitar",
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def rejeitar_cadastro_rota(usuario_id: int, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                           db=Depends(get_db)):
    from db.models import StatusCadastro as _StatusCadastro
    from db.repo import buscar_usuario_por_id

    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    if alvo.status_cadastro != _StatusCadastro.PENDENTE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cadastro não está pendente")

    alvo.status_cadastro = _StatusCadastro.REJEITADO
    alvo.ativo = False
    db.commit()
    audit.registrar_evento(rota="/usuarios/rejeitar", ator_matricula=usuario.matricula,
                           descricao=f"cadastro rejeitado: {alvo.matricula}")
    return {"ok": True}


class CriarConviteReq(BaseModel):
    matricula: str
    nome: str
    papel: str
    email: str
    telefone: "str | None" = None


@app.post("/usuarios/convite", status_code=status.HTTP_201_CREATED, response_model=AprovarResp,
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def criar_convite_rota(req: CriarConviteReq, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                       db=Depends(get_db)):
    """Variante de `criar_usuario_rota` sem campo de senha — o gestor já
    decidiu (sem etapa de aprovação), então nasce direto `aprovado`+`ativo`,
    só sem senha utilizável até o usuário abrir o link."""
    from datetime import timedelta, timezone as _timezone

    import convite as _convite
    from sqlalchemy.exc import IntegrityError

    from db.models import Papel as _Papel
    from db.models import StatusCadastro as _StatusCadastro
    from db.models import Usuario as _Usuario
    import secrets as _secrets

    try:
        papel = _Papel(req.papel)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=f"papel inválido — use um de {[p.value for p in _Papel]}")

    token = _convite.gerar_token()
    senha_inutilizavel = auth.hash_senha(_secrets.token_urlsafe(32))
    novo = _Usuario(matricula=req.matricula, nome=req.nome, senha_hash=senha_inutilizavel,
                    papel=papel, gestora_id=usuario.gestora_id, ativo=True,
                    email=req.email, telefone=req.telefone,
                    status_cadastro=_StatusCadastro.APROVADO,
                    convite_token=token,
                    convite_expira_em=datetime.now(_timezone.utc) + timedelta(hours=_convite.TOKEN_EXPIRA_HORAS))
    db.add(novo)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="matrícula já cadastrada")

    link = _link_ativacao(token)
    email_enviado = _convite.enviar_email_ativacao(novo.email, novo.nome, link) if novo.email else False

    audit.registrar_evento(rota="/usuarios/convite", ator_matricula=usuario.matricula,
                           descricao=f"convite enviado: {novo.matricula}")
    return AprovarResp(link_ativacao=link, email_enviado=email_enviado)


@app.patch("/usuarios/{usuario_id}",
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def atualizar_usuario_rota(usuario_id: int, req: AtualizarUsuarioReq,
                           usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual), db=Depends(get_db)):
    from db.models import Papel
    from db.repo import atualizar_usuario, buscar_usuario_por_id
    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")

    campos: dict = {}
    if req.nome is not None:
        campos["nome"] = req.nome
    if req.papel is not None:
        try:
            campos["papel"] = Papel(req.papel)
        except ValueError:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"papel inválido — use um de {[p.value for p in Papel]}")
    if req.ativo is not None:
        # guarda MVP contra self-lockout — não é proteção completa de
        # "último admin" (isso ficaria pra uma iteração futura), só evita o
        # caso mais óbvio: alguém se desativando sem querer.
        if req.ativo is False and alvo.matricula == usuario.matricula:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail="não é possível desativar a própria conta")
        campos["ativo"] = req.ativo
    if req.senha is not None:
        from senha_policy import validar_senha
        violacoes = validar_senha(req.senha)
        if violacoes:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                                detail=f"senha não atende à política: {', '.join(violacoes)}")
        campos["senha_hash"] = auth.hash_senha(req.senha)
    if req.trocar_senha_no_proximo_login is not None:
        campos["trocar_senha_no_proximo_login"] = req.trocar_senha_no_proximo_login
    if req.email is not None:
        campos["email"] = req.email
    if req.telefone is not None:
        campos["telefone"] = req.telefone

    atualizado = atualizar_usuario(db, alvo, **campos)
    db.commit()
    if req.trocar_senha_no_proximo_login:
        audit.registrar_evento(rota="/usuarios", ator_matricula=usuario.matricula,
                               descricao=f"força troca de senha no próximo login: {alvo.matricula}")
    return _usuario_resp(atualizado)


@app.post("/usuarios/{usuario_id}/revogar-sessao",
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def revogar_sessao_rota(usuario_id: int, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                        db=Depends(get_db)):
    """Derruba a sessão ativa de um usuário na hora, sem esperar o JWT
    expirar sozinho — útil em desligamento ou suspeita de conta comprometida.
    Qualquer token emitido ANTES deste momento passa a ser rejeitado por
    `auth.get_usuario_atual` (compara `iat` do token com este timestamp)."""
    from datetime import timezone

    from db.repo import buscar_usuario_por_id
    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    alvo.sessao_revogada_em = datetime.now(timezone.utc)
    db.commit()
    audit.registrar_evento(rota="/usuarios/revogar-sessao", ator_matricula=usuario.matricula,
                           descricao=f"sessão revogada: {alvo.matricula}")
    return {"ok": True}


@app.post("/usuarios/{usuario_id}/resetar-2fa",
        dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def resetar_2fa_rota(usuario_id: int, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                     db=Depends(get_db)):
    """Limpa segredo + ativação de 2FA de outro usuário — cobre o caso de
    perda do celular/app autenticador, que hoje não tem autorrecuperação
    (o próprio dono não consegue desativar o 2FA sozinho, de propósito).
    Nunca no próprio usuário: reset de 2FA sempre passa por outro
    gestor/compliance, pra manter accountability."""
    from db.repo import buscar_usuario_por_id
    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    if alvo.matricula == usuario.matricula:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="não é possível resetar o 2FA da própria conta")
    alvo.totp_secret = None
    alvo.totp_ativado = False
    db.commit()
    audit.registrar_evento(rota="/usuarios/resetar-2fa", ator_matricula=usuario.matricula,
                           descricao=f"2FA resetado: {alvo.matricula}")
    return {"ok": True}


@app.get("/usuarios/{usuario_id}/historico-acessos",
        dependencies=[Depends(auth.exigir_papel("gestor", "compliance"))])
def historico_acessos_rota(usuario_id: int, limit: int = 20,
                           usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                           db=Depends(get_db)):
    from db.repo import buscar_usuario_por_id
    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    return {"ok": True, "eventos": audit.ler(limit=limit, ator_matricula=alvo.matricula)}
