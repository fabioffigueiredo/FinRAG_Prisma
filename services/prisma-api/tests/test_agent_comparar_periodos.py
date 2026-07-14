"""Meta 3: narrativa proativa — comparar_periodos calcula os deltas (o LLM
só narra), lendo o histórico multi-período real da Meta 1 no Postgres."""
import pytest

import agent

FUNDO_ALFA = {
    "ALFA-33": {
        "fundo": {"nome": "Alfa Multimercado FIC FIM", "codigo": "ALFA-33",
                 "benchmark": "CDI", "periodo": "2º trimestre 2026 (abr–jun)",
                 "classe": "Multimercado Macro"},
        "resumo": {}, "estrategias": [], "serie_diaria": [], "ativos": [], "fics": [],
    }
}


def test_comparar_periodos_traz_periodo_atual_e_anterior():
    out = agent._tool_comparar_periodos(FUNDO_ALFA, {"fundo": "ALFA-33"})
    if "erro" in out:
        pytest.skip("Postgres de dev indisponível/não semeado")
    assert out["periodo_atual"] == "2º trimestre 2026 (abr–jun)"
    assert out["periodo_anterior"] == "1º trimestre 2026 (jan–mar)"
    assert out["delta_retorno_cota_pp"] is not None


def test_comparar_periodos_ordena_por_maior_variacao_absoluta():
    out = agent._tool_comparar_periodos(FUNDO_ALFA, {"fundo": "ALFA-33"})
    if "erro" in out:
        pytest.skip("Postgres de dev indisponível/não semeado")
    deltas = [abs(v["delta_pp"]) for v in out["maiores_variacoes"]]
    assert deltas == sorted(deltas, reverse=True)


def test_comparar_periodos_fundo_inexistente_da_erro():
    out = agent._tool_comparar_periodos(FUNDO_ALFA, {"fundo": "NAO-EXISTE"})
    assert "erro" in out
