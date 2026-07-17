"""Meta 4 — critério de pronto, ponta a ponta: duas gestoras fictícias,
cada uma com usuário e fundos próprios, login real (JWT) e isolamento
comprovado através das ROTAS de verdade (não só a camada de repositório).

Login vira uma chamada TestClient de verdade (não mais função direta) desde
que /auth/login passou a exigir `request: Request` (rate limiting, Meta 5) —
ver .claude/skills/prisma-test-commit-isolation/.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import auth
from db.models import Base, Fundo, Gestora, Papel, Usuario
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
    yield c
    app_module.app.dependency_overrides.clear()


def _duas_gestoras_com_fundos(db):
    gestora_a = Gestora(nome="Gestora Aurora")
    gestora_b = Gestora(nome="Gestora Boreal")
    db.add_all([gestora_a, gestora_b])
    db.flush()

    db.add_all([
        Fundo(codigo="E2E-A1", nome="Fundo Aurora 1", cnpj="00.000.000/0001-00",
             classe="Teste", benchmark_padrao="CDI", gestora_id=gestora_a.id),
        Fundo(codigo="E2E-B1", nome="Fundo Boreal 1", cnpj="00.000.000/0002-00",
             classe="Teste", benchmark_padrao="CDI", gestora_id=gestora_b.id),
    ])
    usuario_a = Usuario(matricula="ANALISTA-A", nome="Analista da Aurora",
                       senha_hash=auth.hash_senha("senha-a-123"),
                       papel=Papel.ANALISTA, gestora_id=gestora_a.id)
    usuario_b = Usuario(matricula="ANALISTA-B", nome="Analista da Boreal",
                       senha_hash=auth.hash_senha("senha-b-123"),
                       papel=Papel.ANALISTA, gestora_id=gestora_b.id)
    db.add_all([usuario_a, usuario_b])
    db.flush()
    return usuario_a, usuario_b


def _login(client, matricula: str, senha: str) -> None:
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text


def test_login_e_isolamento_de_fundos_entre_duas_gestoras(client, db):
    _duas_gestoras_com_fundos(db)

    _login(client, "ANALISTA-A", "senha-a-123")
    codigos_a = {f["codigo"] for f in client.get("/fundos").json()["fundos"]}

    _login(client, "ANALISTA-B", "senha-b-123")
    codigos_b = {f["codigo"] for f in client.get("/fundos").json()["fundos"]}

    assert codigos_a == {"E2E-A1"}
    assert codigos_b == {"E2E-B1"}
    assert "E2E-B1" not in codigos_a
    assert "E2E-A1" not in codigos_b


def test_login_com_senha_errada_nao_gera_token(client, db):
    _duas_gestoras_com_fundos(db)
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": "ANALISTA-A", "senha": "senha-errada"},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 401
