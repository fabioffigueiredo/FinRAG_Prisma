import pytest

from atribuicao.motor import (
    agregar_por_grupo,
    contribuicao_diaria_pp,
    custo_oportunidade_pp,
    encadear_contribuicoes_pp,
)


def test_contribuicao_diaria_pp_caso_basico():
    # saldo de 12.500 num fundo com 1.000.000 de patrimônio no D-1 = 1,25pp
    assert contribuicao_diaria_pp(12_500, 1_000_000) == 1.25


def test_contribuicao_diaria_pp_patrimonio_zero_nao_explode():
    assert contribuicao_diaria_pp(100, 0) == 0.0


def test_encadear_sem_compounding_e_soma_simples():
    contribuicoes = [1.0, 0.5, 0.3]
    retornos = [0.0, 0.0, 0.0]  # sem retorno acumulado -> sem efeito de encadeamento
    assert encadear_contribuicoes_pp(contribuicoes, retornos) == pytest.approx(1.8)


def test_encadear_com_compounding_fica_acima_da_soma_simples():
    contribuicoes = [1.0, 1.0, 1.0]
    retornos = [1.0, 1.0, 1.0]  # 1% de retorno acumulado do fundo por dia
    soma_simples = sum(contribuicoes)
    encadeado = encadear_contribuicoes_pp(contribuicoes, retornos)
    assert encadeado > soma_simples


def test_encadear_exige_mesmo_tamanho():
    with pytest.raises(ValueError):
        encadear_contribuicoes_pp([1.0, 2.0], [0.0])


def test_custo_oportunidade_zero_quando_acompanha_benchmark_ponderado():
    # peso médio 50%, benchmark rendeu 2pp no período -> contribuição
    # "neutra" esperada é 0.5 * 2 = 1.0pp
    assert custo_oportunidade_pp(contribuicao_pp=1.0, peso_medio_pct=50.0,
                                 retorno_benchmark_periodo_pp=2.0) == 0.0


def test_custo_oportunidade_positivo_quando_supera_benchmark():
    resultado = custo_oportunidade_pp(contribuicao_pp=1.5, peso_medio_pct=50.0,
                                      retorno_benchmark_periodo_pp=2.0)
    assert resultado == 0.5


def test_agregar_por_grupo_soma_corretamente():
    contribuicoes = [("Crédito Privado", 1.35), ("Juros Brasil", 1.05), ("Bolsa Brasil", 0.85)]
    mapa = {"Crédito Privado": "Renda Fixa", "Juros Brasil": "Renda Fixa", "Bolsa Brasil": "Renda Variável"}
    resultado = agregar_por_grupo(contribuicoes, mapa)
    assert resultado == {"Renda Fixa": 2.40, "Renda Variável": 0.85}


def test_agregar_por_grupo_sem_mapeamento_cai_no_proprio_bucket():
    resultado = agregar_por_grupo([("Custos e Despesas", -0.25)], mapa_bucket_para_grupo={})
    assert resultado == {"Custos e Despesas": -0.25}
