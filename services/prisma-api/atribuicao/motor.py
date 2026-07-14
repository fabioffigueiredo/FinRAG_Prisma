"""Motor de atribuição (Meta 2) — reimplementação testável da lógica real de
contribuição/custo de oportunidade, sem herdar o débito técnico do sistema
legado (sign-flips hardcoded por fundo, SQL espalhado em arquivos .sql).

Decidi reimplementar em vez de portar 1:1 porque notei, lendo `main.py` do
sistema real, que boa parte da complexidade de lá vem de reconciliar dado
contábil legado (Sinqia/DW) — aqui, sobre dado sintético, a MESMA fórmula
matemática (contribuição diária encadeada + custo de oportunidade ponderado)
é reaproveitável sem herdar as correções manuais por fundo específico.
"""
from __future__ import annotations


def contribuicao_diaria_pp(saldo: float, patrimonio_d1: float) -> float:
    """Contribuição de uma posição num dia = saldo (variação/proventos do
    dia) dividido pelo patrimônio do dia anterior — a mesma fórmula
    (`CONTRIBUICAO = SALDO/PATRIMONIO_D1`) do motor real, em pp."""
    if patrimonio_d1 == 0:
        return 0.0
    return round((saldo / patrimonio_d1) * 100, 6)


def encadear_contribuicoes_pp(contribuicoes_diarias_pp: list[float],
                              retornos_diarios_fundo_pp: list[float]) -> float:
    """Encadeia contribuições diárias pelo retorno acumulado ANTERIOR do
    fundo, porque notei que somar contribuições diárias brutas subestima o
    efeito de compounding ao longo do período — é o mesmo princípio do
    `ajuste_contribuicao` do sistema real (mesmo tamanho de lista exigido
    pros dois argumentos: contribuição do dia i usa o acumulado até i-1)."""
    if len(contribuicoes_diarias_pp) != len(retornos_diarios_fundo_pp):
        raise ValueError("contribuições e retornos diários precisam ter o mesmo tamanho")
    acumulado = 1.0
    total_pp = 0.0
    for contrib_pp, retorno_pp in zip(contribuicoes_diarias_pp, retornos_diarios_fundo_pp):
        total_pp += contrib_pp * acumulado
        acumulado *= (1 + retorno_pp / 100)
    return round(total_pp, 4)


def custo_oportunidade_pp(contribuicao_pp: float, peso_medio_pct: float,
                          retorno_benchmark_periodo_pp: float) -> float:
    """Excesso de contribuição vs. o que essa posição teria rendido só de
    acompanhar o benchmark, ponderado pelo peso médio dela no fundo — mesmo
    conceito do toggle "Custo de oportunidade" do frontend real."""
    return round(contribuicao_pp - (peso_medio_pct / 100) * retorno_benchmark_periodo_pp, 4)


def agregar_por_grupo(contribuicoes: list[tuple[str, float]],
                      mapa_bucket_para_grupo: dict[str, str]) -> dict[str, float]:
    """Faz rollup de contribuições por bucket fino (ex.: estratégia) num
    agrupamento mais grosso (ex.: supergrupo) — o mesmo papel de
    `agregar_dados`/`segmentar_dados` do sistema real, só que aqui é uma
    função pura testável em vez de `match` espalhado em SQL."""
    out: dict[str, float] = {}
    for bucket, contrib_pp in contribuicoes:
        grupo = mapa_bucket_para_grupo.get(bucket, bucket)
        out[grupo] = round(out.get(grupo, 0.0) + contrib_pp, 4)
    return out
