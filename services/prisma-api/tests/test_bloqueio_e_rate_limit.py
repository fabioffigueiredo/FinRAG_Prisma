"""Lockout de conta (5 tentativas -> 15 min) e rate limiting (5/min) em
/auth/login (Stage 6, hardening).

Lockout é testado no nível de função (`auth.autenticar`), sem passar pelo
HTTP/rate limit — os dois mecanismos usam o MESMO limiar (5), então testar
o lockout via HTTP faria a 6ª chamada colidir com o rate limit (que vence,
por estar na camada de fora) e o teste nunca observaria o 401 de bloqueio
de verdade. Rate limiting é testado à parte, via TestClient.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

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


def _usuario_teste(db, matricula="LOCK-001", senha="Senha-123!") -> Usuario:
    gestora = Gestora(nome=f"Gestora {matricula}")
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Fulano Bloqueio", senha_hash=auth.hash_senha(senha),
                      papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return usuario


# --- lockout (nível de função, sem HTTP) ------------------------------------

def test_quinta_falha_bloqueia_a_conta(db):
    usuario = _usuario_teste(db, matricula="LOCK-001")
    for _ in range(4):
        assert auth.autenticar(db, "LOCK-001", "senha-errada") is None
    assert usuario.bloqueado_ate is None

    assert auth.autenticar(db, "LOCK-001", "senha-errada") is None
    assert usuario.bloqueado_ate is not None
    assert usuario.bloqueado_ate > datetime.now(timezone.utc)


def test_conta_bloqueada_rejeita_ate_a_senha_correta(db):
    """Bloqueado nem chega a checar a senha — a mensagem/comportamento é
    idêntico ao de senha errada (ASVS: revelar bloqueio é enumeração)."""
    usuario = _usuario_teste(db, matricula="LOCK-002")
    for _ in range(5):
        auth.autenticar(db, "LOCK-002", "senha-errada")
    assert usuario.bloqueado_ate is not None

    assert auth.autenticar(db, "LOCK-002", "Senha-123!") is None


def test_sucesso_zera_contador_de_tentativas(db):
    usuario = _usuario_teste(db, matricula="LOCK-003")
    for _ in range(3):
        auth.autenticar(db, "LOCK-003", "senha-errada")
    assert usuario.tentativas_falhas == 3

    assert auth.autenticar(db, "LOCK-003", "Senha-123!") is not None
    assert usuario.tentativas_falhas == 0
    assert usuario.bloqueado_ate is None


def test_matricula_inexistente_nunca_bloqueia_nada(db):
    for _ in range(10):
        assert auth.autenticar(db, "NAO-EXISTE-LOCK", "qualquer") is None


# --- rate limiting (HTTP, via TestClient) -----------------------------------

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


def _tentar_login(client, matricula, senha):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    return client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})


def test_sexta_chamada_a_login_em_um_minuto_leva_429(client, db):
    _usuario_teste(db, matricula="RATE-001")
    for _ in range(5):
        resp = _tentar_login(client, "RATE-001", "senha-errada")
        assert resp.status_code == 401
    resp = _tentar_login(client, "RATE-001", "senha-errada")
    assert resp.status_code == 429
