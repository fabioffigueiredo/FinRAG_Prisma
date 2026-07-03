import sinais


FUNDO = {
    "estrategias": [
        {"nome": "Bolsa Brasil", "contribuicao_pp": -0.10},
        {"nome": "Caixa e Over", "contribuicao_pp": 0.48},
        {"nome": "Sem Noticia", "contribuicao_pp": 0.20},
    ]
}
AGG = {
    "Bolsa Brasil": {"pos": 0, "neg": 3, "neu": 0, "total": 3, "liquido": -1.0},
    "Caixa e Over": {"pos": 1, "neg": 0, "neu": 0, "total": 1, "liquido": 1.0},
}
NOTICIAS = [
    {"id": "n07", "estrategia": "Bolsa Brasil"},
    {"id": "n10", "estrategia": "Caixa e Over"},
]


def test_sinal_negativo_vira_alerta_com_evidencia():
    s = sinais.gerar_sinais(FUNDO, AGG, NOTICIAS)
    bb = next(x for x in s if x["estrategia"] == "Bolsa Brasil")
    assert bb["nivel"] == "alerta"          # sent -1, contrib<0 -> 48+28+7=83
    assert bb["prob_neg"] == 83
    assert "noticia:n07" in bb["evidencias"]


def test_sinal_positivo_fica_ok():
    s = sinais.gerar_sinais(FUNDO, AGG, NOTICIAS)
    co = next(x for x in s if x["estrategia"] == "Caixa e Over")
    assert co["nivel"] == "ok"              # sent +1 -> 48-28=20
    assert co["prob_neg"] == 20


def test_estrategia_sem_noticia_nao_gera_sinal():
    nomes = [x["estrategia"] for x in sinais.gerar_sinais(FUNDO, AGG, NOTICIAS)]
    assert "Sem Noticia" not in nomes


def test_saida_ordenada_por_risco_e_tem_metadados():
    s = sinais.gerar_sinais(FUNDO, AGG, NOTICIAS)
    assert s[0]["prob_neg"] >= s[-1]["prob_neg"]
    assert all("base_calculo" in x and "modelo_versao" in x for x in s)
    assert "recomend" not in sinais.AVISO_LEGAL.lower().split("não")[0]  # começa negando
