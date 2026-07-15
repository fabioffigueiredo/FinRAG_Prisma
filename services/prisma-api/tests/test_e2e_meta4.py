"""Meta 4 — critério de pronto, ponta a ponta: duas gestoras fictícias,
cada uma com usuário e fundos próprios, login real (JWT) e isolamento
comprovado através das ROTAS de verdade (não só a camada de repositório).
"""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app as app_module
import auth
from app import LoginReq, listar_fundos, login
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
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()
    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


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


def test_login_e_isolamento_de_fundos_entre_duas_gestoras(db):
    _duas_gestoras_com_fundos(db)

    resp_a = login(LoginReq(matricula="ANALISTA-A", senha="senha-a-123"), db=db)
    resp_b = login(LoginReq(matricula="ANALISTA-B", senha="senha-b-123"), db=db)

    payload_a = auth.decodificar_token(resp_a.token)
    payload_b = auth.decodificar_token(resp_b.token)
    usuario_atual_a = auth.UsuarioAtual(matricula=payload_a["sub"], nome=payload_a["nome"],
                                       papel=payload_a["papel"], gestora_id=payload_a["gestora_id"])
    usuario_atual_b = auth.UsuarioAtual(matricula=payload_b["sub"], nome=payload_b["nome"],
                                       papel=payload_b["papel"], gestora_id=payload_b["gestora_id"])

    fundos_a = listar_fundos(usuario=usuario_atual_a, db=db)
    fundos_b = listar_fundos(usuario=usuario_atual_b, db=db)

    codigos_a = {f["codigo"] for f in fundos_a["fundos"]}
    codigos_b = {f["codigo"] for f in fundos_b["fundos"]}

    assert codigos_a == {"E2E-A1"}
    assert codigos_b == {"E2E-B1"}
    assert "E2E-B1" not in codigos_a
    assert "E2E-A1" not in codigos_b


def test_login_com_senha_errada_nao_gera_token(db):
    _duas_gestoras_com_fundos(db)
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as exc_info:
        login(LoginReq(matricula="ANALISTA-A", senha="senha-errada"), db=db)
    assert exc_info.value.status_code == 401
