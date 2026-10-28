"""Prisma API — camada cognitiva sobre a atribuição de performance.

Envolve o núcleo FinRAG (retrieval + guardrail + prompt aumentado) e expõe:
  POST /narrativa   -> comentário do fundo em linguagem natural (grounded)
  POST /perguntar   -> Q&A RAG fundamentado, com citações e trechos bloqueados
  GET  /health      -> status + backends disponíveis

O pacote finrag (retrieval/guardrails) é vendorizado em ./finrag; adiciona
backend Ollama (local) e embeddings configuráveis.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
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
from pydantic import BaseModel, EmailStr, Field
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

from llm import get_backend, ollama_disponivel, OllamaClient, registrar_falha, registrar_sucesso, status_texto  # noqa: E402
import cota                                                   # noqa: E402
from embed import get_embed_fn                                # noqa: E402
from escopo import (  # noqa: E402
    pede_recomendacao, tenta_injecao, INSTRUCAO_ESCOPO, RESPOSTA_ESCOPO, RESPOSTA_INJECAO,
)
import audit                                                             # noqa: E402
import agent as agente                                                   # noqa: E402
from radar import agregar, persistir_lote, refresh                       # noqa: E402
from sinais import gerar_sinais, AVISO_LEGAL, MODELO_VERSAO              # noqa: E402
import auth                                                              # noqa: E402
from db.session import SessionLocal, get_db                             # noqa: E402
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
    expose_headers=["ETag"],  # o polling do feed do Radar lê o ETag
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

STATE: dict = {
    "index": None,
    "embed": "?",
    "fundos": None,
    "noticias": [],
    "radar": {"estado": "indisponivel", "motivo": "ainda não atualizado"},
}
_RADAR_STOP = threading.Event()
_log_radar = logging.getLogger("prisma.radar")

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
    # Notícias ao vivo não entram automaticamente no corpus RAG. Só o
    # conjunto fictício, versionado e revisável faz parte dessa evidência.
    for n in json.loads(NOTICIAS_PATH.read_text(encoding="utf-8")):
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
    coleta_ligada = os.environ.get("PRISMA_RADAR_REFRESH_ENABLED", "0") == "1"
    _definir_radar([], {
        "estado": "indisponivel",
        "motivo": ("aguardando a primeira coleta de manchetes" if coleta_ligada
                   else "atualização automática do Radar não habilitada neste ambiente"),
    })
    _restaurar_radar()
    if ollama_disponivel():
        OllamaClient().warmup()

    if coleta_ligada:
        # Decidi tirar a coleta síncrona do startup porque notei que ela
        # segurava a API ~10-20s esperando portais lentos. A thread faz a
        # 1ª coleta já (se REFRESH_ON_STARTUP=1) e depois segue o intervalo.
        imediata = os.environ.get("PRISMA_RADAR_REFRESH_ON_STARTUP", "0") == "1"
        _RADAR_STOP.clear()
        threading.Thread(target=_ciclo_radar, args=(imediata,), name="prisma-radar", daemon=True).start()


@app.on_event("shutdown")
def _shutdown() -> None:
    _RADAR_STOP.set()


_RADAR_LOCK_ESTADO = threading.Lock()
# Chave do pg_advisory_lock da coleta: com mais de um worker/réplica, só um
# coleta por vez (os outros pulam o ciclo em vez de duplicar o lote).
_RADAR_ADVISORY_KEY = 7_204_190_031


def _definir_radar(noticias: list, radar_status: dict) -> None:
    """Troca notícias e status juntos — leitores nunca veem metade de cada lote."""
    with _RADAR_LOCK_ESTADO:
        STATE["noticias"] = noticias
        STATE["radar"] = radar_status


def _restaurar_radar() -> None:
    """Depois de um restart, recarrega do Postgres as manchetes recentes em
    vez de ficar vazio até a próxima coleta."""
    try:
        from radar import feed_recente
        with SessionLocal() as db:
            feed = feed_recente(db)
    except Exception:  # noqa: BLE001 - sem banco, espera a próxima coleta
        return
    if feed["itens"]:
        _definir_radar(feed["itens"], {
            "estado": "degradado", "atualizado_em": feed["atualizado_em"],
            "coletadas": len(feed["itens"]), "elegiveis": 0, "modelo": None,
            "motivo": "sem evidência recente classificada com confiança suficiente",
        })


def _persistir_lote_coletado(noticias: list, radar_status: dict) -> None:
    """Grava o lote numa sessão curta, depois da coleta de rede."""
    from radar import podar
    with SessionLocal() as db:
        try:
            persistir_lote(db, noticias, radar_status)
            podar(db, int(os.environ.get("PRISMA_RADAR_RETENCAO_DIAS", "30")))
        except Exception:  # noqa: BLE001 - banco não pode apagar o lote em memória
            db.rollback()
            _definir_radar(noticias, {**radar_status, "estado": "degradado",
                                      "motivo": "lote não foi persistido; verifique a base de dados"})


def _atualizar_radar() -> None:
    """Uma coleta, protegida por lock consultivo do Postgres.

    Decidi segurar o lock numa CONEXÃO dedicada (não numa Session) porque
    notei que o lock consultivo é por conexão: com Session, os commits
    intermediários devolviam a conexão ao pool e o unlock rodava em outra —
    o lock ficava órfão e todo ciclo seguinte era pulado para sempre.
    A coleta de rede (RSS, até ~40 s) roda sem transação aberta.
    """
    from sqlalchemy import text
    from db.session import engine
    try:
        conexao = engine.connect()
    except Exception:  # noqa: BLE001 - sem banco: coleta só em memória
        noticias, radar_status = refresh()
        _definir_radar(noticias, {**radar_status, "estado": "degradado",
                                  "motivo": "lote não foi persistido; verifique a base de dados"})
        return
    try:
        obteve = bool(conexao.execute(text("SELECT pg_try_advisory_lock(:k)"),
                                      {"k": _RADAR_ADVISORY_KEY}).scalar())
        conexao.commit()  # encerra a transação; o lock de sessão continua nesta conexão
        if not obteve:
            _log_radar.info("Outra instância está coletando; ciclo pulado.")
            return
        try:
            noticias, radar_status = refresh()
            _definir_radar(noticias, radar_status)
            _persistir_lote_coletado(noticias, radar_status)
        finally:
            conexao.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _RADAR_ADVISORY_KEY})
            conexao.commit()
    finally:
        conexao.close()


def _ciclo_radar(imediata: bool = False) -> None:
    """Loop da coleta. Uma exceção num ciclo não mata a thread — antes, um
    erro inesperado encerrava o Radar até o próximo restart, em silêncio."""
    intervalo = max(5, int(os.environ.get("PRISMA_RADAR_REFRESH_MINUTES", "30"))) * 60
    espera = 0 if imediata else intervalo
    while not _RADAR_STOP.wait(espera):
        try:
            _atualizar_radar()
            espera = intervalo
        except Exception:  # noqa: BLE001
            _log_radar.exception("Ciclo do Radar falhou; nova tentativa em 60s.")
            espera = 60


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
    gestora_id: "int | None" = None


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
    usuario = auth.autenticar(db, req.matricula, req.senha, gestora_id=req.gestora_id)
    # Sempre commita — mesmo em falha — pra persistir o contador de
    # tentativas/bloqueio que `autenticar()` só marcou no objeto, sem commitar.
    db.commit()
    if usuario is None:
        filtros_alvo = [_Usuario.matricula == req.matricula]
        if req.gestora_id is not None:
            filtros_alvo.append(_Usuario.gestora_id == req.gestora_id)
        candidatos_alvo = db.scalars(_select(_Usuario).where(*filtros_alvo)).all()
        alvo = candidatos_alvo[0] if len(candidatos_alvo) == 1 else None
        bloqueado = alvo is not None and alvo.bloqueado_ate is not None
        audit.registrar_evento(
            rota="/auth/login", ator_matricula=req.matricula, gestora_id=req.gestora_id,
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
        audit.registrar_evento(rota="/auth/login", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                               descricao="login etapa 1/2 — aguardando código 2FA")
        return LoginResp(nome=usuario.nome, papel=usuario.papel.value,
                         gestora_id=usuario.gestora_id, requer_2fa=True)

    auth.emitir_cookies_sessao(response, usuario)
    audit.registrar_evento(rota="/auth/login", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id, descricao="login bem-sucedido")
    return LoginResp(token=auth.criar_token(usuario), nome=usuario.nome,
                     papel=usuario.papel.value, gestora_id=usuario.gestora_id)


@app.post("/auth/logout")
def logout(request: Request, response: Response):
    # Não exige sessão válida (get_usuario_atual dá 401 nesse caso) — logout
    # sem sessão continua sendo um no-op gracioso. Só tenta decodificar o
    # cookie/Bearer, sem lançar, pra saber quem saiu na auditoria.
    ator_matricula, gestora_ator = None, None
    try:
        token = request.cookies.get(auth.COOKIE_SESSAO)
        if token:
            claims = auth.decodificar_token(token)
            ator_matricula, gestora_ator = claims["sub"], claims.get("gestora_id")
    except HTTPException:
        pass
    auth.limpar_cookies_sessao(response)
    auth.limpar_cookie_pre2fa(response)
    if ator_matricula:
        audit.registrar_evento(rota="/auth/logout", ator_matricula=ator_matricula, gestora_id=gestora_ator,
                               descricao="logout")
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
    audit.registrar_evento(rota="/auth/senha", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id, descricao="senha alterada")
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
    audit.registrar_evento(rota="/auth/avatar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao="avatar atualizado")
    return {"avatar_url": alvo.avatar_url}


class Iniciar2FAResp(BaseModel):
    otpauth_uri: str
    qr_base64: str


class Iniciar2FAReq(BaseModel):
    senha_atual: "str | None" = None


@app.post("/auth/2fa/iniciar", response_model=Iniciar2FAResp, dependencies=[Depends(auth.verificar_csrf)])
def iniciar_2fa(request: Request, req: Iniciar2FAReq = Iniciar2FAReq(),
                usuario: auth.UsuarioAtual = Depends(auth.exigir_papel("gestor", "compliance")),
                db=Depends(get_db)):
    """Fininho, mesmo motivo das outras rotas com rate limit (ver skill
    fastapi-slowapi-future-annotations)."""
    return _iniciar_2fa_com_rate_limit(request, req, usuario, db)


@limiter.limit("5/minute")
def _iniciar_2fa_com_rate_limit(request: Request, req: Iniciar2FAReq, usuario: auth.UsuarioAtual, db) -> Iniciar2FAResp:
    """Gera o segredo e devolve o QR — NÃO ativa ainda, e não toca no 2FA já
    ativo. Fica em staging (`totp_secret_pendente`); só /auth/2fa/confirmar
    promove pra `totp_secret`/`totp_ativado`, depois de provar que o
    usuário configurou certo num app autenticador de verdade. Abandonar o
    fluxo aqui (fechar a aba, não escanear o QR) não desliga o 2FA que já
    estava funcionando — o dispositivo antigo continua válido até o novo
    ser confirmado.

    Step-up: se já existe um 2FA ativo (troca de dispositivo self-service),
    exige a senha atual antes de gerar um segredo novo em staging — sem
    isso, um cookie de sessão roubado sozinho bastaria pra sequestrar o 2FA
    (ver docs/SEGURANCA.md). Primeiro enrollment (totp_ativado=False) não
    exige nada além do papel. O step-up usa o mesmo lockout do login
    (`verificar_senha_com_lockout`) e rate limit de 5/minuto — sem isso,
    um cookie de sessão roubado vira um oráculo de senha ilimitado."""
    import base64
    import io

    import pyotp
    import qrcode

    from db.models import Usuario as _Usuario

    alvo = db.get(_Usuario, usuario.id)
    if alvo.totp_ativado:
        senha_ok = auth.verificar_senha_com_lockout(alvo, req.senha_atual)
        # Sempre commita — mesmo em falha — pra persistir o contador de
        # tentativas/bloqueio (mesmo motivo do /auth/login).
        db.commit()
        if not senha_ok:
            bloqueado = alvo.bloqueado_ate is not None
            audit.registrar_evento(
                rota="/auth/2fa/iniciar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                descricao="step-up de senha falhou — conta bloqueada" if bloqueado else "step-up de senha falhou",
                extra={"bloqueado": True} if bloqueado else None,
            )
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="senha atual incorreta")

    segredo = pyotp.random_base32()
    alvo.totp_secret_pendente = segredo
    db.commit()

    uri = pyotp.totp.TOTP(segredo).provisioning_uri(name=usuario.matricula, issuer_name="Prisma")
    imagem = qrcode.make(uri)
    buffer = io.BytesIO()
    imagem.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    audit.registrar_evento(rota="/auth/2fa/iniciar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao="2FA — enrollment iniciado")
    return Iniciar2FAResp(otpauth_uri=uri, qr_base64=qr_base64)


class Confirmar2FAReq(BaseModel):
    codigo: str


@app.post("/auth/2fa/confirmar", dependencies=[Depends(auth.verificar_csrf)])
def confirmar_2fa(request: Request, req: Confirmar2FAReq,
                  usuario: auth.UsuarioAtual = Depends(auth.exigir_papel("gestor", "compliance")),
                  db=Depends(get_db)):
    """Fininho, mesmo motivo das outras rotas com rate limit (ver skill
    fastapi-slowapi-future-annotations)."""
    return _confirmar_2fa_com_rate_limit(request, req, usuario, db)


@limiter.limit("5/minute")
def _confirmar_2fa_com_rate_limit(request: Request, req: Confirmar2FAReq,
                                   usuario: auth.UsuarioAtual, db):
    """Achado #16: TOTP de 6 dígitos é alvo de força bruta se não limitado —
    a rota irmã (/auth/2fa/verificar) já reconhecia isso, esta não tinha o
    mesmo limitador."""
    import pyotp

    from db.models import Usuario as _Usuario
    alvo = db.get(_Usuario, usuario.id)
    if not alvo.totp_secret_pendente:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="nenhum enrollment de 2FA em andamento — chame /auth/2fa/iniciar primeiro")
    if not pyotp.TOTP(alvo.totp_secret_pendente).verify(req.codigo, valid_window=1):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="código inválido")
    alvo.totp_secret = alvo.totp_secret_pendente
    alvo.totp_secret_pendente = None
    alvo.totp_ativado = True
    db.commit()
    audit.registrar_evento(rota="/auth/2fa/confirmar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
        audit.registrar_evento(rota="/auth/2fa/verificar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                               descricao="código 2FA inválido")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="código inválido")

    auth.limpar_cookie_pre2fa(response)
    auth.emitir_cookies_sessao(response, usuario)
    audit.registrar_evento(rota="/auth/2fa/verificar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao="login etapa 2/2 — 2FA confirmado")
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


class GestoraPublicaResp(BaseModel):
    id: int
    nome: str


@app.get("/auth/gestoras", response_model=list[GestoraPublicaResp])
def listar_gestoras_publico(db=Depends(get_db)):
    """Pública de propósito — o formulário de autocadastro precisa saber
    quais gestoras (tenants) existem pra oferecer a escolha. Só id/nome, sem
    nenhum dado sensível."""
    from sqlalchemy import select as _select

    from db.models import Gestora as _Gestora

    gestoras = db.scalars(_select(_Gestora).order_by(_Gestora.nome)).all()
    return [GestoraPublicaResp(id=g.id, nome=g.nome) for g in gestoras]


class CadastroReq(BaseModel):
    matricula: str = Field(max_length=20)
    nome: str = Field(max_length=120)
    email: EmailStr = Field(max_length=160)
    telefone: "str | None" = Field(default=None, max_length=30)
    gestora_id: int


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
    senha utilizável, mas fica explícito.

    `gestora_id` vem do próprio candidato (GET /auth/gestoras alimenta o
    seletor no formulário) — sem isso, todo mundo caía na gestora de menor
    id, misturando o tenant errado (achado de revisão)."""
    import secrets as _secrets
    from sqlalchemy.exc import IntegrityError

    from db.models import Gestora as _Gestora
    from db.models import Papel as _Papel
    from db.models import StatusCadastro as _StatusCadastro
    from db.models import Usuario as _Usuario

    gestora = db.get(_Gestora, req.gestora_id)
    if gestora is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="gestora inválida")

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

    audit.registrar_evento(rota="/auth/cadastro", ator_matricula=req.matricula, gestora_id=req.gestora_id,
                           descricao="autocadastro solicitado — aguardando aprovação")
    return {"ok": True}


class ConviteValidoResp(BaseModel):
    nome: str
    matricula: str


@app.get("/auth/convite/{token}", response_model=ConviteValidoResp)
@limiter.limit("20/minute")
def validar_convite_rota(request: Request, token: str, db=Depends(get_db)):
    """Pública de propósito (o usuário ainda não tem sessão) — só devolve o
    mínimo pra saudação da tela (nome/matrícula), nunca papel/e-mail/etc.
    Rate limit (achado #10): as outras rotas públicas do fluxo de
    cadastro/convite já tinham; esta não tinha, mesmo consumindo um token
    (defesa em profundidade — o token já tem 256 bits de entropia)."""
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
    # zera qualquer lockout acumulado ANTES da ativação — a conta convidada
    # já existe com ativo=True e senha inutilizável desde a criação do
    # convite, então um atacante pode ter esgotado as tentativas de login
    # nesse meio-tempo. Provar posse do token é mais forte que a senha
    # antiga, e o dono legítimo não deveria herdar um bloqueio alheio.
    alvo.bloqueado_ate = None
    alvo.tentativas_falhas = 0
    db.commit()

    auth.emitir_cookies_sessao(response, alvo)
    audit.registrar_evento(rota="/auth/ativar-conta", ator_matricula=alvo.matricula, gestora_id=alvo.gestora_id, descricao="conta ativada")
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


TEXTO_DEMONSTRACAO = (
    "(Demonstração — o motor de IA escolhido está indisponível agora; este texto é "
    "um exemplo fixo, não uma análise do fundo.) No período, o resultado do fundo foi "
    "sustentado principalmente pelo carrego das estratégias de crédito privado e juros."
)


def _gerar_seguro(backend: str, prompt: str, rota: str = "", **kw) -> tuple[str, bool, str, int]:
    """Gera texto; se o motor falhar (sem chave, modelo retirado, Ollama
    ausente, timeout) degrada para um texto de demonstração ROTULADO e
    sinaliza. Devolve (texto, degradado, motor_efetivo, tokens).

    Decidi tratar resposta vazia como falha porque notei que modelos com
    raciocínio podem gastar todo o limite de saída pensando e devolver "".
    """
    t0 = time.perf_counter()
    cliente = None
    try:
        cliente = get_backend(backend)
        texto = cliente.generate(prompt, **kw).strip()
        if not texto:
            raise RuntimeError("motor devolveu resposta vazia")
        degradado, motor = False, (backend or "ollama").lower()
        registrar_sucesso(motor)
    except Exception as e:  # noqa: BLE001 - qualquer falha vira modo demonstração rotulado
        registrar_falha((backend or "").lower(), e)
        texto, degradado, motor = TEXTO_DEMONSTRACAO, True, "demo"
    # Fora do try: resposta vazia também consumiu tokens no provedor e
    # precisa contar na cota (senão repetir pedido vazio seria "de graça").
    tokens = int(getattr(cliente, "ultimo_uso_tokens", 0) or 0)
    latency_ms = int((time.perf_counter() - t0) * 1000)
    evento = observability.registrar_chamada_llm(
        backend=motor, modelo=backend, prompt=prompt,
        resposta=texto, latency_ms=latency_ms, rota=rota,
    )
    if not tokens and not degradado:
        tokens = evento["tokens_entrada_estimado"] + evento["tokens_saida_estimado"]
    return texto, degradado, motor, tokens


def _fundos_visiveis(usuario: auth.UsuarioAtual) -> dict:
    """Fundos que este usuário pode consultar nas rotas cognitivas.

    Os fundos carregados do seed formam o catálogo FICTÍCIO da demonstração,
    compartilhado por todas as gestoras. Decidi esconder um código assim que
    o banco o atribuir a OUTRA gestora porque notei que as rotas liam o
    STATE global sem filtro algum — dado real de um tenant vazaria para outro
    no dia em que um fundo de verdade fosse carregado.
    """
    fundos = STATE.get("fundos") or {}
    donos = _donos_de_fundos()
    return {c: f for c, f in fundos.items() if donos.get(c) in (None, usuario.gestora_id)}


def _donos_de_fundos() -> dict:
    """codigo -> gestora_id dos fundos que o banco atribui a um tenant."""
    try:
        from sqlalchemy import select
        from db.models import Fundo
        with SessionLocal() as db:
            return dict(db.execute(
                select(Fundo.codigo, Fundo.gestora_id).where(Fundo.gestora_id.is_not(None))
            ).all())
    except Exception:  # noqa: BLE001 - sem banco, vale só o catálogo fictício
        return {}


def _fundo_do_usuario(usuario: auth.UsuarioAtual, codigo: str) -> tuple[dict, "dict | None"]:
    """Resolve o fundo pedido dentro do que o usuário pode ver. Pedido de
    fundo de outra gestora é 404 (não revela que existe)."""
    fundos = _fundos_visiveis(usuario)
    f = fundos.get(codigo)
    if f is None:
        # Antes caía no primeiro fundo da lista: a pergunta sobre o fundo X
        # era respondida com os números do fundo Y, sem aviso.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="fundo não encontrado")
    return fundos, f


def _ator(usuario: auth.UsuarioAtual) -> dict:
    return {"ator_matricula": usuario.matricula, "gestora_id": usuario.gestora_id}


@app.get("/health")
def health():
    return {
        "status": "ok",
        "embeddings": {"estado": "disponivel", "motor": STATE["embed"]},
        "texto": status_texto(),
        "radar": STATE["radar"],
        "chunks": len(STATE["index"]._chunks) if STATE["index"] else 0,
    }


@app.get("/demo/status")
def demo_status():
    """Estado seguro para a rota pública; sem segredos ou detalhes de sessão."""
    health_state = health()
    return {
        "ok": True,
        "dados": "fictícios",
        "texto": health_state["texto"],
        "embeddings": health_state["embeddings"],
        "radar": STATE["radar"],
        "limites": [
            "A demonstração não cria conta, não recebe arquivos e não aceita perguntas livres.",
            "O PRISMA explica um cenário fictício; não produz recomendação financeira.",
        ],
    }


@app.post("/narrativa")
def narrativa(req: NarrativaReq, usuario: auth.UsuarioAtual = Depends(cota.usuario_ia)):
    t0 = time.perf_counter()
    _, f = _fundo_do_usuario(usuario, req.fundo)
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
    texto, degradado, motor, tokens = _gerar_seguro(req.backend, prompt, rota="/narrativa",
                                                    temperature=0.1, max_tokens=220)
    cota.registrar(usuario, tokens)
    lat = int((time.perf_counter() - t0) * 1000)
    fontes = [c.source for c, _ in retr]
    audit.registrar(rota="/narrativa", fundo=f["fundo"]["codigo"], pergunta="(narrativa do período)",
                    backend=req.backend, latency_ms=lat, fontes=fontes, bloqueados=[],
                    resposta=texto, extra={**_ator(usuario), "motor_efetivo": motor, "degradado": degradado})
    return {
        "texto": texto,
        "citacoes": [{"fonte": c.source, "trecho": c.text[:160].strip(), "score": round(float(s), 3)} for c, s in retr],
        "backend": req.backend,
        "motor_solicitado": req.backend,
        "motor_efetivo": motor,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/perguntar")
def perguntar(req: PerguntaReq, usuario: auth.UsuarioAtual = Depends(cota.usuario_ia)):
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={**_ator(usuario), "injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={**_ator(usuario), "escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    idx = STATE["index"]
    fundos, _ = _fundo_do_usuario(usuario, req.fundo)
    codigos = e_comparativa(req.pergunta) or [req.fundo]
    fund_chunks = [_fund_chunk(fundos[c]) for c in codigos if c in fundos]

    retr = idx.search(req.pergunta, k=4)
    scores = {id(c): s for c, s in retr}
    safe, blocked = sanitize_chunks([c for c, _ in retr])
    contexto = fund_chunks + safe
    prompt = build_augmented_prompt(req.pergunta, contexto) + INSTRUCAO_ESCOPO
    resposta, degradado, motor, tokens = _gerar_seguro(req.backend, prompt, rota="/perguntar",
                                                       temperature=0.1, max_tokens=380)
    cota.registrar(usuario, tokens)
    lat = int((time.perf_counter() - t0) * 1000)
    citacoes = [
        {"fonte": c.source, "trecho": c.text[:160].strip(),
         "score": round(float(scores.get(id(c), 0)), 3)}
        for c in contexto
    ]
    audit.registrar(rota="/perguntar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[c["fonte"] for c in citacoes],
                    bloqueados=[c.source for c in blocked], resposta=resposta,
                    extra={**_ator(usuario), "motor_efetivo": motor, "degradado": degradado})
    return {
        "resposta": resposta,
        "citacoes": citacoes,
        "bloqueados": [{"fonte": c.source, "motivo": "prompt injection detectado pelo guardrail"} for c in blocked],
        "backend": req.backend,
        "motor_solicitado": req.backend,
        "motor_efetivo": motor,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/analisar")
def analisar_endpoint(req: AnalisarReq, usuario: auth.UsuarioAtual = Depends(cota.usuario_ia)):
    """Copiloto de análise conversacional: traduz a pergunta em chamadas de
    ferramenta sobre os dados do fundo (POC sobre o seed) e devolve narrativa +
    gráfico(s) + chips de ação. Mesmos guardrails do /perguntar."""
    t0 = time.perf_counter()
    if tenta_injecao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[],
                        bloqueados=["(pergunta) injeção/vazamento"], resposta=RESPOSTA_INJECAO,
                        extra={**_ator(usuario), "injecao": True})
        return {"resposta": RESPOSTA_INJECAO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [],
                "bloqueados": [{"fonte": "pergunta do usuário",
                                "motivo": "tentativa de injeção/vazamento de prompt"}],
                "backend": req.backend, "latency_ms": 0, "injecao": True}
    if pede_recomendacao(req.pergunta):
        audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                        backend=req.backend, latency_ms=0, fontes=[], bloqueados=[],
                        resposta=RESPOSTA_ESCOPO, extra={**_ator(usuario), "escopo": True})
        return {"resposta": RESPOSTA_ESCOPO, "consulta_echo": {}, "blocos": [], "acoes": [],
                "avisos": [], "citacoes": [], "bloqueados": [],
                "backend": req.backend, "latency_ms": 0, "escopo": True}

    fundos, _ = _fundo_do_usuario(usuario, req.fundo)
    # Só notícia classificada com confiança entra no raciocínio do agente;
    # manchete crua do feed não é evidência de sinal (falha fechada de 31/08).
    with _RADAR_LOCK_ESTADO:
        noticias = [n for n in (STATE.get("noticias") or []) if n.get("elegivel_agregado")]
    degradado, motor, tokens = False, (req.backend or "ollama").lower(), 0
    cliente = None
    try:
        cliente = get_backend(req.backend)
        if hasattr(cliente, "chat"):
            resultado = agente.analisar(pergunta=req.pergunta, fundo_ativo=req.fundo,
                                        backend=cliente, fundos=fundos, noticias=noticias)
        else:
            resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos,
                                             noticias=noticias, pergunta=req.pergunta)
            degradado, motor = True, "demo"
        if not degradado and not (resultado.get("resposta") or "").strip():
            raise RuntimeError("motor devolveu resposta vazia")
        if not degradado:
            registrar_sucesso(motor)
    except Exception as e:  # noqa: BLE001 - falha do motor vira demonstração rotulada
        registrar_falha(motor, e)
        resultado = agente.analisar_mock(fundo_ativo=req.fundo, fundos=fundos,
                                         noticias=noticias, pergunta=req.pergunta)
        degradado, motor = True, "demo"
    tokens = int(getattr(cliente, "tokens_acumulados", 0) or 0)
    cota.registrar(usuario, tokens)

    lat = int((time.perf_counter() - t0) * 1000)
    audit.registrar(rota="/analisar", fundo=req.fundo, pergunta=req.pergunta,
                    backend=req.backend, latency_ms=lat,
                    fontes=[t["tool"] for t in resultado.get("tool_trace", [])],
                    bloqueados=[], resposta=resultado["resposta"],
                    extra={**_ator(usuario), "consulta_echo": resultado.get("consulta_echo"),
                           "tool_trace": resultado.get("tool_trace"),
                           "motor_efetivo": motor, "degradado": degradado})
    return {
        "resposta": resultado["resposta"],
        "consulta_echo": resultado.get("consulta_echo", {}),
        "blocos": resultado.get("blocos", []),
        "acoes": resultado.get("acoes", []),
        "avisos": resultado.get("avisos", []),
        "citacoes": [],
        "bloqueados": [],
        "backend": req.backend,
        "motor_solicitado": req.backend,
        "motor_efetivo": motor,
        "latency_ms": lat,
        "degradado": degradado,
    }


@app.post("/ingerir")
def ingerir(req: IngestReq, _usuario: auth.UsuarioAtual = Depends(cota.usuario_com_csrf)):
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


@app.get("/radar/feed")
def radar_feed(request: Request, response: Response,
               _usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual)):
    """Manchetes ao vivo, NÃO classificadas. Contrato separado do /radar
    (agregado/sinal), que continua em falha fechada (decisão de 31/08).
    ETag permite polling barato: sem lote novo, 304 sem corpo."""
    from radar import feed_recente
    try:
        with SessionLocal() as db:
            feed = feed_recente(db)
        fonte = "banco"
    except Exception:  # noqa: BLE001 - sem banco, serve o último lote em memória
        with _RADAR_LOCK_ESTADO:
            itens = [n for n in (STATE.get("noticias") or []) if n.get("relevante")]
            atualizado = (STATE.get("radar") or {}).get("atualizado_em")
        feed = {"itens": itens, "lote_id": None, "atualizado_em": atualizado, "lotes": 0}
        fonte = "memoria"
    etag = '"' + hashlib.sha256(
        f"{feed['atualizado_em']}|{len(feed['itens'])}|{feed['itens'][0]['fingerprint'] if feed['itens'] else ''}"
        .encode()).hexdigest()[:20] + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, no-cache"
    with _RADAR_LOCK_ESTADO:
        status_radar = dict(STATE.get("radar") or {})
    itens = [{k: n[k] for k in ("id", "titulo", "link", "portal", "publicada_em", "coletada_em")}
             for n in feed["itens"]]
    return {
        "ok": bool(itens),
        "itens": itens,
        "classificacao": "nao_classificado",
        "aviso": "Manchetes públicas sem classificação de sentimento. Não são sinal nem recomendação.",
        "atualizado_em": feed["atualizado_em"],
        "coleta": "ligada" if os.environ.get("PRISMA_RADAR_REFRESH_ENABLED", "0") == "1" else "desligada",
        "motivo": None if itens else status_radar.get("motivo"),
        "fonte": fonte,
    }


@app.get("/radar")
def radar_endpoint():
    """Agregado de sentimento (o "sinal"). Falha fechada: só entra notícia
    classificada localmente com confiança suficiente — o feed cru de
    manchetes vive em /radar/feed."""
    with _RADAR_LOCK_ESTADO:
        todas = list(STATE.get("noticias") or [])
        status_radar = dict(STATE.get("radar") or {})
    noticias = [n for n in todas if n.get("elegivel_agregado")]
    agregado = agregar(noticias)
    return {
        "ok": bool(agregado),
        "noticias": noticias,
        "agregado": agregado,
        "estado": status_radar.get("estado", "indisponivel"),
        "atualizado_em": status_radar.get("atualizado_em"),
        "modelo": status_radar.get("modelo"),
        "motivo": status_radar.get("motivo"),
        "degradado": status_radar.get("estado") != "disponivel",
    }


@app.get("/sinais")
def sinais_endpoint(fundo: str = "ALFA-33",
                    usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual)):
    """Alertas probabilísticos de apoio à decisão (modelo de regras auditável).
    Mesmo isolamento por gestora das rotas cognitivas (404 se não for seu)."""
    _, f = _fundo_do_usuario(usuario, fundo)
    with _RADAR_LOCK_ESTADO:
        noticias = [n for n in (STATE.get("noticias") or []) if n.get("elegivel_agregado")]
    agregado = agregar(noticias)
    if not f or not noticias or not agregado:
        return {
            "ok": False,
            "sinais": [],
            "aviso": "Sem evidência recente e classificada com confiança suficiente. " + AVISO_LEGAL,
            "modelo": MODELO_VERSAO,
        }
    sinais = gerar_sinais(f, agregado, noticias)
    return {"ok": True, "sinais": sinais, "aviso": AVISO_LEGAL, "modelo": MODELO_VERSAO}


@app.get("/auditoria")
def auditoria(limit: int = 50,
              usuario: auth.UsuarioAtual = Depends(auth.exigir_papel("gestor", "compliance"))):
    """Só gestor/compliance auditam, e só a PRÓPRIA gestora — antes a
    leitura era global e um gestor da gestora A via perguntas da B."""
    return {"ok": True, "consultas": audit.ler(limit=limit, gestora_id=usuario.gestora_id)}


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
    matricula: str = Field(max_length=20)
    nome: str = Field(max_length=120)
    papel: str
    senha: str
    trocar_senha_no_proximo_login: bool = False
    email: "EmailStr | None" = Field(default=None, max_length=160)
    telefone: "str | None" = Field(default=None, max_length=30)


class AtualizarUsuarioReq(BaseModel):
    """Update parcial — `matricula` e `gestora_id` de propósito não existem
    aqui: são imutáveis por essa rota (ver Stage 3 do plano)."""
    nome: str | None = Field(default=None, max_length=120)
    papel: str | None = None
    ativo: bool | None = None
    senha: str | None = None
    trocar_senha_no_proximo_login: bool | None = None
    email: "EmailStr | None" = Field(default=None, max_length=160)
    telefone: "str | None" = Field(default=None, max_length=30)


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
    audit.registrar_evento(rota="/usuarios", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
    if alvo.status_cadastro not in (_StatusCadastro.PENDENTE, _StatusCadastro.REJEITADO):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="cadastro precisa estar pendente ou rejeitado")

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

    audit.registrar_evento(rota="/usuarios/aprovar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao=f"cadastro aprovado: {alvo.matricula}")
    return AprovarResp(link_ativacao=link, email_enviado=email_enviado)


@app.post("/usuarios/{usuario_id}/reenviar-convite", response_model=AprovarResp,
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def reenviar_convite_rota(usuario_id: int, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                          db=Depends(get_db)):
    """Gera um novo token quando o anterior expirou (48h) e o usuário nunca
    ativou a conta — mesmo efeito de `aprovar_cadastro_rota`, mas pra quem
    já está `APROVADO` (não passa por Pendente de novo)."""
    from datetime import timedelta, timezone as _timezone

    import convite as _convite

    from db.models import StatusCadastro as _StatusCadastro
    from db.repo import buscar_usuario_por_id

    alvo = buscar_usuario_por_id(db, usuario_id)
    if alvo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="usuário não encontrado")
    if alvo.gestora_id != usuario.gestora_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="usuário de outra gestora")
    if alvo.status_cadastro != _StatusCadastro.APROVADO:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="cadastro não está aprovado")
    if alvo.convite_token is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="conta já foi ativada")

    token = _convite.gerar_token()
    alvo.convite_token = token
    alvo.convite_expira_em = datetime.now(_timezone.utc) + timedelta(hours=_convite.TOKEN_EXPIRA_HORAS)
    db.commit()

    link = _link_ativacao(token)
    email_enviado = _convite.enviar_email_ativacao(alvo.email, alvo.nome, link) if alvo.email else False

    audit.registrar_evento(rota="/usuarios/reenviar-convite", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao=f"convite reemitido: {alvo.matricula}")
    return AprovarResp(link_ativacao=link, email_enviado=email_enviado)


@app.post("/usuarios/{usuario_id}/rejeitar",
          dependencies=[Depends(auth.exigir_papel("gestor", "compliance")), Depends(auth.verificar_csrf)])
def rejeitar_cadastro_rota(usuario_id: int, usuario: auth.UsuarioAtual = Depends(auth.get_usuario_atual),
                           db=Depends(get_db)):
    import convite as _convite

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
    if alvo.email:
        _convite.enviar_email_rejeicao(alvo.email, alvo.nome)
    audit.registrar_evento(rota="/usuarios/rejeitar", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
                           descricao=f"cadastro rejeitado: {alvo.matricula}")
    return {"ok": True}


class CriarConviteReq(BaseModel):
    matricula: str = Field(max_length=20)
    nome: str = Field(max_length=120)
    papel: str
    email: EmailStr = Field(max_length=160)
    telefone: "str | None" = Field(default=None, max_length=30)


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

    audit.registrar_evento(rota="/usuarios/convite", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
        if req.ativo is False:
            # sem isso, um convite/autocadastro aprovado antes da
            # desativação continua com o token de ativação válido por até
            # 48h — quem tiver o link reativa a própria conta sozinho,
            # desfazendo a decisão do admin (achado de revisão).
            campos["convite_token"] = None
            campos["convite_expira_em"] = None
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
        audit.registrar_evento(rota="/usuarios", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
    audit.registrar_evento(rota="/usuarios/revogar-sessao", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
    alvo.totp_secret_pendente = None
    db.commit()
    audit.registrar_evento(rota="/usuarios/resetar-2fa", ator_matricula=usuario.matricula, gestora_id=usuario.gestora_id,
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
    return {"ok": True, "eventos": audit.ler(limit=limit, ator_matricula=alvo.matricula,
                                             gestora_id=alvo.gestora_id)}
