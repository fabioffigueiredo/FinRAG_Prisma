import json
from pathlib import Path

import radar


def _seed(tmp_path):
    caminho = tmp_path / "noticias_seed.json"
    caminho.write_text(json.dumps([
        {"id": "n01", "titulo": "Notícia do seed", "corpo": "corpo", "estrategia": "Crédito Privado",
         "data": "2026-06-01", "sentimento": "neutro", "confianca": 0.7},
    ], ensure_ascii=False), encoding="utf-8")
    return caminho


def test_carregar_noticias_cai_para_seed_quando_rss_vazio(monkeypatch, tmp_path):
    monkeypatch.setattr(radar, "fetch_feeds", lambda: [])
    caminho = _seed(tmp_path)
    noticias = radar.carregar_noticias(caminho)
    assert len(noticias) == 1
    assert noticias[0]["fonte"] == "seed"


def test_carregar_noticias_usa_rss_quando_disponivel(monkeypatch, tmp_path):
    fake_entradas = [
        {"title": "Fed sinaliza corte de juros", "summary": "resumo em inglês",
         "text": "Fed sinaliza corte de juros. resumo em inglês", "link": "https://x", "portal": "Reuters"},
        {"title": "Banco Central mantém Selic", "summary": "resumo em portugues",
         "text": "Banco Central mantém Selic. resumo em portugues", "link": "https://y", "portal": "Valor"},
    ]
    monkeypatch.setattr(radar, "fetch_feeds", lambda: fake_entradas)
    caminho = _seed(tmp_path)
    noticias = radar.carregar_noticias(caminho)
    assert len(noticias) == 2
    assert all(n["fonte"] == "rss" for n in noticias)
    assert {n["portal"] for n in noticias} == {"Reuters", "Valor"}
    # nenhuma notícia ao vivo é classificada por um modelo que não existe nesta API
    assert all(n["classificado"] is False for n in noticias)


def test_carregar_noticias_propaga_erro_de_fetch_para_fallback(monkeypatch, tmp_path):
    def _explode():
        raise RuntimeError("rede indisponível")

    monkeypatch.setattr(radar, "fetch_feeds", _explode)
    caminho = _seed(tmp_path)
    noticias = radar.carregar_noticias(caminho)
    assert len(noticias) == 1
    assert noticias[0]["fonte"] == "seed"
