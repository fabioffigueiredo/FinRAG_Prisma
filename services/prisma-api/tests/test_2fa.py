"""2FA TOTP (Stage 9): enrollment em duas etapas (iniciar/confirmar) e login
em duas etapas para gestor/compliance. Round-trip real com `pyotp.TOTP`.
"""
import pyotp
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


@pytest.fixture(scope="module")
def test_app():
    import app as app_module
    with TestClient(app_module.app) as c:
        yield app_module, c


@pytest.fixture()
def client(test_app, db):
    """`c` é o mesmo TestClient reaproveitado pelo módulo inteiro (startup
    roda 1x) — limpa os cookies a cada teste, senão um login de um teste
    anterior vaza (ex.: prisma_session de um teste sem 2FA aparecendo num
    teste que assume que só prisma_pre2fa deveria existir)."""
    app_module, c = test_app
    app_module.app.dependency_overrides[app_module.get_db] = lambda: db
    c.cookies.clear()
    yield c
    app_module.app.dependency_overrides.clear()


def _gestora_com_usuario(db, matricula="G2FA-000", papel=Papel.GESTOR, gestora_nome="Gestora 2FA") -> tuple[Gestora, Usuario]:
    gestora = Gestora(nome=gestora_nome)
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Fulano 2FA", senha_hash=auth.hash_senha("Senha-123!"),
                      papel=papel, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return gestora, usuario


def _login(client, matricula: str, senha: str = "Senha-123!"):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    return client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})


def _csrf_headers(client) -> dict:
    return {"x-csrf-token": client.cookies.get("prisma_csrf")}


# --- enrollment --------------------------------------------------------------

def test_iniciar_enrollment_gera_segredo_sem_ativar(client, db):
    _gestora_com_usuario(db, matricula="G2FA-001")
    assert _login(client, "G2FA-001").status_code == 200

    resp = client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["otpauth_uri"].startswith("otpauth://totp/")
    assert len(corpo["qr_base64"]) > 100

    alvo = db.query(Usuario).filter(Usuario.matricula == "G2FA-001").one()
    assert alvo.totp_secret is None
    assert alvo.totp_secret_pendente is not None
    assert alvo.totp_ativado is False


def test_analista_nao_pode_iniciar_2fa(client, db):
    _gestora_com_usuario(db, matricula="A2FA-001", papel=Papel.ANALISTA)
    _login(client, "A2FA-001")
    resp = client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_confirmar_com_codigo_real_ativa_2fa(client, db):
    _gestora_com_usuario(db, matricula="G2FA-002")
    _login(client, "G2FA-002")
    resp = client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    secret = pyotp.parse_uri(resp.json()["otpauth_uri"]).secret

    codigo = pyotp.TOTP(secret).now()
    resp = client.post("/auth/2fa/confirmar", json={"codigo": codigo}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    alvo = db.query(Usuario).filter(Usuario.matricula == "G2FA-002").one()
    assert alvo.totp_ativado is True
    assert alvo.totp_secret == secret
    assert alvo.totp_secret_pendente is None


def test_confirmar_com_codigo_errado_nao_ativa(client, db):
    _gestora_com_usuario(db, matricula="G2FA-003")
    _login(client, "G2FA-003")
    client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    resp = client.post("/auth/2fa/confirmar", json={"codigo": "000000"}, headers=_csrf_headers(client))
    assert resp.status_code == 401

    alvo = db.query(Usuario).filter(Usuario.matricula == "G2FA-003").one()
    assert alvo.totp_ativado is False


def test_confirmar_sem_enrollment_em_andamento_retorna_400(client, db):
    _gestora_com_usuario(db, matricula="G2FA-004")
    _login(client, "G2FA-004")
    resp = client.post("/auth/2fa/confirmar", json={"codigo": "123456"}, headers=_csrf_headers(client))
    assert resp.status_code == 400


# --- login em duas etapas ----------------------------------------------------

def test_login_de_gestor_com_2fa_ativo_exige_segunda_etapa(client, db):
    _, usuario = _gestora_com_usuario(db, matricula="G2FA-005")
    secret = pyotp.random_base32()
    usuario.totp_secret = secret
    usuario.totp_ativado = True
    db.flush()

    resp = _login(client, "G2FA-005")
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["requer_2fa"] is True
    assert corpo["token"] is None
    assert "prisma_pre2fa" in client.cookies
    assert "prisma_session" not in client.cookies

    # cookie pendente de 2FA não abre nenhuma rota protegida
    assert client.get("/auth/me").status_code == 401


def test_verificar_com_codigo_certo_completa_o_login(client, db):
    _, usuario = _gestora_com_usuario(db, matricula="G2FA-006")
    secret = pyotp.random_base32()
    usuario.totp_secret = secret
    usuario.totp_ativado = True
    db.flush()

    resp = _login(client, "G2FA-006")
    assert resp.json()["requer_2fa"] is True

    codigo = pyotp.TOTP(secret).now()
    resp = client.post("/auth/2fa/verificar", json={"codigo": codigo}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert corpo["requer_2fa"] is False
    assert corpo["token"] is not None
    assert "prisma_session" in client.cookies

    resp = client.get("/auth/me")
    assert resp.status_code == 200
    assert resp.json()["matricula"] == "G2FA-006"


def test_verificar_com_codigo_errado_e_rejeitado(client, db):
    _, usuario = _gestora_com_usuario(db, matricula="G2FA-007")
    secret = pyotp.random_base32()
    usuario.totp_secret = secret
    usuario.totp_ativado = True
    db.flush()

    _login(client, "G2FA-007")
    resp = client.post("/auth/2fa/verificar", json={"codigo": "000000"}, headers=_csrf_headers(client))
    assert resp.status_code == 401


def test_verificar_sem_cookie_pre2fa_e_rejeitado(client, db):
    _gestora_com_usuario(db, matricula="G2FA-008")
    resp = client.post("/auth/2fa/verificar", json={"codigo": "123456"})
    assert resp.status_code in (401, 403)  # 403 se cair no CSRF antes; 401 se passar e faltar o cookie


def test_analista_com_totp_ativado_no_banco_ainda_loga_em_uma_etapa(client, db):
    """2FA é regra de papel, não só de totp_ativado — cobre o caso de um
    usuário que foi rebaixado depois de já ter configurado 2FA."""
    _, usuario = _gestora_com_usuario(db, matricula="A2FA-002", papel=Papel.ANALISTA)
    usuario.totp_secret = pyotp.random_base32()
    usuario.totp_ativado = True
    db.flush()

    resp = _login(client, "A2FA-002")
    assert resp.status_code == 200
    assert resp.json()["requer_2fa"] is False
    assert resp.json()["token"] is not None


def test_rate_limit_de_5_por_minuto_em_verificar_2fa(client, db):
    _, usuario = _gestora_com_usuario(db, matricula="G2FA-009")
    usuario.totp_secret = pyotp.random_base32()
    usuario.totp_ativado = True
    db.flush()

    _login(client, "G2FA-009")
    for _ in range(5):
        resp = client.post("/auth/2fa/verificar", json={"codigo": "000000"}, headers=_csrf_headers(client))
        assert resp.status_code == 401
    resp = client.post("/auth/2fa/verificar", json={"codigo": "000000"}, headers=_csrf_headers(client))
    assert resp.status_code == 429


# --- reset de 2FA (perda de dispositivo) ------------------------------------

def test_gestor_reseta_2fa_de_outro_usuario(client, db):
    gestora, admin = _gestora_com_usuario(db, matricula="G2FA-ADMIN1")
    alvo = Usuario(matricula="G2FA-ALVO1", nome="Alvo", senha_hash=auth.hash_senha("Senha-123!"),
                  papel=Papel.GESTOR, gestora_id=gestora.id, ativo=True,
                  totp_secret=pyotp.random_base32(), totp_ativado=True)
    db.add(alvo)
    db.flush()

    _login(client, "G2FA-ADMIN1")
    resp = client.post(f"/usuarios/{alvo.id}/resetar-2fa", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(alvo)
    assert alvo.totp_secret is None
    assert alvo.totp_ativado is False


def test_nao_pode_resetar_o_proprio_2fa(client, db):
    # sem 2FA ativo no próprio ator de propósito — login em uma etapa só,
    # o bloqueio de autoreset independe do estado de 2FA de quem chama.
    _, admin = _gestora_com_usuario(db, matricula="G2FA-ADMIN2")

    _login(client, "G2FA-ADMIN2")
    resp = client.post(f"/usuarios/{admin.id}/resetar-2fa", headers=_csrf_headers(client))
    assert resp.status_code == 400


def test_analista_nao_pode_resetar_2fa(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G2FA-ADMIN3")
    alvo = Usuario(matricula="G2FA-ALVO3", nome="Alvo", senha_hash=auth.hash_senha("Senha-123!"),
                  papel=Papel.GESTOR, gestora_id=gestora.id, ativo=True,
                  totp_secret=pyotp.random_base32(), totp_ativado=True)
    analista = Usuario(matricula="A2FA-ADMIN3", nome="Analista", senha_hash=auth.hash_senha("Senha-123!"),
                      papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add_all([alvo, analista])
    db.flush()

    _login(client, "A2FA-ADMIN3")
    resp = client.post(f"/usuarios/{alvo.id}/resetar-2fa", headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_resetar_2fa_de_usuario_de_outra_gestora_e_rejeitado(client, db):
    _, admin_a = _gestora_com_usuario(db, matricula="G2FA-ADMIN4", gestora_nome="Gestora 2FA A")
    _, alvo_b = _gestora_com_usuario(db, matricula="G2FA-ALVO4", gestora_nome="Gestora 2FA B")
    alvo_b.totp_secret = pyotp.random_base32()
    alvo_b.totp_ativado = True
    db.flush()

    _login(client, "G2FA-ADMIN4")
    resp = client.post(f"/usuarios/{alvo_b.id}/resetar-2fa", headers=_csrf_headers(client))
    assert resp.status_code == 403
