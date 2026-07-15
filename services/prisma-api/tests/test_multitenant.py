"""Meta 4 — critério de pronto: duas gestoras fictícias em tenants
separados, cada uma só vendo seus próprios fundos."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Base, Fundo, Gestora
from db.repo import listar_fundos_da_gestora
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


def test_gestora_a_nao_ve_fundos_da_gestora_b(db):
    gestora_a = Gestora(nome="Gestora A")
    gestora_b = Gestora(nome="Gestora B")
    db.add_all([gestora_a, gestora_b])
    db.flush()

    db.add_all([
        Fundo(codigo="MT-A1", nome="Fundo A1", cnpj="00.000.000/0001-00",
             classe="Teste", benchmark_padrao="CDI", gestora_id=gestora_a.id),
        Fundo(codigo="MT-A2", nome="Fundo A2", cnpj="00.000.000/0002-00",
             classe="Teste", benchmark_padrao="CDI", gestora_id=gestora_a.id),
        Fundo(codigo="MT-B1", nome="Fundo B1", cnpj="00.000.000/0003-00",
             classe="Teste", benchmark_padrao="CDI", gestora_id=gestora_b.id),
    ])
    db.flush()

    fundos_a = listar_fundos_da_gestora(db, gestora_a.id)
    fundos_b = listar_fundos_da_gestora(db, gestora_b.id)

    assert {f.codigo for f in fundos_a} == {"MT-A1", "MT-A2"}
    assert {f.codigo for f in fundos_b} == {"MT-B1"}
    assert "MT-B1" not in {f.codigo for f in fundos_a}
    assert "MT-A1" not in {f.codigo for f in fundos_b}


def test_gestora_sem_fundo_recebe_lista_vazia_nao_erro(db):
    gestora_vazia = Gestora(nome="Gestora Vazia")
    db.add(gestora_vazia)
    db.flush()
    assert listar_fundos_da_gestora(db, gestora_vazia.id) == []
