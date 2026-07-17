"""Meta 4: hash de senha, JWT e RBAC."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

import auth
from db.models import Base, Gestora, Papel, Usuario
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """Padrão SAVEPOINT (join a session into an external transaction) —
    necessário desde que /auth/login passou a commitar (Meta 5, lockout);
    ver .claude/skills/prisma-test-commit-isolation/. Um `db.commit()` da
    aplicação só libera o savepoint, nunca a transação externa real, então
    o rollback no teardown ainda descarta tudo."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, future=True)

    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _reabrir_savepoint(sess, transacao):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


def _usuario_teste(db, matricula="M001", papel=Papel.ANALISTA, ativo=True) -> Usuario:
    gestora = Gestora(nome=f"Gestora {matricula}")
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Fulano de Tal", senha_hash=auth.hash_senha("senha123"),
                      papel=papel, gestora_id=gestora.id, ativo=ativo)
    db.add(usuario)
    db.flush()
    return usuario


def test_hash_senha_verifica_correta_e_rejeita_errada():
    h = auth.hash_senha("minhasenha")
    assert auth.verificar_senha("minhasenha", h) is True
    assert auth.verificar_senha("outrasenha", h) is False


def test_criar_e_decodificar_token_faz_roundtrip(db):
    usuario = _usuario_teste(db, papel=Papel.GESTOR)
    token = auth.criar_token(usuario)
    payload = auth.decodificar_token(token)
    assert payload["sub"] == usuario.matricula
    assert payload["papel"] == "gestor"
    assert payload["gestora_id"] == usuario.gestora_id


def test_decodificar_token_invalido_levanta_401():
    with pytest.raises(HTTPException) as exc_info:
        auth.decodificar_token("token-totalmente-invalido")
    assert exc_info.value.status_code == 401


def test_autenticar_credenciais_corretas(db):
    _usuario_teste(db, matricula="M002")
    usuario = auth.autenticar(db, "M002", "senha123")
    assert usuario is not None
    assert usuario.matricula == "M002"


def test_autenticar_senha_errada_retorna_none(db):
    _usuario_teste(db, matricula="M003")
    assert auth.autenticar(db, "M003", "senha-errada") is None


def test_autenticar_usuario_inativo_retorna_none(db):
    _usuario_teste(db, matricula="M004", ativo=False)
    assert auth.autenticar(db, "M004", "senha123") is None


def test_autenticar_matricula_inexistente_retorna_none(db):
    assert auth.autenticar(db, "NAO-EXISTE", "senha123") is None


def test_exigir_papel_permite_papel_correto():
    checker = auth.exigir_papel("gestor", "compliance")
    usuario = auth.UsuarioAtual(matricula="M001", nome="Fulano", papel="gestor", gestora_id=1)
    assert checker(usuario) is usuario


def test_exigir_papel_bloqueia_papel_sem_permissao():
    checker = auth.exigir_papel("gestor", "compliance")
    usuario = auth.UsuarioAtual(matricula="M001", nome="Fulano", papel="analista", gestora_id=1)
    with pytest.raises(HTTPException) as exc_info:
        checker(usuario)
    assert exc_info.value.status_code == 403


def test_get_usuario_atual_prioriza_cookie_sobre_bearer(db):
    """Quando os dois estão presentes, o cookie de sessão do navegador vence
    — o Bearer é só fallback pra chamador não-browser (ver test_csrf.py)."""
    from starlette.requests import Request as StarletteRequest

    usuario_cookie = _usuario_teste(db, matricula="M-COOKIE")
    usuario_bearer = _usuario_teste(db, matricula="M-BEARER")
    token_cookie = auth.criar_token(usuario_cookie)
    token_bearer = auth.criar_token(usuario_bearer)

    scope = {
        "type": "http",
        "headers": [
            (b"authorization", f"Bearer {token_bearer}".encode()),
            (b"cookie", f"prisma_session={token_cookie}".encode()),
        ],
    }
    request = StarletteRequest(scope)
    from fastapi.security import HTTPAuthorizationCredentials
    credenciais = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token_bearer)

    resultado = auth.get_usuario_atual(request, credenciais, db=db)
    assert resultado.matricula == "M-COOKIE"


def test_jwt_secret_falha_rapido_em_producao_sem_variavel(monkeypatch):
    """Fail-fast: PRISMA_ENV=production sem PRISMA_JWT_SECRET não pode subir
    com o fallback de dev silenciosamente — reimporta o módulo pra reexecutar
    a checagem de import-time."""
    import importlib

    monkeypatch.delenv("PRISMA_JWT_SECRET", raising=False)
    monkeypatch.setenv("PRISMA_ENV", "production")
    try:
        with pytest.raises(RuntimeError, match="PRISMA_JWT_SECRET"):
            importlib.reload(auth)
    finally:
        # sempre restaurar o módulo pro estado de dev antes de sair do teste,
        # senão todo teste seguinte neste processo herda o RuntimeError.
        monkeypatch.setenv("PRISMA_ENV", "dev")
        importlib.reload(auth)
