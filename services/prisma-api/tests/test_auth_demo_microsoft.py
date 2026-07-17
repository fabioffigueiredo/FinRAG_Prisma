"""Login "Microsoft" simulado (Stage 10) — NÃO é OAuth/OIDC real, não fala
com Azure AD. Get-or-create idempotente da mesma conta demo fixa,
papel=analista de propósito (mantém o clique único simples, nunca aciona 2FA).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

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


def _gestora(db, nome="Gestora Microsoft Demo") -> Gestora:
    gestora = Gestora(nome=nome)
    db.add(gestora)
    db.flush()
    return gestora


def _csrf_headers(client) -> dict:
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    return {"x-csrf-token": csrf}


def test_primeiro_clique_cria_a_conta_demo(client, db):
    _gestora(db)
    resp = client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["papel"] == "analista"
    assert corpo["requer_2fa"] is False
    assert corpo["token"] is not None

    from app import PRISMA_DEMO_MATRICULA
    criado = db.scalar(select(Usuario).where(Usuario.matricula == PRISMA_DEMO_MATRICULA))
    assert criado is not None
    assert criado.papel == Papel.ANALISTA


def test_segundo_clique_reaproveita_a_mesma_conta_sem_duplicar(client, db):
    _gestora(db)
    client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
    client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))

    from app import PRISMA_DEMO_MATRICULA
    linhas = list(db.scalars(select(Usuario).where(Usuario.matricula == PRISMA_DEMO_MATRICULA)))
    assert len(linhas) == 1


def test_login_demo_emite_sessao_real_direto(client, db):
    _gestora(db)
    resp = client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
    assert resp.status_code == 200
    assert "prisma_session" in client.cookies

    resp = client.get("/auth/me")
    assert resp.status_code == 200

    from app import PRISMA_DEMO_MATRICULA
    assert resp.json()["matricula"] == PRISMA_DEMO_MATRICULA


def test_sem_gestora_cadastrada_retorna_503(client, db):
    resp = client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
    assert resp.status_code == 503


def test_sem_csrf_e_rejeitado(client, db):
    _gestora(db)
    resp = client.post("/auth/login-microsoft-demo")
    assert resp.status_code == 403


def test_rate_limit_de_5_por_minuto(client, db):
    _gestora(db)
    for _ in range(5):
        resp = client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
        assert resp.status_code == 200
    resp = client.post("/auth/login-microsoft-demo", headers=_csrf_headers(client))
    assert resp.status_code == 429
