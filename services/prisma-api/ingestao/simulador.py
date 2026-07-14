"""SimuladorConnector (Meta 1) — implementa os 4 protocolos de `base.py` com
dado 100% sintético, rico o bastante pra exercitar tudo que falta hoje:
multi-período, 8 dimensões, VaR por classe, benchmark composto.

Decidi ANCORAR no seed já existente (`data/seed/fundo_*.json`, o trimestre
"2T26" atual) em vez de reescrever os 7 perfis de fundo do zero, porque notei
que eles já são consistentes (soma de contribuições bate) e são a base do
que a UI já mostra hoje — sintetizo os 3 trimestres anteriores e as 7
dimensões que faltam A PARTIR desse ancoral, não do zero.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from .base import (
    BenchmarkPesoDTO,
    ContribuicaoDTO,
    EstrategiaClassificacaoDTO,
    FundoDTO,
    PeriodoDTO,
    PontoSerieDTO,
    VarPontoDTO,
)

SEED_DIR = Path(__file__).resolve().parents[3] / "data" / "seed"

# As 4 janelas trimestrais simuladas — a mais recente ("2T26") é a âncora
# real do seed; as 3 anteriores são sintetizadas a partir dela.
PERIODOS = [
    ("3º trimestre 2025 (jul–set)", date(2025, 7, 1), date(2025, 9, 30)),
    ("4º trimestre 2025 (out–dez)", date(2025, 10, 1), date(2025, 12, 31)),
    ("1º trimestre 2026 (jan–mar)", date(2026, 1, 1), date(2026, 3, 31)),
    ("2º trimestre 2026 (abr–jun)", date(2026, 4, 1), date(2026, 6, 30)),
]
PERIODO_ANCORA = PERIODOS[-1][0]

# Buckets genéricos pras 7 dimensões que hoje não existem no seed — não são
# uma cópia da taxonomia real (que é proprietária/numérica), só uma forma
# plausível o bastante pra exercitar o copiloto/UI nas 8 lentes.
BUCKETS_POR_DIMENSAO: dict[str, list[str]] = {
    "grupo_contabil": ["Aplicações Financeiras", "Despesas e Encargos", "Outros Ativos/Passivos"],
    "supergrupo": ["Renda Fixa", "Renda Variável", "Derivativos", "Caixa e Disponibilidades"],
    "privados": ["Emissor Privado A", "Emissor Privado B", "Emissor Privado C"],
    "renda_variavel": ["Ações Large Cap", "Ações Small Cap", "ETFs e Fundos de Índice"],
    "renda_fixa": ["Pré-fixado", "Pós-fixado (CDI)", "Inflação (IPCA+)"],
    "vencimento": ["Curto Prazo (<1a)", "Médio Prazo (1-3a)", "Longo Prazo (>3a)"],
}

BENCHMARK_UNIVERSO = ["CDI", "IBOVESPA", "IMA-B", "IPCA+", "SELIC", "DÓLAR (PTAX)"]

_CLASSES_VAR = ["juros", "inflacao", "credito", "equity", "fx", "commodity"]


@dataclass
class _FundoSeed:
    """Dado do seed original (2T26), carregado uma vez do JSON."""
    codigo: str
    nome: str
    cnpj: str
    classe: str
    benchmark_padrao: str
    retorno_cota: float
    retorno_bench: float
    vol_anual: float
    estrategias: list[dict]
    ativos: list[dict]
    serie_diaria: list[dict]


def _carregar_seeds() -> dict[str, _FundoSeed]:
    out: dict[str, _FundoSeed] = {}
    for arq in sorted(SEED_DIR.glob("fundo_*.json")):
        d = json.loads(arq.read_text(encoding="utf-8"))
        f, r = d["fundo"], d["resumo"]
        out[f["codigo"]] = _FundoSeed(
            codigo=f["codigo"], nome=f["nome"], cnpj=f["cnpj"], classe=f["classe"],
            benchmark_padrao=f["benchmark"], retorno_cota=r["retorno_cota"],
            retorno_bench=r["retorno_bench"], vol_anual=r["vol_anual"],
            estrategias=d["estrategias"], ativos=d["ativos"], serie_diaria=d["serie_diaria"],
        )
    return out


def _fator_trimestre(rnd: random.Random) -> float:
    """Fator de tendência plausível pra um trimestre histórico: entre 0.4x e
    1.6x do retorno âncora, podendo inverter sinal ocasionalmente (~15%)."""
    fator = rnd.uniform(0.4, 1.6)
    if rnd.random() < 0.15:
        fator = -fator * 0.5
    return fator


def _redistribuir(total_pp: float, n: int, rnd: random.Random) -> list[float]:
    """Divide `total_pp` em `n` partes com pesos aleatórios que somam
    exatamente o total (mesmo truque de ajuste-no-fim do gen_seed.py)."""
    pesos = [rnd.uniform(0.2, 1.0) for _ in range(n)]
    soma_pesos = sum(pesos)
    partes = [total_pp * p / soma_pesos for p in pesos]
    ajuste = total_pp - sum(partes)
    partes[-1] += ajuste
    return [round(p, 4) for p in partes]


def _dias_uteis(inicio: date, fim: date) -> list[date]:
    out, d = [], inicio
    while d <= fim:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


class SimuladorConnector:
    """Implementa FundoConnector + EstrategiaConnector + VarConnector +
    BenchmarkConnector inteiramente com dado sintético derivado do seed."""

    def __init__(self) -> None:
        self._seeds = _carregar_seeds()

    # ---- FundoConnector ----
    def listar_fundos(self) -> list[FundoDTO]:
        return [
            FundoDTO(codigo=s.codigo, nome=s.nome, cnpj=s.cnpj, classe=s.classe,
                    benchmark_padrao=s.benchmark_padrao)
            for s in self._seeds.values()
        ]

    def obter_periodos(self, fundo_codigo: str) -> list[PeriodoDTO]:
        return [PeriodoDTO(label=label, data_inicio=ini, data_fim=fim)
                for label, ini, fim in PERIODOS]

    def _retorno_periodo(self, seed: _FundoSeed, periodo_label: str,
                        rnd: random.Random) -> tuple[float, float]:
        """(retorno_cota, retorno_bench) do período — idêntico ao seed pra
        âncora, sintetizado por um fator de tendência pros anteriores."""
        if periodo_label == PERIODO_ANCORA:
            return seed.retorno_cota, seed.retorno_bench
        fator = _fator_trimestre(rnd)
        return round(seed.retorno_cota * fator, 2), round(seed.retorno_bench * fator, 2)

    def obter_serie_diaria(self, fundo_codigo: str, periodo_label: str) -> list[PontoSerieDTO]:
        seed = self._seeds[fundo_codigo]
        if periodo_label == PERIODO_ANCORA:
            return [PontoSerieDTO(data=date.fromisoformat(p["data"]), cota=p["cota"], bench=p["bench"])
                    for p in seed.serie_diaria]
        label, ini, fim = next(p for p in PERIODOS if p[0] == periodo_label)
        rnd = random.Random(f"{fundo_codigo}:{periodo_label}:serie")
        retorno_cota, retorno_bench = self._retorno_periodo(seed, periodo_label, rnd)
        dias = _dias_uteis(ini, fim)
        n = len(dias) - 1
        passo_c, passo_b = retorno_cota / n, retorno_bench / n
        vol = max(abs(retorno_cota) / 40, 0.02)
        acum_c = acum_b = 0.0
        pontos: list[PontoSerieDTO] = []
        for i, d in enumerate(dias):
            if i > 0:
                acum_c += passo_c + rnd.uniform(-vol, vol)
                acum_b += passo_b + rnd.uniform(-vol / 6, vol / 6)
            pontos.append(PontoSerieDTO(data=d, cota=round(acum_c, 4), bench=round(acum_b, 4)))
        ajuste_c = retorno_cota - pontos[-1].cota
        ajuste_b = retorno_bench - pontos[-1].bench
        return [
            PontoSerieDTO(data=p.data,
                          cota=round(p.cota + ajuste_c * (i / n), 4),
                          bench=round(p.bench + ajuste_b * (i / n), 4))
            for i, p in enumerate(pontos)
        ]

    def obter_contribuicoes(self, fundo_codigo: str, periodo_label: str,
                            dimensao: str) -> list[ContribuicaoDTO]:
        seed = self._seeds[fundo_codigo]
        rnd = random.Random(f"{fundo_codigo}:{periodo_label}:{dimensao}")
        retorno_cota, _ = self._retorno_periodo(seed, periodo_label, rnd)

        if dimensao == "estrategia" and periodo_label == PERIODO_ANCORA:
            return [ContribuicaoDTO(dimensao=dimensao, chave_dimensao=e["nome"],
                                    contribuicao_pp=e["contribuicao_pp"],
                                    peso_medio=e["peso_medio"], cor=e.get("cor", "neutral"))
                    for e in seed.estrategias]

        if dimensao == "ativos" and periodo_label == PERIODO_ANCORA:
            return [ContribuicaoDTO(dimensao=dimensao, chave_dimensao=a["ativo"],
                                    contribuicao_pp=a["contribuicao_pp"],
                                    peso_medio=a["peso_medio"])
                    for a in seed.ativos]

        if dimensao == "estrategia":
            # trimestre histórico: reaproveita os NOMES das estratégias do
            # seed, mas redistribui o retorno sintetizado do período.
            nomes = [e["nome"] for e in seed.estrategias]
            cores = [e.get("cor", "neutral") for e in seed.estrategias]
            partes = _redistribuir(retorno_cota, len(nomes), rnd)
            pesos = _redistribuir(100.0, len(nomes), rnd)
            return [ContribuicaoDTO(dimensao=dimensao, chave_dimensao=n, contribuicao_pp=p,
                                    peso_medio=abs(w), cor=c)
                    for n, p, w, c in zip(nomes, partes, pesos, cores)]

        buckets = BUCKETS_POR_DIMENSAO.get(dimensao)
        if buckets is None:
            return []
        partes = _redistribuir(retorno_cota, len(buckets), rnd)
        pesos = _redistribuir(100.0, len(buckets), rnd)
        return [ContribuicaoDTO(dimensao=dimensao, chave_dimensao=b, contribuicao_pp=p, peso_medio=abs(w))
                for b, p, w in zip(buckets, partes, pesos)]

    # ---- VarConnector ----
    def obter_var(self, fundo_codigo: str, data_inicio: date, data_fim: date) -> list[VarPontoDTO]:
        seed = self._seeds[fundo_codigo]
        rnd = random.Random(f"{fundo_codigo}:var")
        base = max(seed.vol_anual / 20, 0.1)  # magnitude plausível de VaR% do NAV
        pontos: list[VarPontoDTO] = []
        for d in _dias_uteis(data_inicio, data_fim):
            valores = {c: round(abs(rnd.gauss(base, base / 3)), 4) for c in _CLASSES_VAR}
            for c, v in valores.items():
                pontos.append(VarPontoDTO(data=d, classe=c, valor_pct_nav=v))
            pontos.append(VarPontoDTO(data=d, classe="total", valor_pct_nav=round(sum(valores.values()), 4)))
        return pontos

    # ---- BenchmarkConnector ----
    def listar_benchmarks(self) -> list[str]:
        return list(BENCHMARK_UNIVERSO)

    def obter_pesos(self, fundo_codigo: str, periodo_label: str) -> list[BenchmarkPesoDTO]:
        seed = self._seeds[fundo_codigo]
        rnd = random.Random(f"{fundo_codigo}:{periodo_label}:bench")
        principal = seed.benchmark_padrao
        secundario = rnd.choice([b for b in BENCHMARK_UNIVERSO if b != principal])
        peso_principal = round(rnd.uniform(0.8, 0.95), 2)
        return [
            BenchmarkPesoDTO(benchmark_nome=principal, peso=peso_principal),
            BenchmarkPesoDTO(benchmark_nome=secundario, peso=round(1 - peso_principal, 2)),
        ]

    # ---- EstrategiaConnector ----
    def obter_classificacao_atual(self, fundo_codigo: str) -> list[EstrategiaClassificacaoDTO]:
        seed = self._seeds[fundo_codigo]
        out = []
        for a in seed.ativos:
            out.append(EstrategiaClassificacaoDTO(
                ativo_codigo=a["ativo"], ativo_nome=a["ativo"], ativo_tipo="titulo",
                nome_estrategia=a["estrategia"],
            ))
        return out

    def aplicar_classificacao(self, fundo_codigo: str, linhas: list[EstrategiaClassificacaoDTO],
                              matricula: str) -> str:
        import hashlib
        payload = "|".join(f"{fundo_codigo}:{l.ativo_codigo}:{l.nome_estrategia}" for l in linhas)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()
