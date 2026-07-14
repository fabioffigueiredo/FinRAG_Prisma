from pathlib import Path

import radar
from radar import agregar, carregar_noticias


def test_agregar_liquido():
    noticias = [
        {"estrategia": "Bolsa Brasil", "sentimento": "positivo"},
        {"estrategia": "Bolsa Brasil", "sentimento": "positivo"},
        {"estrategia": "Bolsa Brasil", "sentimento": "negativo"},
        {"estrategia": "Bolsa Brasil", "sentimento": "neutro"},
        {"estrategia": "Caixa e Over", "sentimento": "neutro"},
    ]
    agg = agregar(noticias)
    bb = agg["Bolsa Brasil"]
    assert (bb["pos"], bb["neg"], bb["neu"], bb["total"]) == (2, 1, 1, 4)
    assert bb["liquido"] == 0.25
    assert agg["Caixa e Over"]["liquido"] == 0.0


def test_carregar_inexistente(monkeypatch):
    monkeypatch.setattr(radar, "fetch_feeds", lambda: [])
    assert carregar_noticias(Path("/nao/existe.json")) == []
