"""Radar de Mercado: carga das notícias classificadas e agregado por estratégia."""
import json
import logging
from datetime import date
from pathlib import Path

from rss_scraper import fetch_feeds

_log = logging.getLogger(__name__)


def _carregar_seed(caminho: Path) -> list[dict]:
    try:
        noticias = json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []
    for n in noticias:
        n.setdefault("fonte", "seed")
    return noticias


def _rss_para_noticia(entry: dict, indice: int) -> dict:
    """Converto uma entrada de RSS pro schema de notícia do radar.

    Decidi marcar `sentimento: neutro` e `confianca: 0.0` em vez de inventar
    uma classificação porque notei que não existe classificador SVM rodando
    ao vivo nesta API — o `sentimento_svm` do seed foi calculado uma vez,
    offline (ver docs/INTEGRATION_RISKS.md #7). Fingir uma nota de confiança
    aqui seria pior do que admitir que a notícia ainda não foi classificada.
    """
    return {
        "id": f"rss-{indice}",
        "titulo": entry["title"],
        "corpo": entry["summary"] or entry["text"],
        "estrategia": "Mercado Geral",
        "data": date.today().isoformat(),
        "sentimento": "neutro",
        "confianca": 0.0,
        "classificado": False,
        "fonte": "rss",
        "portal": entry["portal"],
    }


def carregar_noticias(caminho: Path) -> list[dict]:
    """Tento RSS ao vivo (EN+PT) primeiro; caio pro seed estático se vier
    vazio ou o fetch falhar — mesmo padrão de degradação já usado pro LLM
    (real -> mock), pra API nunca quebrar por causa de um feed fora do ar."""
    try:
        entradas = fetch_feeds()
    except Exception:  # noqa: BLE001 — robustez: nunca derruba a API
        _log.exception("fetch_feeds falhou; caindo para o seed estático de notícias.")
        entradas = []
    if entradas:
        return [_rss_para_noticia(e, i) for i, e in enumerate(entradas)]
    return _carregar_seed(caminho)


def agregar(noticias: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for n in noticias:
        e = n.get("estrategia", "—")
        g = out.setdefault(e, {"pos": 0, "neg": 0, "neu": 0, "total": 0, "liquido": 0.0})
        s = n.get("sentimento", "neutro")
        g["pos" if s == "positivo" else "neg" if s == "negativo" else "neu"] += 1
        g["total"] += 1
    for g in out.values():
        g["liquido"] = round((g["pos"] - g["neg"]) / g["total"], 2) if g["total"] else 0.0
    return out
