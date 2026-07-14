"""Critério de pronto da Meta 2: o motor de reconciliação bate com os
números REAIS já semeados no Postgres pela Meta 1 (não um fixture — lê o
banco de dev de verdade, `docker-compose.dev.yml` + `scripts/seed_db.py`)."""
import pytest
from sqlalchemy import select

from atribuicao.reconciliacao import validar_batimento
from db.models import Contribuicao, Dimensao, Periodo, SerieDiaria
from db.session import SessionLocal


@pytest.fixture()
def db():
    session = SessionLocal()
    yield session
    session.close()


def _periodos_semeados(db) -> list[Periodo]:
    periodos = list(db.scalars(select(Periodo)))
    if not periodos:
        pytest.skip("banco de dev vazio — rode scripts/seed_db.py primeiro")
    return periodos


def _soma_contribuicoes(db, fundo_codigo: str, periodo_id: int, dimensao: Dimensao) -> float:
    return sum(db.scalars(
        select(Contribuicao.contribuicao_pp).where(
            Contribuicao.fundo_codigo == fundo_codigo,
            Contribuicao.periodo_id == periodo_id,
            Contribuicao.dimensao == dimensao,
        )
    ))


def _ultimo_ponto_serie(db, fundo_codigo: str, periodo_id: int) -> SerieDiaria | None:
    return db.scalar(
        select(SerieDiaria).where(
            SerieDiaria.fundo_codigo == fundo_codigo,
            SerieDiaria.periodo_id == periodo_id,
        ).order_by(SerieDiaria.data.desc()).limit(1)
    )


def test_soma_de_contribuicoes_por_estrategia_bate_com_retorno_da_cota(db):
    periodos = _periodos_semeados(db)
    falhas = []
    for periodo in periodos:
        soma_pp = _soma_contribuicoes(db, periodo.fundo_codigo, periodo.id, Dimensao.ESTRATEGIA)
        ultimo_ponto = _ultimo_ponto_serie(db, periodo.fundo_codigo, periodo.id)
        if ultimo_ponto is None:
            continue
        resultado = validar_batimento(
            soma_contribuicoes_pp=soma_pp, retorno_cota_pp=ultimo_ponto.cota,
            tolerancia_pp=0.05, contexto=f"{periodo.fundo_codigo} · {periodo.label}",
        )
        if not resultado.ok:
            falhas.append(resultado.mensagem)

    assert not falhas, "\n".join(falhas)


def test_todas_as_8_dimensoes_tambem_batem_por_periodo(db):
    """As outras 7 dimensões (não só estratégia) também devem bater —
    é exatamente o gap #1 do diagnóstico crítico (só estratégia existia)."""
    periodos = _periodos_semeados(db)
    falhas = []
    for periodo in periodos[:4]:  # amostra: 1 fundo completo (4 períodos)
        for dimensao in Dimensao:
            soma_pp = _soma_contribuicoes(db, periodo.fundo_codigo, periodo.id, dimensao)
            ultimo_ponto = _ultimo_ponto_serie(db, periodo.fundo_codigo, periodo.id)
            if ultimo_ponto is None:
                continue
            resultado = validar_batimento(
                soma_contribuicoes_pp=soma_pp, retorno_cota_pp=ultimo_ponto.cota,
                tolerancia_pp=0.05,
                contexto=f"{periodo.fundo_codigo} · {periodo.label} · {dimensao.value}",
            )
            if not resultado.ok:
                falhas.append(resultado.mensagem)

    assert not falhas, "\n".join(falhas)
