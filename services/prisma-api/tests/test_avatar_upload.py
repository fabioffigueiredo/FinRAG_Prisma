"""Upload de avatar (Stage 8): magic bytes (não Content-Type), cap de 2MB,
sobrescreve o arquivo anterior, exige autenticação + CSRF.
"""
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import auth
from db.models import Base, Gestora, Papel, Usuario
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")

PNG_VALIDO = b"\x89PNG\r\n\x1a\n" + b"0" * 50
JPEG_VALIDO = b"\xff\xd8\xff" + b"0" * 50
WEBP_VALIDO = b"RIFF" + b"0000" + b"WEBP" + b"0" * 50
NAO_IMAGEM = b"isso nao e uma imagem, so texto puro" * 3


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


@pytest.fixture(autouse=True)
def _limpar_arquivos_de_avatar():
    """A rota grava em disco de verdade (fora da transação SAVEPOINT do
    banco) — precisa limpar manualmente, senão os arquivos de teste ficam."""
    yield
    diretorio = Path(__file__).resolve().parents[1] / "static" / "avatars"
    for caminho in diretorio.glob("AVT-*"):
        caminho.unlink()


def _usuario_teste(db, matricula="AVT-001") -> Usuario:
    gestora = Gestora(nome=f"Gestora {matricula}")
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Fulano Avatar", senha_hash=auth.hash_senha("Senha-123!"),
                      papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return usuario


def _login(client, matricula: str, senha: str = "Senha-123!"):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text


def _csrf_headers(client) -> dict:
    return {"x-csrf-token": client.cookies.get("prisma_csrf")}


def test_upload_png_valido(client, db):
    _usuario_teste(db, matricula="AVT-001")
    _login(client, "AVT-001")
    resp = client.post(
        "/auth/avatar",
        headers=_csrf_headers(client),
        files={"arquivo": ("foto.png", io.BytesIO(PNG_VALIDO), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["avatar_url"] == "/static/avatars/AVT-001.png"

    alvo = db.query(Usuario).filter(Usuario.matricula == "AVT-001").one()
    assert alvo.avatar_url == "/static/avatars/AVT-001.png"


def test_upload_jpeg_valido(client, db):
    _usuario_teste(db, matricula="AVT-002")
    _login(client, "AVT-002")
    resp = client.post(
        "/auth/avatar",
        headers=_csrf_headers(client),
        files={"arquivo": ("foto.jpg", io.BytesIO(JPEG_VALIDO), "image/jpeg")},
    )
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "/static/avatars/AVT-002.jpg"


def test_upload_webp_valido(client, db):
    _usuario_teste(db, matricula="AVT-003")
    _login(client, "AVT-003")
    resp = client.post(
        "/auth/avatar",
        headers=_csrf_headers(client),
        files={"arquivo": ("foto.webp", io.BytesIO(WEBP_VALIDO), "image/webp")},
    )
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "/static/avatars/AVT-003.webp"


def test_upload_sem_assinatura_de_imagem_e_rejeitado(client, db):
    """Confere magic bytes, não Content-Type — um .txt disfarçado de PNG."""
    _usuario_teste(db, matricula="AVT-004")
    _login(client, "AVT-004")
    resp = client.post(
        "/auth/avatar",
        headers=_csrf_headers(client),
        files={"arquivo": ("fake.png", io.BytesIO(NAO_IMAGEM), "image/png")},
    )
    assert resp.status_code == 422


def test_upload_maior_que_2mb_e_rejeitado(client, db):
    _usuario_teste(db, matricula="AVT-005")
    _login(client, "AVT-005")
    grande = b"\x89PNG\r\n\x1a\n" + b"0" * (2 * 1024 * 1024 + 100)
    resp = client.post(
        "/auth/avatar",
        headers=_csrf_headers(client),
        files={"arquivo": ("grande.png", io.BytesIO(grande), "image/png")},
    )
    assert resp.status_code == 413


def test_reupload_sobrescreve_extensao_anterior(client, db):
    _usuario_teste(db, matricula="AVT-006")
    _login(client, "AVT-006")
    client.post("/auth/avatar", headers=_csrf_headers(client),
               files={"arquivo": ("foto.png", io.BytesIO(PNG_VALIDO), "image/png")})
    resp = client.post("/auth/avatar", headers=_csrf_headers(client),
                       files={"arquivo": ("foto.jpg", io.BytesIO(JPEG_VALIDO), "image/jpeg")})
    assert resp.status_code == 200
    assert resp.json()["avatar_url"] == "/static/avatars/AVT-006.jpg"

    diretorio = Path(__file__).resolve().parents[1] / "static" / "avatars"
    assert not (diretorio / "AVT-006.png").exists()
    assert (diretorio / "AVT-006.jpg").exists()


def test_upload_com_csrf_mas_sem_sessao_e_rejeitado(client, db):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post(
        "/auth/avatar",
        headers={"x-csrf-token": csrf},
        files={"arquivo": ("foto.png", io.BytesIO(PNG_VALIDO), "image/png")},
    )
    assert resp.status_code == 401


def test_upload_com_sessao_mas_sem_csrf_e_rejeitado(client, db):
    _usuario_teste(db, matricula="AVT-007")
    _login(client, "AVT-007")
    resp = client.post(
        "/auth/avatar",
        files={"arquivo": ("foto.png", io.BytesIO(PNG_VALIDO), "image/png")},
    )
    assert resp.status_code == 403
