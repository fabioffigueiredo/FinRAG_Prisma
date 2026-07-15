"""Meta 4: hash de senha, JWT e RBAC."""
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

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
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()
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
