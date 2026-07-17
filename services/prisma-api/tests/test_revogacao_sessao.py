"""Revogação de sessão (Stage 5 + 11): `get_usuario_atual` passa a consultar
o banco e comparar o `iat` do token com `sessao_revogada_em`; rota HTTP
`POST /usuarios/{id}/revogar-sessao` (RBAC gestor/compliance + tenant + CSRF).
"""
import time
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from starlette.requests import Request as StarletteRequest

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


def _gestora_com_usuario(db, matricula="ADMIN-REV", papel=Papel.GESTOR, gestora_nome="Gestora Revogação") -> tuple[Gestora, Usuario]:
    gestora = Gestora(nome=gestora_nome)
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Admin", senha_hash=auth.hash_senha("Senha-123!"),
                      papel=papel, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return gestora, usuario


def _request_com_bearer(token: str) -> StarletteRequest:
    scope = {"type": "http", "headers": [(b"authorization", f"Bearer {token}".encode())]}
    return StarletteRequest(scope)


# --- get_usuario_atual + sessao_revogada_em (nível de função) --------------

def test_token_emitido_antes_da_revogacao_e_rejeitado(db):
    _, usuario = _gestora_com_usuario(db, matricula="REV-001")
    token = auth.criar_token(usuario)
    time.sleep(1.1)  # garante iat do token < timestamp da revogação (granularidade de segundo)
    usuario.sessao_revogada_em = datetime.now(timezone.utc)
    db.flush()

    request = _request_com_bearer(token)
    credenciais = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc_info:
        auth.get_usuario_atual(request, credenciais, db=db)
    assert exc_info.value.status_code == 401


def test_token_emitido_depois_da_revogacao_continua_valido(db):
    _, usuario = _gestora_com_usuario(db, matricula="REV-002")
    usuario.sessao_revogada_em = datetime.now(timezone.utc)
    db.flush()
    time.sleep(1.1)
    token = auth.criar_token(usuario)  # emitido DEPOIS da revogação

    request = _request_com_bearer(token)
    credenciais = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    resultado = auth.get_usuario_atual(request, credenciais, db=db)
    assert resultado.matricula == "REV-002"


def test_usuario_sem_revogacao_nunca_e_afetado(db):
    _, usuario = _gestora_com_usuario(db, matricula="REV-003")
    token = auth.criar_token(usuario)
    request = _request_com_bearer(token)
    credenciais = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    resultado = auth.get_usuario_atual(request, credenciais, db=db)
    assert resultado.matricula == "REV-003"


# --- rota HTTP POST /usuarios/{id}/revogar-sessao ---------------------------

@pytest.fixture(scope="module")
def test_app():
    import app as app_module
    with TestClient(app_module.app) as c:
        yield app_module, c


@pytest.fixture()
def client(test_app, db):
    app_module, c = test_app
    app_module.app.dependency_overrides[app_module.get_db] = lambda: db
    c.cookies.clear()
    yield c
    app_module.app.dependency_overrides.clear()


def _login(client, matricula: str, senha: str = "Senha-123!"):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text


def _csrf_headers(client) -> dict:
    return {"x-csrf-token": client.cookies.get("prisma_csrf")}


def test_gestor_revoga_sessao_de_usuario_da_propria_gestora(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-REV1")
    alvo = Usuario(matricula="ALVO-REV1", nome="Alvo", senha_hash=auth.hash_senha("Senha-123!"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(alvo)
    db.flush()
    assert alvo.sessao_revogada_em is None

    _login(client, "GESTOR-REV1")
    resp = client.post(f"/usuarios/{alvo.id}/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(alvo)
    assert alvo.sessao_revogada_em is not None


def test_analista_nao_pode_revogar_sessao(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-REV2")
    analista = Usuario(matricula="ANALISTA-REV2", nome="Analista", senha_hash=auth.hash_senha("Senha-123!"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(analista)
    db.flush()
    _login(client, "ANALISTA-REV2")
    resp = client.post(f"/usuarios/{analista.id}/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_gestor_nao_revoga_sessao_de_usuario_de_outra_gestora(client, db):
    _, admin_a = _gestora_com_usuario(db, matricula="GESTOR-REV3", gestora_nome="Gestora REV A")
    _, alvo_b = _gestora_com_usuario(db, matricula="GESTOR-REV4", gestora_nome="Gestora REV B")
    _login(client, "GESTOR-REV3")
    resp = client.post(f"/usuarios/{alvo_b.id}/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_revogar_usuario_inexistente_retorna_404(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-REV5")
    _login(client, "GESTOR-REV5")
    resp = client.post("/usuarios/999999/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 404


def test_revogacao_sem_csrf_e_rejeitada(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-REV6")
    alvo = Usuario(matricula="ALVO-REV6", nome="Alvo", senha_hash=auth.hash_senha("Senha-123!"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(alvo)
    db.flush()
    _login(client, "GESTOR-REV6")
    resp = client.post(f"/usuarios/{alvo.id}/revogar-sessao")
    assert resp.status_code == 403


def test_sessao_revogada_derruba_o_proximo_acesso_do_alvo(test_app, client, db):
    """Integração ponta a ponta: o alvo loga (pega um cookie próprio), o
    gestor revoga, e o cookie antigo do alvo passa a ser rejeitado."""
    app_module, _ = test_app
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-REV7")
    alvo = Usuario(matricula="ALVO-REV7", nome="Alvo", senha_hash=auth.hash_senha("Senha-123!"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(alvo)
    db.flush()

    client_alvo = TestClient(app_module.app)
    csrf_alvo = client_alvo.get("/auth/csrf").json()["csrf_token"]
    resp = client_alvo.post("/auth/login", json={"matricula": "ALVO-REV7", "senha": "Senha-123!"},
                            headers={"x-csrf-token": csrf_alvo})
    assert resp.status_code == 200
    assert client_alvo.get("/auth/me").status_code == 200

    time.sleep(1.1)

    _login(client, "GESTOR-REV7")
    resp = client.post(f"/usuarios/{alvo.id}/revogar-sessao", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    resp = client_alvo.get("/auth/me")
    assert resp.status_code == 401
