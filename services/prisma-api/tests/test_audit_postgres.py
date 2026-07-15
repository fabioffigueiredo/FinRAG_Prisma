"""Meta 4: trilha de auditoria persistida no Postgres (não mais só JSONL).

`_registrar_no_banco` faz `commit()` de verdade (não dá pra usar o padrão de
transação-com-rollback dos outros testes de banco) — por isso aqui eu limpo
a tabela antes de cada teste em vez de rodar dentro de uma savepoint.
"""
import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

import audit
import db.session as db_session
from db.models import AuditoriaEvento, Base
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def test_session_local(engine, monkeypatch):
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as db:
        db.execute(delete(AuditoriaEvento))
        db.commit()
    monkeypatch.setattr(db_session, "SessionLocal", SessionLocal)
    monkeypatch.setattr(audit, "_FORCAR_ARQUIVO", False)
    return SessionLocal


def test_registrar_persiste_no_postgres(test_session_local):
    audit.registrar(rota="/perguntar", fundo="ALFA-33", pergunta="teste postgres?",
                    backend="mock", latency_ms=42, fontes=["doc.md"], bloqueados=[],
                    resposta="resposta qualquer")
    regs = audit.ler(limit=10)
    assert len(regs) == 1
    assert regs[0]["rota"] == "/perguntar"
    assert regs[0]["fundo"] == "ALFA-33"
    assert "resposta" not in regs[0]  # só o hash, nunca o texto em claro
    assert regs[0]["resposta_hash"]


def test_ler_ordena_mais_recente_primeiro_e_respeita_limite(test_session_local):
    for i in range(5):
        audit.registrar(rota="/narrativa", fundo="ALFA-33", pergunta=f"p{i}",
                        backend="mock", latency_ms=i, fontes=[], bloqueados=[], resposta=str(i))
    regs = audit.ler(limit=3)
    assert [r["pergunta"] for r in regs] == ["p4", "p3", "p2"]


def test_extra_e_mesclado_no_registro_lido(test_session_local):
    audit.registrar(rota="/perguntar", fundo="ALFA-33", pergunta="x", backend="mock",
                    latency_ms=1, fontes=[], bloqueados=[], resposta="y",
                    extra={"injecao": True})
    regs = audit.ler(limit=1)
    assert regs[0]["injecao"] is True
