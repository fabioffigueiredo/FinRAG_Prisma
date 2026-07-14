"""Gera os fundos-exemplo (fictícios) do POC Prisma.

Três perfis: Alfa Multimercado (CDI), Beta Ações (IBOVESPA) e Gama Renda Fixa CP
(CDI). Números sintéticos; a série diária fecha exatamente no alvo e a soma das
contribuições por estratégia é igual ao retorno da cota.

Uso: python3 data/gen_seed.py  -> escreve data/seed/fundo_{alfa,beta,gama}.json
"""
import json
import random
from datetime import date, timedelta
from pathlib import Path

OUT = Path(__file__).resolve().parent / "seed"
OUT.mkdir(parents=True, exist_ok=True)
DIAS = 63


def serie(alvo_pct, vol_diaria, seed):
    rnd = random.Random(seed)
    passo = alvo_pct / DIAS
    acum, pts = 0.0, []
    for i in range(DIAS + 1):
        if i > 0:
            acum += passo + rnd.uniform(-vol_diaria, vol_diaria)
        pts.append(acum)
    ajuste = alvo_pct - pts[-1]
    return [round(p + ajuste * (i / DIAS), 4) for i, p in enumerate(pts)]


def dias_uteis(n):
    out, d = [], date(2026, 4, 1)
    while len(out) <= n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


DATAS = dias_uteis(DIAS)


def montar(meta, resumo, estrategias, ativos, fics, vol_cota, vol_bench, seed):
    soma = round(sum(e["contribuicao_pp"] for e in estrategias), 2)
    assert abs(soma - resumo["retorno_cota"]) < 0.01, (meta["codigo"], soma)
    cota = serie(resumo["retorno_cota"], vol_cota, seed)
    bench = serie(resumo["retorno_bench"], vol_bench, seed + 1)
    return {
        "fundo": meta,
        "resumo": resumo,
        "estrategias": estrategias,
        "ativos": ativos,
        "serie_diaria": [
            {"data": dt, "cota": c, "bench": b} for dt, c, b in zip(DATAS, cota, bench)
        ],
        "fics": fics,
    }


FUNDOS = {
    "fundo_alfa.json": montar(
        {"nome": "Alfa Multimercado FIC FIM", "codigo": "ALFA-33",
         "cnpj": "00.000.000/0001-00 (fictício)", "benchmark": "CDI",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Multimercado Macro"},
        {"retorno_cota": 4.25, "retorno_bench": 3.10, "excesso_pp": 1.15,
         "pct_cdi": 137.1, "beta": 0.15, "alpha_pp": 1.10, "vol_anual": 4.8,
         "patrimonio_mm": 1284.6, "num_cotistas": 3120},
        [
            {"nome": "Crédito Privado", "contribuicao_pp": 1.35, "peso_medio": 28.0, "cor": "gold"},
            {"nome": "Juros Brasil", "contribuicao_pp": 1.05, "peso_medio": 24.0, "cor": "blue"},
            {"nome": "Bolsa Brasil", "contribuicao_pp": 0.85, "peso_medio": 14.0, "cor": "green"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.48, "peso_medio": 18.0, "cor": "neutral"},
            {"nome": "Câmbio (USD)", "contribuicao_pp": 0.42, "peso_medio": 6.0, "cor": "violet"},
            {"nome": "Juros Global", "contribuicao_pp": 0.35, "peso_medio": 8.0, "cor": "blue"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.25, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Crédito Privado", "ativo": "Debênture Infra Energia 2031", "contribuicao_pp": 0.55, "peso_medio": 11.0},
            {"estrategia": "Crédito Privado", "ativo": "CDB Banco Médio 2027", "contribuicao_pp": 0.40, "peso_medio": 9.0},
            {"estrategia": "Crédito Privado", "ativo": "FIDC Recebíveis Comerciais", "contribuicao_pp": 0.40, "peso_medio": 8.0},
            {"estrategia": "Juros Brasil", "ativo": "NTN-B 2030", "contribuicao_pp": 0.60, "peso_medio": 13.0},
            {"estrategia": "Juros Brasil", "ativo": "LTN 2027", "contribuicao_pp": 0.45, "peso_medio": 11.0},
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Bancário", "contribuicao_pp": 0.50, "peso_medio": 6.0},
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Energia Elétrica", "contribuicao_pp": 0.45, "peso_medio": 5.0},
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Varejo", "contribuicao_pp": -0.10, "peso_medio": 3.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.48, "peso_medio": 18.0},
            {"estrategia": "Câmbio (USD)", "ativo": "USD/BRL a termo", "contribuicao_pp": 0.42, "peso_medio": 6.0},
            {"estrategia": "Juros Global", "ativo": "Treasury 10Y (futuro)", "contribuicao_pp": 0.35, "peso_medio": 8.0},
        ],
        [
            {"nome": "Alfa Crédito Master FI", "resultado_pp": 1.35, "diferencial_pp": 0.02},
            {"nome": "Alfa Macro Master FI", "resultado_pp": 2.60, "diferencial_pp": -0.01},
        ],
        vol_cota=0.11, vol_bench=0.015, seed=42,
    ),
    "fundo_beta.json": montar(
        {"nome": "Beta Ações FIA", "codigo": "BETA-71",
         "cnpj": "00.000.000/0002-00 (fictício)", "benchmark": "IBOVESPA",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Ações Livre"},
        {"retorno_cota": 6.40, "retorno_bench": 5.80, "excesso_pp": 0.60,
         "pct_cdi": 110.3, "beta": 0.92, "alpha_pp": 0.85, "vol_anual": 14.2,
         "patrimonio_mm": 642.3, "num_cotistas": 8540},
        [
            {"nome": "Setor Bancário", "contribuicao_pp": 2.60, "peso_medio": 22.0, "cor": "gold"},
            {"nome": "Setor Energia", "contribuicao_pp": 1.90, "peso_medio": 18.0, "cor": "green"},
            {"nome": "Small Caps", "contribuicao_pp": 1.40, "peso_medio": 10.0, "cor": "violet"},
            {"nome": "Indústria", "contribuicao_pp": 1.10, "peso_medio": 14.0, "cor": "blue"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.55, "peso_medio": 24.0, "cor": "neutral"},
            {"nome": "Consumo e Varejo", "contribuicao_pp": -0.80, "peso_medio": 12.0, "cor": "red"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.35, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Setor Bancário", "ativo": "Cesta Bancos Large Cap", "contribuicao_pp": 1.60, "peso_medio": 12.0},
            {"estrategia": "Setor Bancário", "ativo": "Banco Digital Norte ON", "contribuicao_pp": 1.00, "peso_medio": 10.0},
            {"estrategia": "Setor Energia", "ativo": "Elétricas Reguladas", "contribuicao_pp": 1.20, "peso_medio": 10.0},
            {"estrategia": "Setor Energia", "ativo": "Geração Renovável ON", "contribuicao_pp": 0.70, "peso_medio": 8.0},
            {"estrategia": "Small Caps", "ativo": "Cesta Small Caps", "contribuicao_pp": 1.40, "peso_medio": 10.0},
            {"estrategia": "Indústria", "ativo": "Bens de Capital ON", "contribuicao_pp": 1.10, "peso_medio": 14.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.55, "peso_medio": 24.0},
            {"estrategia": "Consumo e Varejo", "ativo": "Varejo Alimentar ON", "contribuicao_pp": -0.30, "peso_medio": 6.0},
            {"estrategia": "Consumo e Varejo", "ativo": "E-commerce BR ON", "contribuicao_pp": -0.50, "peso_medio": 6.0},
        ],
        [],
        vol_cota=0.35, vol_bench=0.30, seed=71,
    ),
    "fundo_gama.json": montar(
        {"nome": "Gama Renda Fixa CP", "codigo": "GAMA-12",
         "cnpj": "00.000.000/0003-00 (fictício)", "benchmark": "CDI",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Renda Fixa Crédito Privado"},
        {"retorno_cota": 3.45, "retorno_bench": 3.10, "excesso_pp": 0.35,
         "pct_cdi": 111.3, "beta": 0.98, "alpha_pp": 0.35, "vol_anual": 0.6,
         "patrimonio_mm": 2410.8, "num_cotistas": 15230},
        [
            {"nome": "Caixa e Over", "contribuicao_pp": 2.30, "peso_medio": 40.0, "cor": "neutral"},
            {"nome": "Crédito Privado", "contribuicao_pp": 0.85, "peso_medio": 45.0, "cor": "gold"},
            {"nome": "Juros Brasil", "contribuicao_pp": 0.42, "peso_medio": 15.0, "cor": "blue"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.12, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 2.30, "peso_medio": 40.0},
            {"estrategia": "Crédito Privado", "ativo": "CDB AAA 2027", "contribuicao_pp": 0.45, "peso_medio": 25.0},
            {"estrategia": "Crédito Privado", "ativo": "Debênture Saneamento 2028", "contribuicao_pp": 0.28, "peso_medio": 12.0},
            {"estrategia": "Crédito Privado", "ativo": "LF Banco Grande Porte", "contribuicao_pp": 0.12, "peso_medio": 8.0},
            {"estrategia": "Juros Brasil", "ativo": "LFT 2028", "contribuicao_pp": 0.42, "peso_medio": 15.0},
        ],
        [],
        vol_cota=0.02, vol_bench=0.015, seed=12,
    ),
    "fundo_delta.json": montar(
        {"nome": "Delta Multimercado FIC FIM", "codigo": "DELTA-08",
         "cnpj": "00.000.000/0004-00 (fictício)", "benchmark": "CDI",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Multimercado Macro"},
        {"retorno_cota": -1.85, "retorno_bench": 3.05, "excesso_pp": -4.90,
         "pct_cdi": -60.7, "beta": 0.20, "alpha_pp": -4.85, "vol_anual": 6.5,
         "patrimonio_mm": 410.2, "num_cotistas": 980},
        [
            {"nome": "Bolsa Brasil", "contribuicao_pp": -2.20, "peso_medio": 20.0, "cor": "red"},
            {"nome": "Câmbio (USD)", "contribuicao_pp": -0.55, "peso_medio": 12.0, "cor": "red"},
            {"nome": "Juros Brasil", "contribuicao_pp": 0.40, "peso_medio": 22.0, "cor": "blue"},
            {"nome": "Crédito Privado", "contribuicao_pp": 0.35, "peso_medio": 18.0, "cor": "gold"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.25, "peso_medio": 28.0, "cor": "neutral"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.10, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Varejo", "contribuicao_pp": -1.30, "peso_medio": 11.0},
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Bancário", "contribuicao_pp": -0.90, "peso_medio": 9.0},
            {"estrategia": "Câmbio (USD)", "ativo": "USD/BRL a termo", "contribuicao_pp": -0.55, "peso_medio": 12.0},
            {"estrategia": "Juros Brasil", "ativo": "NTN-B 2030", "contribuicao_pp": 0.40, "peso_medio": 22.0},
            {"estrategia": "Crédito Privado", "ativo": "CDB Banco Médio 2027", "contribuicao_pp": 0.35, "peso_medio": 18.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.25, "peso_medio": 28.0},
        ],
        [],
        vol_cota=0.25, vol_bench=0.015, seed=8,
    ),
    "fundo_epsilon.json": montar(
        {"nome": "Epsilon Ações Long Biased FIA", "codigo": "EPSILON-45",
         "cnpj": "00.000.000/0005-00 (fictício)", "benchmark": "IBOVESPA",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Ações Livre"},
        {"retorno_cota": 4.10, "retorno_bench": 6.50, "excesso_pp": -2.40,
         "pct_cdi": 70.6, "beta": 1.05, "alpha_pp": -2.35, "vol_anual": 13.5,
         "patrimonio_mm": 310.0, "num_cotistas": 2200},
        [
            {"nome": "Setor Bancário", "contribuicao_pp": 1.50, "peso_medio": 18.0, "cor": "gold"},
            {"nome": "Setor Energia", "contribuicao_pp": 0.90, "peso_medio": 14.0, "cor": "green"},
            {"nome": "Small Caps", "contribuicao_pp": 0.60, "peso_medio": 9.0, "cor": "violet"},
            {"nome": "Indústria", "contribuicao_pp": 0.55, "peso_medio": 12.0, "cor": "blue"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.35, "peso_medio": 22.0, "cor": "neutral"},
            {"nome": "Consumo e Varejo", "contribuicao_pp": 0.30, "peso_medio": 15.0, "cor": "green"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.10, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Setor Bancário", "ativo": "Cesta Bancos Large Cap", "contribuicao_pp": 1.50, "peso_medio": 18.0},
            {"estrategia": "Setor Energia", "ativo": "Elétricas Reguladas", "contribuicao_pp": 0.90, "peso_medio": 14.0},
            {"estrategia": "Small Caps", "ativo": "Cesta Small Caps", "contribuicao_pp": 0.60, "peso_medio": 9.0},
            {"estrategia": "Indústria", "ativo": "Bens de Capital ON", "contribuicao_pp": 0.55, "peso_medio": 12.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.35, "peso_medio": 22.0},
            {"estrategia": "Consumo e Varejo", "ativo": "Varejo Alimentar ON", "contribuicao_pp": 0.30, "peso_medio": 15.0},
        ],
        [],
        vol_cota=0.30, vol_bench=0.28, seed=45,
    ),
    "fundo_zeta.json": montar(
        {"nome": "Zeta Multimercado Alto Risco FIM", "codigo": "ZETA-19",
         "cnpj": "00.000.000/0006-00 (fictício)", "benchmark": "CDI",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Multimercado Alto Risco"},
        {"retorno_cota": 7.80, "retorno_bench": 3.05, "excesso_pp": 4.75,
         "pct_cdi": 255.7, "beta": 0.45, "alpha_pp": 4.60, "vol_anual": 22.4,
         "patrimonio_mm": 180.5, "num_cotistas": 410},
        [
            {"nome": "Câmbio (USD)", "contribuicao_pp": 2.80, "peso_medio": 20.0, "cor": "violet"},
            {"nome": "Juros Global", "contribuicao_pp": 1.90, "peso_medio": 16.0, "cor": "blue"},
            {"nome": "Bolsa Brasil", "contribuicao_pp": 1.60, "peso_medio": 14.0, "cor": "green"},
            {"nome": "Crédito Privado", "contribuicao_pp": 0.85, "peso_medio": 12.0, "cor": "gold"},
            {"nome": "Juros Brasil", "contribuicao_pp": 0.20, "peso_medio": 10.0, "cor": "blue"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.55, "peso_medio": 28.0, "cor": "neutral"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.10, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Câmbio (USD)", "ativo": "USD/BRL a termo", "contribuicao_pp": 2.80, "peso_medio": 20.0},
            {"estrategia": "Juros Global", "ativo": "Treasury 10Y (futuro)", "contribuicao_pp": 1.90, "peso_medio": 16.0},
            {"estrategia": "Bolsa Brasil", "ativo": "Setor Energia Elétrica", "contribuicao_pp": 1.60, "peso_medio": 14.0},
            {"estrategia": "Crédito Privado", "ativo": "FIDC Recebíveis Comerciais", "contribuicao_pp": 0.85, "peso_medio": 12.0},
            {"estrategia": "Juros Brasil", "ativo": "LTN 2027", "contribuicao_pp": 0.20, "peso_medio": 10.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.55, "peso_medio": 28.0},
        ],
        [],
        vol_cota=0.55, vol_bench=0.015, seed=19,
    ),
    "fundo_theta.json": montar(
        {"nome": "Theta Renda Fixa Duração FIC FI", "codigo": "THETA-52",
         "cnpj": "00.000.000/0007-00 (fictício)", "benchmark": "CDI",
         "periodo": "2º trimestre 2026 (abr–jun)", "classe": "Renda Fixa Duração"},
        {"retorno_cota": 3.65, "retorno_bench": 3.05, "excesso_pp": 0.60,
         "pct_cdi": 119.7, "beta": 0.99, "alpha_pp": 0.58, "vol_anual": 1.2,
         "patrimonio_mm": 980.4, "num_cotistas": 5400},
        [
            {"nome": "Juros Brasil", "contribuicao_pp": 2.10, "peso_medio": 55.0, "cor": "blue"},
            {"nome": "Crédito Privado", "contribuicao_pp": 1.05, "peso_medio": 30.0, "cor": "gold"},
            {"nome": "Caixa e Over", "contribuicao_pp": 0.60, "peso_medio": 15.0, "cor": "neutral"},
            {"nome": "Custos e Despesas", "contribuicao_pp": -0.10, "peso_medio": 0.0, "cor": "red"},
        ],
        [
            {"estrategia": "Juros Brasil", "ativo": "NTN-B 2035", "contribuicao_pp": 1.30, "peso_medio": 35.0},
            {"estrategia": "Juros Brasil", "ativo": "LTN 2029", "contribuicao_pp": 0.80, "peso_medio": 20.0},
            {"estrategia": "Crédito Privado", "ativo": "Debênture Infra Energia 2031", "contribuicao_pp": 0.65, "peso_medio": 18.0},
            {"estrategia": "Crédito Privado", "ativo": "CDB AAA 2027", "contribuicao_pp": 0.40, "peso_medio": 12.0},
            {"estrategia": "Caixa e Over", "ativo": "Operações Compromissadas", "contribuicao_pp": 0.60, "peso_medio": 15.0},
        ],
        [],
        vol_cota=0.03, vol_bench=0.015, seed=52,
    ),
}

for nome, dados in FUNDOS.items():
    (OUT / nome).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    r = dados["resumo"]
    print(f"{nome}: cota {r['retorno_cota']}% vs bench {r['retorno_bench']}% ok")
