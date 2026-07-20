"""Testes dedicados à detecção de fundo citado numa pergunta, cobrindo o
achado do plans/006-avisar-fundo-nao-reconhecido-no-mock.md: `analisar_mock`
não deve responder silenciosamente sobre o fundo em foco quando a pergunta
cita um código de fundo que não existe.
"""
import agent


def _fundo(codigo, retorno_cota=1.0, retorno_bench=0.5):
    return {
        "fundo": {"nome": f"Fundo {codigo}", "codigo": codigo, "benchmark": "CDI",
                  "periodo": "2T26", "classe": "Teste"},
        "resumo": {"retorno_cota": retorno_cota, "retorno_bench": retorno_bench,
                   "excesso_pp": round(retorno_cota - retorno_bench, 2), "pct_cdi": 0.0,
                   "beta": 0.5, "alpha_pp": round(retorno_cota - retorno_bench, 2),
                   "vol_anual": 1.0, "patrimonio_mm": 1.0, "num_cotistas": 1},
        "estrategias": [{"nome": "Caixa e Over", "contribuicao_pp": retorno_cota,
                        "peso_medio": 100.0, "cor": "neutral"}],
        "serie_diaria": [{"data": "2026-04-01", "cota": 0.0, "bench": 0.0}],
        "ativos": [], "fics": [],
    }


# --- _fundo_nao_reconhecido_citado ------------------------------------------

def test_fundo_nao_reconhecido_citado_detecta_codigo_no_padrao_que_nao_existe():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    assert agent._fundo_nao_reconhecido_citado("mostra o fundo XYZ-99", fundos) == "XYZ-99"


def test_fundo_nao_reconhecido_citado_ignora_codigo_que_existe():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    assert agent._fundo_nao_reconhecido_citado("mostra o fundo ALFA-33", fundos) is None


def test_fundo_nao_reconhecido_citado_ignora_pergunta_sem_nenhum_codigo():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    assert agent._fundo_nao_reconhecido_citado("qual foi a rentabilidade?", fundos) is None


# --- Stoplist de palavras genéricas em _detectar_fundo_citado ---------------

def test_detectar_fundo_citado_nao_confunde_palavra_generica_fundo_com_apelido():
    """Fixtures nomeiam fundos como 'Fundo {codigo}' — a palavra genérica
    'fundo' na pergunta não deve ser tratada como o apelido do fundo em
    foco (achado real durante a execução deste plano: sem a stoplist,
    'mostra o fundo XYZ-99' resolvia para ALFA-33 via primeira_palavra)."""
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    assert agent._detectar_fundo_citado("mostra o fundo XYZ-99", fundos) is None


def test_detectar_fundo_citado_por_codigo_continua_funcionando():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    assert agent._detectar_fundo_citado("mostra o ALFA-33", fundos) == "ALFA-33"


# --- analisar_mock -----------------------------------------------------------

def test_analisar_mock_fundo_citado_inexistente_avisa_sem_trocar_de_fundo():
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="mostra o fundo XYZ-99")
    assert "não encontrado" in out["resposta"]
    assert "ALFA" not in out["resposta"]


def test_analisar_mock_pergunta_normal_continua_respondendo_fundo_em_foco():
    """Regressão: pergunta sem código de fundo inexistente não deve ser
    afetada pela checagem nova."""
    fundos = {"ALFA-33": _fundo("ALFA-33")}
    out = agent.analisar_mock(fundo_ativo="ALFA-33", fundos=fundos, noticias=[],
                              pergunta="qual foi a rentabilidade do fundo no semestre?")
    assert "não encontrado" not in out["resposta"]
    assert "ALFA-33" in out["resposta"]
