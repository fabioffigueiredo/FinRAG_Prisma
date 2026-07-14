"""Testes da Meta 1 — SCD2, hash de auditoria, e a garantia de que a chave
de estratégia NUNCA é texto livre (o anti-padrão do sistema real).

Precisam de um Postgres rodando (docker-compose.dev.yml) com o banco
`prisma_test` criado — se não tiver, esses testes falham na conexão (são os
únicos do backend que dependem de um serviço externo)."""
from datetime import date

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from db.models import Base, EstrategiaVersao, Fundo
from db.repo import _hash_classificacao, aplicar_classificacao_estrategia
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")


@pytest.fixture(scope="module")
def engine():
    from sqlalchemy import create_engine
    eng = create_engine(TEST_DB_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine) -> Session:
    connection = engine.connect()
    trans = connection.begin()
    SessionLocal = sessionmaker(bind=connection, future=True)
    session = SessionLocal()
    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


def _fundo_teste(db: Session, codigo: str) -> Fundo:
    fundo = Fundo(codigo=codigo, nome=f"Fundo {codigo}", cnpj="00.000.000/0000-00",
                 classe="Teste", benchmark_padrao="CDI")
    db.add(fundo)
    db.flush()
    return fundo


def _vigentes(db: Session, fundo_codigo: str, ativo_id: int) -> list[EstrategiaVersao]:
    return list(db.scalars(
        select(EstrategiaVersao).where(
            EstrategiaVersao.fundo_codigo == fundo_codigo,
            EstrategiaVersao.ativo_id == ativo_id,
            EstrategiaVersao.vigente.is_(True),
        )
    ))


def test_scd2_fecha_versao_anterior_ao_reclassificar(db):
    _fundo_teste(db, "TESTE-01")
    aplicar_classificacao_estrategia(
        db, fundo_codigo="TESTE-01", ativo_codigo="ATV-1", ativo_nome="Debênture Teste",
        ativo_tipo="titulo", nome_estrategia="Crédito Privado", matricula="M001",
    )
    db.flush()
    ativo_id = db.scalar(select(EstrategiaVersao.ativo_id).where(
        EstrategiaVersao.fundo_codigo == "TESTE-01"))

    # 1ª versão vigente
    assert len(_vigentes(db, "TESTE-01", ativo_id)) == 1
    primeira = _vigentes(db, "TESTE-01", ativo_id)[0]

    # reclassifica o MESMO fundo+ativo pra outra estratégia
    aplicar_classificacao_estrategia(
        db, fundo_codigo="TESTE-01", ativo_codigo="ATV-1", ativo_nome="Debênture Teste",
        ativo_tipo="titulo", nome_estrategia="Juros Brasil", matricula="M002",
    )
    db.flush()

    vigentes = _vigentes(db, "TESTE-01", ativo_id)
    assert len(vigentes) == 1  # só 1 vigente, nunca 2
    assert vigentes[0].nome_estrategia == "Juros Brasil"

    db.refresh(primeira)
    assert primeira.vigente is False
    assert primeira.dt_fim_vigencia is not None


def test_cada_reclassificacao_gera_log_de_auditoria(db):
    _fundo_teste(db, "TESTE-02")
    log1 = aplicar_classificacao_estrategia(
        db, fundo_codigo="TESTE-02", ativo_codigo="ATV-2", ativo_nome="CDB Teste",
        ativo_tipo="titulo", nome_estrategia="Crédito Privado", matricula="M001",
    )
    log2 = aplicar_classificacao_estrategia(
        db, fundo_codigo="TESTE-02", ativo_codigo="ATV-2", ativo_nome="CDB Teste",
        ativo_tipo="titulo", nome_estrategia="Caixa e Over", matricula="M001",
    )
    db.flush()
    assert log1.hash_sha256 != log2.hash_sha256
    assert log1.tipo_alteracao == "import_csv"


def test_hash_e_deterministico_para_mesmo_payload():
    from datetime import datetime, timezone
    quando = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    a = _hash_classificacao("ALFA-33", "ATV-1", "Crédito Privado", "M001", quando)
    b = _hash_classificacao("ALFA-33", "ATV-1", "Crédito Privado", "M001", quando)
    assert a == b


def test_hash_muda_se_qualquer_campo_mudar():
    from datetime import datetime, timezone
    quando = datetime(2026, 7, 14, 12, 0, 0, tzinfo=timezone.utc)
    base = _hash_classificacao("ALFA-33", "ATV-1", "Crédito Privado", "M001", quando)
    outra_estrategia = _hash_classificacao("ALFA-33", "ATV-1", "Juros Brasil", "M001", quando)
    assert base != outra_estrategia


def test_chave_de_estrategia_nao_e_baseada_em_texto_livre(db):
    """A constraint de unicidade é sobre (fundo_codigo, ativo_id) — NUNCA
    sobre nome_estrategia ou qualquer texto livre. Prova: inserir duas
    versões vigentes do MESMO (fundo, ativo) só falha por causa da chave
    (fundo, ativo), independente de terem nomes de estratégia diferentes."""
    _fundo_teste(db, "TESTE-03")
    aplicar_classificacao_estrategia(
        db, fundo_codigo="TESTE-03", ativo_codigo="ATV-3", ativo_nome="NTN-B Teste",
        ativo_tipo="titulo", nome_estrategia="Juros Brasil", matricula="M001",
    )
    db.flush()
    ativo_id = db.scalar(select(EstrategiaVersao.ativo_id).where(
        EstrategiaVersao.fundo_codigo == "TESTE-03"))

    # insere OUTRA versão vigente do mesmo (fundo, ativo) manualmente,
    # sem passar pelo repo (que fecharia a anterior) — deve violar a
    # constraint no banco, mesmo com nome_estrategia totalmente diferente.
    duplicata = EstrategiaVersao(
        fundo_codigo="TESTE-03", ativo_id=ativo_id, nome_estrategia="Bolsa Brasil (nome livre diferente)",
        dt_inicio_vigencia=date.today(), vigente=True,
        matricula_responsavel="M999",
    )
    db.add(duplicata)
    with pytest.raises(IntegrityError):
        db.flush()
