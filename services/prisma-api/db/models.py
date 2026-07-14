"""Schema Postgres da Meta 1 (fundação de dados simulada).

Decidi modelar a classificação de estratégia como SCD2 (EstrategiaVersao +
LogAlteracaoEstrategia) porque notei, lendo o sistema real (`prf_estrategias`,
DIM_ESTT/LOG_IMP_ESTT), que é exatamente esse o padrão que resolve o problema
central de lá — só que aqui a chave natural é (fundo, ativo), NUNCA texto
livre. O sistema real usa uma "chave quádrupla" que inclui `NOME_LONGO_TITULO`
(texto livre) — é a causa raiz do problema #1 do diagnóstico (erro de
digitação quebra o join). Aqui o nome do ativo é um ATRIBUTO de `Ativo`, não
parte de nenhuma chave/constraint.
"""
from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Dimensao(str, enum.Enum):
    """As 8 dimensões de "Foco da Análise" do sistema real — no POC atual
    (Meta 0) só `estrategia` está povoada; a Meta 1 povoa as 8."""
    ESTRATEGIA = "estrategia"
    GRUPO_CONTABIL = "grupo_contabil"
    SUPERGRUPO = "supergrupo"
    PRIVADOS = "privados"
    RENDA_VARIAVEL = "renda_variavel"
    RENDA_FIXA = "renda_fixa"
    VENCIMENTO = "vencimento"
    ATIVOS = "ativos"


class ClasseVar(str, enum.Enum):
    """As 7 classes de VaR do `azure_bloomberg` real."""
    JUROS = "juros"
    INFLACAO = "inflacao"
    CREDITO = "credito"
    EQUITY = "equity"
    FX = "fx"
    COMMODITY = "commodity"
    TOTAL = "total"


class Fundo(Base):
    __tablename__ = "fundo"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(40))
    classe: Mapped[str] = mapped_column(String(100))
    benchmark_padrao: Mapped[str] = mapped_column(String(40))

    periodos: Mapped[list["Periodo"]] = relationship(back_populates="fundo")


class Periodo(Base):
    """Um trimestre/intervalo com dado carregado para um fundo. A Meta 0 só
    tinha 1 por fundo; a Meta 1 exige ≥4 (histórico multi-período)."""
    __tablename__ = "periodo"
    __table_args__ = (UniqueConstraint("fundo_codigo", "label", name="uq_periodo_fundo_label"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    label: Mapped[str] = mapped_column(String(60))  # ex.: "2º trimestre 2026 (abr–jun)"
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)

    fundo: Mapped["Fundo"] = relationship(back_populates="periodos")


class Ativo(Base):
    """Nome do ativo é um ATRIBUTO aqui, nunca parte de uma chave/constraint
    — a correção deliberada do anti-padrão `NOME_LONGO_TITULO` do sistema
    real (ver docstring do módulo)."""
    __tablename__ = "ativo"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(60))
    nome: Mapped[str] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(String(60))  # ex.: debênture, ação, NTN-B...


class EstrategiaVersao(Base):
    """SCD2: a chave natural é (fundo_codigo, ativo_id) — sem texto livre.
    Só pode existir 1 versão `vigente=True` por (fundo, ativo) por vez; o
    índice parcial abaixo garante isso no banco, não só na aplicação."""
    __tablename__ = "estrategia_versao"
    __table_args__ = (
        Index(
            "uq_estrategia_versao_vigente",
            "fundo_codigo", "ativo_id",
            unique=True,
            postgresql_where=text("vigente = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    ativo_id: Mapped[int] = mapped_column(ForeignKey("ativo.id"))
    nome_estrategia: Mapped[str] = mapped_column(String(120))
    dt_inicio_vigencia: Mapped[date] = mapped_column(Date)
    dt_fim_vigencia: Mapped["date | None"] = mapped_column(Date, nullable=True)
    vigente: Mapped[bool] = mapped_column(Boolean, default=True)
    matricula_responsavel: Mapped[str] = mapped_column(String(20))
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    logs: Mapped[list["LogAlteracaoEstrategia"]] = relationship(back_populates="estrategia_versao")


class LogAlteracaoEstrategia(Base):
    """Append-only — nunca UPDATE/DELETE. Espelha `LOG_IMP_ESTT` do sistema
    real (hash SHA-256 + metadados do evento), mas sem herdar a chave com
    texto livre."""
    __tablename__ = "log_alteracao_estrategia"

    id: Mapped[int] = mapped_column(primary_key=True)
    estrategia_versao_id: Mapped[int] = mapped_column(ForeignKey("estrategia_versao.id"))
    hash_sha256: Mapped[str] = mapped_column(String(64))
    tipo_alteracao: Mapped[str] = mapped_column(String(20))  # import_csv | export_csv | manual
    matricula: Mapped[str] = mapped_column(String(20))
    payload_json: Mapped[str] = mapped_column(String)  # JSON serializado (metadados do evento)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    estrategia_versao: Mapped["EstrategiaVersao"] = relationship(back_populates="logs")


class Contribuicao(Base):
    """Contribuição de uma "bucket" de uma dimensão (ex.: estratégia
    "Crédito Privado") ao retorno do fundo NO PERÍODO — não é diária (a
    série diária de cota vive em `SerieDiaria`)."""
    __tablename__ = "contribuicao"

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodo.id"))
    dimensao: Mapped[Dimensao] = mapped_column(Enum(Dimensao, name="dimensao_enum"))
    chave_dimensao: Mapped[str] = mapped_column(String(120))  # ex.: "Crédito Privado"
    contribuicao_pp: Mapped[float] = mapped_column(Float)
    peso_medio: Mapped[float] = mapped_column(Float)
    cor: Mapped[str] = mapped_column(String(20), default="neutral")


class SerieDiaria(Base):
    """Série diária de cota × benchmark dentro de um período (pro gráfico
    de linha do copiloto)."""
    __tablename__ = "serie_diaria"
    __table_args__ = (UniqueConstraint("fundo_codigo", "periodo_id", "data", name="uq_serie_dia"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodo.id"))
    data: Mapped[date] = mapped_column(Date)
    cota: Mapped[float] = mapped_column(Float)
    bench: Mapped[float] = mapped_column(Float)


class VarClasseDiaria(Base):
    """VaR por classe e por dia — espelha o Parquet que o `azure_bloomberg`
    real produz (% do NAV), aqui gerado sinteticamente."""
    __tablename__ = "var_classe_diaria"
    __table_args__ = (UniqueConstraint("fundo_codigo", "data", "classe", name="uq_var_dia_classe"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    data: Mapped[date] = mapped_column(Date)
    classe: Mapped[ClasseVar] = mapped_column(Enum(ClasseVar, name="classe_var_enum"))
    valor_pct_nav: Mapped[float] = mapped_column(Float)


class Benchmark(Base):
    __tablename__ = "benchmark"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), unique=True)
    descricao: Mapped[str] = mapped_column(String(200), default="")


class BenchmarkPeso(Base):
    """Peso de um benchmark dentro do benchmark composto/customizado de um
    fundo num período — versionado (só 1 `ativo=True` por fundo+periodo+
    benchmark), pra existir governança que o sistema real admite não ter."""
    __tablename__ = "benchmark_peso"

    id: Mapped[int] = mapped_column(primary_key=True)
    fundo_codigo: Mapped[str] = mapped_column(ForeignKey("fundo.codigo"))
    periodo_id: Mapped[int] = mapped_column(ForeignKey("periodo.id"))
    benchmark_id: Mapped[int] = mapped_column(ForeignKey("benchmark.id"))
    peso: Mapped[float] = mapped_column(Float)  # 0-1
    dt_versao: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
