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


class Papel(str, enum.Enum):
    """Os 3 papéis de RBAC da Meta 4 — espelha os perfis reais que um
    sistema desse porte precisa (analista opera, gestor decide, compliance
    audita), não uma lista genérica de permissões."""
    ANALISTA = "analista"
    GESTOR = "gestor"
    COMPLIANCE = "compliance"


class StatusCadastro(str, enum.Enum):
    """Estado do ciclo de vida de cadastro — só o autocadastro público nasce
    `pendente`; usuário criado pelo admin (com ou sem convite) já nasce
    `aprovado`, nunca passa pela fila de aprovação."""
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    REJEITADO = "rejeitado"


class Gestora(Base):
    """O "tenant" da Meta 4 — cada gestora só vê seus próprios fundos.
    Decidi isolar por FK simples (não schema-per-tenant) porque é o
    suficiente pra provar a separação com poucas gestoras/fundos; schema
    separado só valeria a pena em escala bem maior."""
    __tablename__ = "gestora"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), unique=True)

    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="gestora")


class Usuario(Base):
    __tablename__ = "usuario"

    id: Mapped[int] = mapped_column(primary_key=True)
    matricula: Mapped[str] = mapped_column(String(20), unique=True)
    nome: Mapped[str] = mapped_column(String(120))
    senha_hash: Mapped[str] = mapped_column(String(200))
    papel: Mapped[Papel] = mapped_column(Enum(Papel, name="papel_enum"))
    gestora_id: Mapped[int] = mapped_column(ForeignKey("gestora.id"))
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)

    # Conta do usuário (hardening estilo instituição financeira, ver docs/SEGURANCA.md)
    email: Mapped["str | None"] = mapped_column(String(160), nullable=True)
    telefone: Mapped["str | None"] = mapped_column(String(30), nullable=True)
    avatar_url: Mapped["str | None"] = mapped_column(String(300), nullable=True)

    # 2FA (TOTP) — segredo em texto plano é uma simplificação de POC
    # documentada (ver docs/SEGURANCA.md); produção real deveria criptografar
    # em repouso (ex.: cryptography.fernet + chave de secrets manager).
    totp_secret: Mapped["str | None"] = mapped_column(String(64), nullable=True)
    totp_ativado: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))

    # Segurança de senha/sessão
    trocar_senha_no_proximo_login: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=text("false")
    )
    tentativas_falhas: Mapped[int] = mapped_column(default=0, server_default=text("0"))
    bloqueado_ate: Mapped["datetime | None"] = mapped_column(DateTime(timezone=True), nullable=True)
    sessao_revogada_em: Mapped["datetime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    # Cadastro/convite — usuários pré-existentes e os criados direto pelo
    # admin nascem "aprovado" (server_default); só o autocadastro público
    # nasce "pendente". convite_token é o mesmo link pra ambos os fluxos
    # (aprovação de autocadastro E convite direto do gestor) — nunca uma
    # senha por e-mail, ver docs/SEGURANCA.md.
    status_cadastro: Mapped[str] = mapped_column(
        Enum(StatusCadastro, name="status_cadastro_enum"),
        default=StatusCadastro.APROVADO, server_default=text("'APROVADO'"),
    )
    convite_token: Mapped["str | None"] = mapped_column(String(64), nullable=True, unique=True)
    convite_expira_em: Mapped["datetime | None"] = mapped_column(DateTime(timezone=True), nullable=True)

    gestora: Mapped["Gestora"] = relationship(back_populates="usuarios")


class Fundo(Base):
    __tablename__ = "fundo"

    codigo: Mapped[str] = mapped_column(String(20), primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cnpj: Mapped[str] = mapped_column(String(40))
    classe: Mapped[str] = mapped_column(String(100))
    benchmark_padrao: Mapped[str] = mapped_column(String(40))
    # nullable porque o dado sintético da Meta 1 foi criado antes da Meta 4
    # existir — um fundo sem gestora é tratado como "sem tenant" (visível só
    # a quem não tem isolamento, ex. scripts internos), nunca exposto via API.
    gestora_id: Mapped["int | None"] = mapped_column(ForeignKey("gestora.id"), nullable=True)

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


class AuditoriaEvento(Base):
    """Meta 4 — substitui o JSONL local de `audit.py` por uma trilha
    consultável no banco. Guardo só o HASH da resposta (nunca o texto em
    claro), mesma decisão de privacidade que o JSONL já tinha."""
    __tablename__ = "auditoria_evento"

    id: Mapped[int] = mapped_column(primary_key=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rota: Mapped[str] = mapped_column(String(60))
    fundo: Mapped[str] = mapped_column(String(20))
    pergunta: Mapped[str] = mapped_column(String)
    backend: Mapped[str] = mapped_column(String(40))
    latency_ms: Mapped[int] = mapped_column()
    fontes_json: Mapped[str] = mapped_column(String, default="[]")
    bloqueados_json: Mapped[str] = mapped_column(String, default="[]")
    resposta_hash: Mapped[str] = mapped_column(String(16))
    extra_json: Mapped["str | None"] = mapped_column(String, nullable=True)
    # Ator do evento — necessário pro "histórico de acessos" filtrar por
    # usuário; None em eventos que não têm um usuário logado associado
    # (ex.: tentativa de login com matrícula inexistente).
    ator_matricula: Mapped["str | None"] = mapped_column(String(20), nullable=True, index=True)


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
