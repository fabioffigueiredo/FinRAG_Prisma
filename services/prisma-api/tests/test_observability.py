import json
import logging

import observability


def test_estimar_tokens_ordem_de_grandeza():
    assert observability.estimar_tokens("abcd" * 10) == 10  # 40 chars / 4
    assert observability.estimar_tokens("") == 1  # nunca zero


def test_estimar_custo_ollama_e_sempre_zero():
    assert observability.estimar_custo_usd("ollama", 10_000, 10_000) == 0.0


def test_estimar_custo_groq_e_maior_que_zero_e_cresce_com_tokens():
    custo_pouco = observability.estimar_custo_usd("groq", 1_000, 1_000)
    custo_muito = observability.estimar_custo_usd("groq", 100_000, 100_000)
    assert custo_pouco > 0
    assert custo_muito > custo_pouco


def test_estimar_custo_backend_desconhecido_cai_no_zero_de_mock():
    assert observability.estimar_custo_usd("backend-que-nao-existe", 1000, 1000) == 0.0


def test_registrar_chamada_llm_devolve_evento_com_campos_esperados():
    evento = observability.registrar_chamada_llm(
        backend="groq", modelo="llama-3.3-70b-versatile", prompt="pergunta " * 20,
        resposta="resposta " * 30, latency_ms=850, rota="/perguntar",
    )
    assert evento["backend"] == "groq"
    assert evento["tokens_entrada_estimado"] > 0
    assert evento["tokens_saida_estimado"] > 0
    assert evento["custo_usd_estimado"] > 0
    assert evento["latency_ms"] == 850


def test_registrar_chamada_llm_emite_log(caplog):
    with caplog.at_level(logging.INFO, logger="prisma.observability"):
        observability.registrar_chamada_llm(backend="ollama", modelo="qwen3:8b",
                                            prompt="oi", resposta="olá", latency_ms=100)
    assert any(r.message == "chamada_llm" for r in caplog.records)


def test_formatador_json_produz_json_valido_com_campos_extra():
    formatador = observability._FormatadorJSON()
    record = logging.LogRecord("prisma.observability", logging.INFO, __file__, 1,
                               "chamada_llm", None, None)
    record.campos_extra = {"backend": "groq", "custo_usd_estimado": 0.001}
    saida = formatador.format(record)
    parsed = json.loads(saida)
    assert parsed["backend"] == "groq"
    assert parsed["mensagem"] == "chamada_llm"
