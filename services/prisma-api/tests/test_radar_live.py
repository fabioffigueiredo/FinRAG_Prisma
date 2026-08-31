from datetime import UTC, datetime, timedelta

import radar


class Classifier:
    model_version = "teste@1"

    def __init__(self, score=0.91):
        self.score = score

    def classify(self, _text):
        return "positivo", self.score


def _entry(title="Fed sinaliza corte de juros", *, when=None, link="https://fonte.test/a", summary="Notícia de mercado financeiro."):
    when = when or datetime.now(UTC)
    return {
        "title": title,
        "summary": summary,
        "text": title,
        "link": link,
        "portal": "Fonte teste",
        "published_at": when.isoformat(),
    }


def test_rss_recente_e_relevante_e_classificado_localmente(monkeypatch):
    monkeypatch.setattr(radar, "fetch_feeds", lambda: [_entry()])
    noticias = radar.carregar_noticias(classifier=Classifier())
    assert len(noticias) == 1
    assert noticias[0]["estado"] == "classificado_local"
    assert noticias[0]["elegivel_agregado"] is True
    assert "corpo" not in noticias[0]


def test_rss_antigo_duplicado_ou_fora_da_taxonomia_e_descartado(monkeypatch):
    antigo = _entry(when=datetime.now(UTC) - timedelta(hours=25), link="https://fonte.test/old")
    repetido = _entry(link="https://fonte.test/same")
    duplicado = _entry(link="https://fonte.test/same")
    irrelevante = _entry("Festival anuncia programação cultural", link="https://fonte.test/cultura", summary="Programação de shows.")
    monkeypatch.setattr(radar, "fetch_feeds", lambda: [antigo, repetido, duplicado, irrelevante])
    noticias = radar.carregar_noticias(classifier=Classifier())
    assert len(noticias) == 2
    assert sum(n["elegivel_agregado"] for n in noticias) == 1
    assert next(n for n in noticias if not n["relevante"])["estado"] == "pendente_revisao"


def test_indisponibilidade_do_modelo_nunca_inventa_sentimento(monkeypatch):
    monkeypatch.setattr(radar, "fetch_feeds", lambda: [_entry()])
    noticias, status = radar.refresh(classifier=None)
    assert noticias[0]["sentimento"] is None
    assert noticias[0]["estado"] == "pendente_revisao"
    assert status["estado"] == "degradado"


def test_agregado_exclui_revisao_assistida_e_pendente():
    noticias = [
        {"estrategia": "Mercado geral", "sentimento": "positivo", "elegivel_agregado": True},
        {"estrategia": "Mercado geral", "sentimento": "negativo", "elegivel_agregado": False},
    ]
    assert radar.agregar(noticias)["Mercado geral"] == {"pos": 1, "neg": 0, "neu": 0, "total": 1, "liquido": 1.0}
