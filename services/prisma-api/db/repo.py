"""Repositório de acesso a dado (Meta 1).

`popular_do_conector` traduz qualquer `FundoConnector`+`EstrategiaConnector`+
`VarConnector`+`BenchmarkConnector` (hoje o `SimuladorConnector`, amanhã um
conector real) pro schema Postgres. `aplicar_classificacao_estrategia` é a
função mais crítica do módulo — é o SCD2 de verdade: fecha a versão vigente
anterior e abre uma nova, com hash de auditoria, tudo numa transação.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestao.base import ConectorCompleto

from .models import (
    Ativo,
    Benchmark,
    BenchmarkPeso,
    Contribuicao,
    EstrategiaVersao,
    Fundo,
    LogAlteracaoEstrategia,
    Periodo,
    SerieDiaria,
    VarClasseDiaria,
)

DIMENSOES = [
    "estrategia", "grupo_contabil", "supergrupo", "privados",
    "renda_variavel", "renda_fixa", "vencimento", "ativos",
]


def _hash_classificacao(fundo_codigo: str, ativo_codigo: str, nome_estrategia: str,
                        matricula: str, criado_em: datetime) -> str:
    """Hash determinístico do evento de classificação — mesmo princípio do
    `generate_payload_hash` do sistema real (SHA-256 sobre o payload
    canônico), mas sem nenhum campo de texto livre na composição da CHAVE
    (o hash em si pode incluir o nome só como metadado de auditoria)."""
    payload = f"{fundo_codigo}|{ativo_codigo}|{nome_estrategia}|{matricula}|{criado_em.isoformat()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _obter_ou_criar_ativo(db: Session, codigo: str, nome: str, tipo: str) -> Ativo:
    ativo = db.scalar(select(Ativo).where(Ativo.codigo == codigo))
    if ativo is None:
        ativo = Ativo(codigo=codigo, nome=nome, tipo=tipo)
        db.add(ativo)
        db.flush()
    return ativo


def aplicar_classificacao_estrategia(
    db: Session, *, fundo_codigo: str, ativo_codigo: str, ativo_nome: str,
    ativo_tipo: str, nome_estrategia: str, matricula: str,
    hoje: date | None = None,
) -> LogAlteracaoEstrategia:
    """SCD2: fecha a versão vigente anterior (se houver) e abre uma nova.

    A chave natural é (fundo_codigo, ativo_id) — nunca texto livre. Se a
    estratégia pedida for igual à vigente, ainda assim registra o evento no
    log (idempotência de dado não é a mesma coisa que idempotência de
    auditoria: cada import é um evento).
    """
    hoje = hoje or date.today()
    ativo = _obter_ou_criar_ativo(db, ativo_codigo, ativo_nome, ativo_tipo)

    vigente = db.scalar(
        select(EstrategiaVersao).where(
            EstrategiaVersao.fundo_codigo == fundo_codigo,
            EstrategiaVersao.ativo_id == ativo.id,
            EstrategiaVersao.vigente.is_(True),
        )
    )
    if vigente is not None:
        vigente.vigente = False
        vigente.dt_fim_vigencia = hoje

    nova = EstrategiaVersao(
        fundo_codigo=fundo_codigo, ativo_id=ativo.id, nome_estrategia=nome_estrategia,
        dt_inicio_vigencia=hoje, dt_fim_vigencia=None, vigente=True,
        matricula_responsavel=matricula,
    )
    db.add(nova)
    db.flush()  # garante nova.id antes do log/hash

    criado_em = datetime.now(timezone.utc)
    hash_evento = _hash_classificacao(fundo_codigo, ativo_codigo, nome_estrategia, matricula, criado_em)
    log = LogAlteracaoEstrategia(
        estrategia_versao_id=nova.id, hash_sha256=hash_evento, tipo_alteracao="import_csv",
        matricula=matricula,
        payload_json=json.dumps({"fundo": fundo_codigo, "ativo": ativo_codigo,
                                 "estrategia": nome_estrategia}, ensure_ascii=False),
    )
    db.add(log)
    return log


def popular_do_conector(
    db: Session,
    conector: ConectorCompleto,
    matricula: str = "SIMULADOR",
) -> None:
    """Popula o Postgres inteiro a partir de um conector (hoje o
    `SimuladorConnector`). Idempotente o bastante pra rodar em cima de um
    banco vazio (não faz upsert de período/fundo já existente)."""
    for fundo_dto in conector.listar_fundos():
        fundo = db.get(Fundo, fundo_dto.codigo) or Fundo(codigo=fundo_dto.codigo)
        fundo.nome = fundo_dto.nome
        fundo.cnpj = fundo_dto.cnpj
        fundo.classe = fundo_dto.classe
        fundo.benchmark_padrao = fundo_dto.benchmark_padrao
        db.add(fundo)
        db.flush()

        periodos_db: dict[str, Periodo] = {}
        for periodo_dto in conector.obter_periodos(fundo_dto.codigo):
            periodo = Periodo(fundo_codigo=fundo.codigo, label=periodo_dto.label,
                             data_inicio=periodo_dto.data_inicio, data_fim=periodo_dto.data_fim)
            db.add(periodo)
            db.flush()
            periodos_db[periodo_dto.label] = periodo

            for ponto in conector.obter_serie_diaria(fundo.codigo, periodo_dto.label):
                db.add(SerieDiaria(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                   data=ponto.data, cota=ponto.cota, bench=ponto.bench))

            for dimensao in DIMENSOES:
                for c in conector.obter_contribuicoes(fundo.codigo, periodo_dto.label, dimensao):
                    db.add(Contribuicao(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                        dimensao=dimensao, chave_dimensao=c.chave_dimensao,
                                        contribuicao_pp=c.contribuicao_pp, peso_medio=c.peso_medio,
                                        cor=c.cor))

            for var_ponto in conector.obter_var(fundo.codigo, periodo_dto.data_inicio, periodo_dto.data_fim):
                db.add(VarClasseDiaria(fundo_codigo=fundo.codigo, data=var_ponto.data,
                                       classe=var_ponto.classe, valor_pct_nav=var_ponto.valor_pct_nav))

            for peso_dto in conector.obter_pesos(fundo.codigo, periodo_dto.label):
                bench = db.scalar(select(Benchmark).where(Benchmark.nome == peso_dto.benchmark_nome))
                if bench is None:
                    bench = Benchmark(nome=peso_dto.benchmark_nome)
                    db.add(bench)
                    db.flush()
                db.add(BenchmarkPeso(fundo_codigo=fundo.codigo, periodo_id=periodo.id,
                                     benchmark_id=bench.id, peso=peso_dto.peso))

        for classificacao in conector.obter_classificacao_atual(fundo.codigo):
            aplicar_classificacao_estrategia(
                db, fundo_codigo=fundo.codigo, ativo_codigo=classificacao.ativo_codigo,
                ativo_nome=classificacao.ativo_nome, ativo_tipo=classificacao.ativo_tipo,
                nome_estrategia=classificacao.nome_estrategia, matricula=matricula,
            )
    db.commit()
