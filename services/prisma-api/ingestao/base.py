"""Protocolos de conector plugável (Meta 1).

Decidi expressar isso como `Protocol` (tipagem estrutural), não classe-base
abstrata, porque notei que assim o `SimuladorConnector` de hoje e um futuro
conector real (Sinqia/DW, Bloomberg) não precisam herdar de nada em comum —
só implementar os mesmos métodos. Troca de simulado pra real vira troca de
qual objeto é injetado em `db/repo.py`, não uma reescrita.

Os DTOs são dataclasses simples (não os modelos SQLAlchemy) de propósito:
um conector real não necessariamente lê do nosso Postgres — ele traduz dados
de outro sistema pra essa forma comum.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol


@dataclass(frozen=True)
class FundoDTO:
    codigo: str
    nome: str
    cnpj: str
    classe: str
    benchmark_padrao: str


@dataclass(frozen=True)
class PeriodoDTO:
    label: str
    data_inicio: date
    data_fim: date


@dataclass(frozen=True)
class PontoSerieDTO:
    data: date
    cota: float
    bench: float


@dataclass(frozen=True)
class ContribuicaoDTO:
    dimensao: str
    chave_dimensao: str
    contribuicao_pp: float
    peso_medio: float
    cor: str = "neutral"


@dataclass(frozen=True)
class EstrategiaClassificacaoDTO:
    """Uma linha de classificação — a chave natural é (fundo, ativo), nunca
    texto livre (ver docstring de `db/models.py`)."""
    ativo_codigo: str
    ativo_nome: str
    ativo_tipo: str
    nome_estrategia: str


@dataclass(frozen=True)
class VarPontoDTO:
    data: date
    classe: str
    valor_pct_nav: float


@dataclass(frozen=True)
class BenchmarkPesoDTO:
    benchmark_nome: str
    peso: float


class FundoConnector(Protocol):
    def listar_fundos(self) -> list[FundoDTO]: ...
    def obter_periodos(self, fundo_codigo: str) -> list[PeriodoDTO]: ...
    def obter_serie_diaria(self, fundo_codigo: str, periodo_label: str) -> list[PontoSerieDTO]: ...
    def obter_contribuicoes(
        self, fundo_codigo: str, periodo_label: str, dimensao: str
    ) -> list[ContribuicaoDTO]: ...


class EstrategiaConnector(Protocol):
    def obter_classificacao_atual(self, fundo_codigo: str) -> list[EstrategiaClassificacaoDTO]: ...

    def aplicar_classificacao(
        self, fundo_codigo: str, linhas: list[EstrategiaClassificacaoDTO], matricula: str
    ) -> str:
        """Aplica uma nova classificação (import); retorna o hash SHA-256 do evento."""
        ...


class VarConnector(Protocol):
    def obter_var(self, fundo_codigo: str, data_inicio: date, data_fim: date) -> list[VarPontoDTO]: ...


class BenchmarkConnector(Protocol):
    def listar_benchmarks(self) -> list[str]: ...
    def obter_pesos(self, fundo_codigo: str, periodo_label: str) -> list[BenchmarkPesoDTO]: ...


class ConectorCompleto(FundoConnector, EstrategiaConnector, VarConnector, BenchmarkConnector, Protocol):
    """Um conector que implementa os 4 protocolos ao mesmo tempo — é o que
    `db/repo.py::popular_do_conector` espera receber (hoje o
    `SimuladorConnector`, amanhã um conector real)."""
