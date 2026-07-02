"""Gera o fundo-exemplo (fictício) de atribuição de performance para o POC Prisma.

Fundo, ativos e números são sintéticos — nenhuma instituição real é citada
(mesma regra de ouro dos projetos anteriores). A série diária é construída para
fechar exatamente no retorno-alvo da cota e do benchmark.

Uso: python3 data/gen_seed.py  -> escreve data/seed/fundo_alfa.json
"""
import json
import math
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(42)
OUT = Path(__file__).resolve().parent / "seed"
OUT.mkdir(parents=True, exist_ok=True)

# ---- Alvos do período (2º trimestre 2026, abr–jun) ----
RET_COTA = 4.25   # % no período
RET_BENCH = 3.10  # % CDI no período
DIAS = 63         # dias úteis aprox.

# ---- Contribuição por estratégia (pp) — soma = RET_COTA ----
estrategias = [
    {"nome": "Crédito Privado",   "contribuicao_pp": 1.35, "peso_medio": 28.0, "cor": "gold"},
    {"nome": "Juros Brasil",      "contribuicao_pp": 1.05, "peso_medio": 24.0, "cor": "blue"},
    {"nome": "Bolsa Brasil",      "contribuicao_pp": 0.85, "peso_medio": 14.0, "cor": "green"},
    {"nome": "Caixa e Over",      "contribuicao_pp": 0.48, "peso_medio": 18.0, "cor": "neutral"},
    {"nome": "Câmbio (USD)",      "contribuicao_pp": 0.42, "peso_medio": 6.0,  "cor": "violet"},
    {"nome": "Juros Global",      "contribuicao_pp": 0.35, "peso_medio": 8.0,  "cor": "blue"},
    {"nome": "Custos e Despesas", "contribuicao_pp": -0.25, "peso_medio": 0.0, "cor": "red"},
]

# ---- Ativos por estratégia (pp) ----
ativos = [
    {"estrategia": "Crédito Privado", "ativo": "Debênture Infra Energia 2031", "contribuicao_pp": 0.55, "peso_medio": 11.0},
    {"estrategia": "Crédito Privado", "ativo": "CDB Banco Médio 2027",         "contribuicao_pp": 0.40, "peso_medio": 9.0},
    {"estrategia": "Crédito Privado", "ativo": "FIDC Recebíveis Comerciais",    "contribuicao_pp": 0.40, "peso_medio": 8.0},
    {"estrategia": "Juros Brasil",    "ativo": "NTN-B 2030",                    "contribuicao_pp": 0.60, "peso_medio": 13.0},
    {"estrategia": "Juros Brasil",    "ativo": "LTN 2027",                      "contribuicao_pp": 0.45, "peso_medio": 11.0},
    {"estrategia": "Bolsa Brasil",    "ativo": "Setor Bancário",               "contribuicao_pp": 0.50, "peso_medio": 6.0},
    {"estrategia": "Bolsa Brasil",    "ativo": "Setor Energia Elétrica",       "contribuicao_pp": 0.45, "peso_medio": 5.0},
    {"estrategia": "Bolsa Brasil",    "ativo": "Setor Varejo",                 "contribuicao_pp": -0.10, "peso_medio": 3.0},
    {"estrategia": "Caixa e Over",    "ativo": "Operações Compromissadas",     "contribuicao_pp": 0.48, "peso_medio": 18.0},
    {"estrategia": "Câmbio (USD)",    "ativo": "USD/BRL a termo",              "contribuicao_pp": 0.42, "peso_medio": 6.0},
    {"estrategia": "Juros Global",    "ativo": "Treasury 10Y (futuro)",        "contribuicao_pp": 0.35, "peso_medio": 8.0},
]

# ---- Série diária: passeio suave até o alvo ----
def serie(alvo_pct, vol_diaria):
    passo = alvo_pct / DIAS
    acum, pts = 0.0, []
    for i in range(DIAS + 1):
        if i > 0:
            acum += passo + random.uniform(-vol_diaria, vol_diaria)
        pts.append(acum)
    # normaliza para fechar exatamente no alvo
    ajuste = alvo_pct - pts[-1]
    return [round(p + ajuste * (i / DIAS), 4) for i, p in enumerate(pts)]

d0 = date(2026, 4, 1)
def dias_uteis(n):
    out, d = [], d0
    while len(out) <= n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out

datas = dias_uteis(DIAS)
cota = serie(RET_COTA, 0.11)
bench = serie(RET_BENCH, 0.015)
serie_diaria = [{"data": dt, "cota": c, "bench": b} for dt, c, b in zip(datas, cota, bench)]

fundo = {
    "fundo": {
        "nome": "Alfa Multimercado FIC FIM",
        "codigo": "ALFA-33",
        "cnpj": "00.000.000/0001-00 (fictício)",
        "benchmark": "CDI",
        "periodo": "2º trimestre 2026 (abr–jun)",
        "classe": "Multimercado Macro",
    },
    "resumo": {
        "retorno_cota": RET_COTA,
        "retorno_bench": RET_BENCH,
        "excesso_pp": round(RET_COTA - RET_BENCH, 2),
        "pct_cdi": round(RET_COTA / RET_BENCH * 100, 1),
        "beta": 0.15,
        "alpha_pp": 1.10,
        "vol_anual": 4.8,
        "patrimonio_mm": 1284.6,
        "num_cotistas": 3120,
    },
    "estrategias": estrategias,
    "ativos": ativos,
    "serie_diaria": serie_diaria,
    "fics": [
        {"nome": "Alfa Crédito Master FI", "resultado_pp": 1.35, "diferencial_pp": 0.02},
        {"nome": "Alfa Macro Master FI",   "resultado_pp": 2.60, "diferencial_pp": -0.01},
    ],
}

path = OUT / "fundo_alfa.json"
path.write_text(json.dumps(fundo, ensure_ascii=False, indent=2), encoding="utf-8")
soma = round(sum(e["contribuicao_pp"] for e in estrategias), 2)
print("escrito:", path)
print("soma contribuições estratégias:", soma, "| alvo cota:", RET_COTA, "| ok:", abs(soma - RET_COTA) < 0.01)
print("série:", len(serie_diaria), "pontos | cota fim:", serie_diaria[-1]["cota"], "| bench fim:", serie_diaria[-1]["bench"])
