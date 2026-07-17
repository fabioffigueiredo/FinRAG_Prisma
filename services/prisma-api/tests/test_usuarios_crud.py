"""CRUD de usuários (Stage 3): RBAC, isolamento de tenant, CSRF em mutação.

Nota de infraestrutura de teste: as rotas de escrita (`POST`/`PATCH /usuarios`)
chamam `db.commit()` de verdade (precisa persistir em produção). A fixture
`db` de `test_auth.py`/`test_csrf.py` só usa `db.flush()` implicitamente (via
os repositórios) e depende de `trans.rollback()` no teardown pra isolamento —
um `db.commit()` dentro da rota terminaria essa transação externa cedo e
vazaria dado pro `prisma_test` permanentemente. Aqui a fixture usa o padrão
oficial do SQLAlchemy "join a session into an external transaction" (SAVEPOINT
+ listener que reabre o savepoint a cada commit da aplicação) — a transação
REAL de fora nunca é finalizada até o rollback do teardown, então commits da
rota só liberam o savepoint, sem persistir nada de verdade.
"""
import pytest
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


def _gestora_com_usuario(db, matricula="ADMIN-A", papel=Papel.GESTOR, gestora_nome="Gestora A") -> tuple[Gestora, Usuario]:
    gestora = Gestora(nome=gestora_nome)
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Admin da Gestora", senha_hash=auth.hash_senha("senha123"),
                      papel=papel, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return gestora, usuario


@pytest.fixture(scope="module")
def test_app():
    """TestClient reaproveitado pelo módulo inteiro — o startup real (índice
    RAG) só roda 1x, não 1x por teste (~8s cada, senão)."""
    import app as app_module
    with TestClient(app_module.app) as c:
        yield app_module, c


@pytest.fixture()
def client(test_app, db):
    app_module, c = test_app
    app_module.app.dependency_overrides[app_module.get_db] = lambda: db
    yield c
    app_module.app.dependency_overrides.clear()


def _login(client, matricula: str, senha: str = "senha123") -> None:
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text


def _csrf_headers(client) -> dict:
    return {"x-csrf-token": client.cookies.get("prisma_csrf")}


# --- RBAC -----------------------------------------------------------------

def test_analista_nao_pode_listar_usuarios(client, db):
    _gestora_com_usuario(db, matricula="ANALISTA-1", papel=Papel.ANALISTA)
    _login(client, "ANALISTA-1")
    resp = client.get("/usuarios")
    assert resp.status_code == 403


def test_gestor_pode_listar_usuarios_da_propria_gestora(client, db):
    gestora, admin = _gestora_com_usuario(db, matricula="GESTOR-1")
    db.add(Usuario(matricula="ANALISTA-2", nome="Outro", senha_hash=auth.hash_senha("x"),
                   papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True))
    db.flush()
    _login(client, "GESTOR-1")
    resp = client.get("/usuarios")
    assert resp.status_code == 200
    matriculas = {u["matricula"] for u in resp.json()["usuarios"]}
    assert matriculas == {"GESTOR-1", "ANALISTA-2"}
    # nunca serializa a senha
    assert all("senha_hash" not in u and "senha" not in u for u in resp.json()["usuarios"])


# --- isolamento de tenant ---------------------------------------------------

def test_gestor_nao_ve_usuarios_de_outra_gestora(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-B1", gestora_nome="Gestora B")
    _gestora_com_usuario(db, matricula="GESTOR-C1", gestora_nome="Gestora C")
    _login(client, "GESTOR-B1")
    resp = client.get("/usuarios")
    matriculas = {u["matricula"] for u in resp.json()["usuarios"]}
    assert matriculas == {"GESTOR-B1"}


def test_gestor_nao_pode_editar_usuario_de_outra_gestora(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-D1", gestora_nome="Gestora D")
    _, alvo = _gestora_com_usuario(db, matricula="ANALISTA-E1", papel=Papel.ANALISTA, gestora_nome="Gestora E")
    _login(client, "GESTOR-D1")
    resp = client.patch(f"/usuarios/{alvo.id}", json={"nome": "Tentativa de invasão"},
                        headers=_csrf_headers(client))
    assert resp.status_code == 403


# --- criação -----------------------------------------------------------------

def test_gestor_cria_usuario_na_propria_gestora(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-F1", gestora_nome="Gestora F")
    _login(client, "GESTOR-F1")
    resp = client.post("/usuarios", json={
        "matricula": "NOVO-1", "nome": "Fulano Novo", "papel": "analista", "senha": "Senha-Nova-123!",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    assert corpo["matricula"] == "NOVO-1"
    assert corpo["gestora_id"] == gestora.id
    assert "senha" not in corpo and "senha_hash" not in corpo


def test_criar_usuario_gestora_id_do_payload_e_ignorado(client, db):
    """Mesmo se um cliente malicioso mandar gestora_id no payload, o campo
    nem existe em CriarUsuarioReq — Pydantic descarta silenciosamente."""
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-G1", gestora_nome="Gestora G")
    outra, _ = _gestora_com_usuario(db, matricula="GESTOR-H1", gestora_nome="Gestora H")
    _login(client, "GESTOR-G1")
    resp = client.post("/usuarios", json={
        "matricula": "NOVO-2", "nome": "Fulano", "papel": "analista", "senha": "Senha-123!",
        "gestora_id": outra.id,
    }, headers=_csrf_headers(client))
    assert resp.status_code == 201
    assert resp.json()["gestora_id"] == gestora.id


def test_criar_usuario_matricula_duplicada_retorna_409(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-I1", gestora_nome="Gestora I")
    _login(client, "GESTOR-I1")
    resp = client.post("/usuarios", json={
        "matricula": "GESTOR-I1", "nome": "Duplicado", "papel": "analista", "senha": "Senha-123!",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 409


def test_criar_usuario_sem_csrf_e_rejeitado(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-J1", gestora_nome="Gestora J")
    _login(client, "GESTOR-J1")
    resp = client.post("/usuarios", json={
        "matricula": "NOVO-3", "nome": "Fulano", "papel": "analista", "senha": "Senha-123!",
    })
    assert resp.status_code == 403


def test_criar_usuario_papel_invalido_retorna_422(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-K1", gestora_nome="Gestora K")
    _login(client, "GESTOR-K1")
    resp = client.post("/usuarios", json={
        "matricula": "NOVO-4", "nome": "Fulano", "papel": "super-admin", "senha": "Senha-123!",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 422


# --- atualização -----------------------------------------------------------

def test_gestor_atualiza_papel_de_usuario_da_propria_gestora(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="GESTOR-L1", gestora_nome="Gestora L")
    alvo = Usuario(matricula="ANALISTA-L1", nome="Fulano", senha_hash=auth.hash_senha("x"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(alvo)
    db.flush()
    _login(client, "GESTOR-L1")
    resp = client.patch(f"/usuarios/{alvo.id}", json={"papel": "compliance"}, headers=_csrf_headers(client))
    assert resp.status_code == 200
    assert resp.json()["papel"] == "compliance"


def test_usuario_nao_pode_se_autodesativar(client, db):
    _gestora_com_usuario(db, matricula="GESTOR-M1", gestora_nome="Gestora M")
    _login(client, "GESTOR-M1")
    resp = client.get("/usuarios")
    meu_id = next(u["id"] for u in resp.json()["usuarios"] if u["matricula"] == "GESTOR-M1")
    resp = client.patch(f"/usuarios/{meu_id}", json={"ativo": False}, headers=_csrf_headers(client))
    assert resp.status_code == 400
