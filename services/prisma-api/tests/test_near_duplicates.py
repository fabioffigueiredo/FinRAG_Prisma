"""Meta 3: assistente de classificação — detecta ativo com nome PARECIDO a
um já cadastrado antes do import, atacando a mesma armadilha do
NOME_LONGO_TITULO texto-livre do sistema real (erro de digitação cria
duplicata em vez de reaproveitar o ativo existente)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from db.models import Ativo, Base
from db.repo import detectar_near_duplicates_ativo
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


def _semear_ativo(db, codigo: str, nome: str):
    db.add(Ativo(codigo=codigo, nome=nome, tipo="titulo"))
    db.flush()


def test_detecta_erro_de_digitacao_como_near_duplicate(db):
    _semear_ativo(db, "ATV-1", "Debênture Infra Energia 2031")
    achados = detectar_near_duplicates_ativo(db, "Debenture Infra Energia 2031")  # sem acento
    assert len(achados) == 1
    assert achados[0]["ativo_codigo"] == "ATV-1"
    assert achados[0]["similaridade"] > 0.9


def test_nao_flagra_ativos_genuinamente_diferentes(db):
    _semear_ativo(db, "ATV-2", "NTN-B 2030")
    achados = detectar_near_duplicates_ativo(db, "Ação Setor Bancário ON")
    assert achados == []


def test_exclui_o_proprio_codigo_da_comparacao(db):
    _semear_ativo(db, "ATV-3", "CDB Banco Médio 2027")
    achados = detectar_near_duplicates_ativo(db, "CDB Banco Médio 2027", excluir_codigo="ATV-3")
    assert achados == []


def test_nome_identico_sob_codigo_diferente_e_o_caso_mais_suspeito(db):
    _semear_ativo(db, "ATV-4", "FIDC Recebíveis Comerciais")
    achados = detectar_near_duplicates_ativo(db, "FIDC Recebíveis Comerciais")
    assert achados[0]["similaridade"] == 1.0
