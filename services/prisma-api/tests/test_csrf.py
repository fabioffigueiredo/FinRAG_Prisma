"""Cookie de sessão (httpOnly) + CSRF double-submit, ponta a ponta via TestClient
— primeiro teste HTTP-level (não chamada direta de função) desta suíte."""
import os

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
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
    """SAVEPOINT — /auth/login agora commita (lockout, Meta 5); ver
    .claude/skills/prisma-test-commit-isolation/."""
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


def _usuario_teste(db, matricula="CSRF-001", papel=Papel.ANALISTA) -> Usuario:
    gestora = Gestora(nome=f"Gestora {matricula}")
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Fulano de Tal", senha_hash=auth.hash_senha("senha123"),
                      papel=papel, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return usuario


def _login(client, matricula: str, senha: str = "senha123") -> None:
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text


@pytest.fixture(scope="module")
def test_app():
    """TestClient reaproveitado pelo módulo inteiro — o startup real (índice
    RAG) só roda 1x, não 1x por teste (~8s cada, senão)."""
    import app as app_module
    with TestClient(app_module.app) as c:
        yield app_module, c


@pytest.fixture()
def client(test_app, db):
    """Override de get_db apontando pro banco de teste transacional acima."""
    app_module, c = test_app
    app_module.app.dependency_overrides[app_module.get_db] = lambda: db
    yield c
    app_module.app.dependency_overrides.clear()


# --- unit: atributos dos cookies ---------------------------------------

def test_emitir_cookies_sessao_seta_httponly_no_cookie_de_sessao(db):
    usuario = _usuario_teste(db)
    response = Response()
    auth.emitir_cookies_sessao(response, usuario)
    set_cookie = response.headers.get("set-cookie", "")
    assert "prisma_session=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


def test_emitir_cookies_sessao_csrf_nao_e_httponly(db):
    usuario = _usuario_teste(db, matricula="CSRF-002")
    response = Response()
    auth.emitir_cookies_sessao(response, usuario)
    # dois Set-Cookie no mesmo Response — checar via raw_headers
    valores = [v.decode() for k, v in response.raw_headers if k == b"set-cookie"]
    csrf_header = next(v for v in valores if v.startswith("prisma_csrf="))
    assert "httponly" not in csrf_header.lower()


def test_cookie_secure_flag_segue_prisma_env(monkeypatch, db):
    usuario = _usuario_teste(db, matricula="CSRF-003")
    monkeypatch.setattr(auth, "PRISMA_ENV", "production")
    response = Response()
    auth.emitir_cookies_sessao(response, usuario)
    assert "secure" in response.headers.get("set-cookie", "").lower()


# --- verificar_csrf (double-submit) -------------------------------------

def test_verificar_csrf_aceita_header_igual_ao_cookie():
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "headers": [(b"x-csrf-token", b"abc123"), (b"cookie", b"prisma_csrf=abc123")],
    }
    request = StarletteRequest(scope)
    auth.verificar_csrf(request)  # não deve levantar


def test_verificar_csrf_rejeita_header_diferente_do_cookie():
    from fastapi import HTTPException
    from starlette.requests import Request as StarletteRequest

    scope = {
        "type": "http",
        "headers": [(b"x-csrf-token", b"errado"), (b"cookie", b"prisma_csrf=abc123")],
    }
    request = StarletteRequest(scope)
    with pytest.raises(HTTPException) as exc_info:
        auth.verificar_csrf(request)
    assert exc_info.value.status_code == 403


def test_verificar_csrf_rejeita_ausencia_de_ambos():
    from fastapi import HTTPException
    from starlette.requests import Request as StarletteRequest

    scope = {"type": "http", "headers": []}
    request = StarletteRequest(scope)
    with pytest.raises(HTTPException) as exc_info:
        auth.verificar_csrf(request)
    assert exc_info.value.status_code == 403


# --- fluxo HTTP completo via TestClient ---------------------------------

def test_fluxo_completo_csrf_bootstrap_login_e_rota_protegida(client, db):
    _usuario_teste(db, matricula="CSRF-E2E", papel=Papel.GESTOR)

    resp_csrf = client.get("/auth/csrf")
    assert resp_csrf.status_code == 200
    csrf_token = resp_csrf.json()["csrf_token"]
    assert client.cookies.get("prisma_csrf") == csrf_token

    resp_login = client.post(
        "/auth/login",
        json={"matricula": "CSRF-E2E", "senha": "senha123"},
        headers={"x-csrf-token": csrf_token},
    )
    assert resp_login.status_code == 200
    assert client.cookies.get("prisma_session") is not None

    resp_me = client.get("/auth/me")
    assert resp_me.status_code == 200
    assert resp_me.json()["matricula"] == "CSRF-E2E"

    resp_logout = client.post("/auth/logout", headers={"x-csrf-token": client.cookies.get("prisma_csrf")})
    assert resp_logout.status_code == 200


def test_login_sem_csrf_token_e_rejeitado(client, db):
    _usuario_teste(db, matricula="CSRF-SEM-TOKEN")
    resp = client.post("/auth/login", json={"matricula": "CSRF-SEM-TOKEN", "senha": "senha123"})
    assert resp.status_code == 403


def test_get_usuario_atual_aceita_bearer_sem_cookie(client, db):
    """Compat: chamador não-browser (Bearer puro) continua funcionando mesmo
    sem cookie de sessão."""
    usuario = _usuario_teste(db, matricula="CSRF-BEARER", papel=Papel.COMPLIANCE)
    token = auth.criar_token(usuario)
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["matricula"] == "CSRF-BEARER"


def test_auditoria_bloqueia_analista_e_libera_gestor(client, db):
    """Stage 9: RBAC de /auditoria reativada agora que o login existe."""
    _usuario_teste(db, matricula="AUDIT-ANALISTA", papel=Papel.ANALISTA)
    _usuario_teste(db, matricula="AUDIT-GESTOR", papel=Papel.GESTOR)

    _login(client, "AUDIT-ANALISTA")
    resp_negado = client.get("/auditoria")
    assert resp_negado.status_code == 403

    _login(client, "AUDIT-GESTOR")
    resp_ok = client.get("/auditoria")
    assert resp_ok.status_code == 200
    assert resp_ok.json()["ok"] is True
