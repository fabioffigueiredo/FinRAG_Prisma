"""Radar de Mercado: carga das notícias classificadas e agregado por estratégia."""
import json
from pathlib import Path


def carregar_noticias(caminho: Path) -> list[dict]:
    try:
        return json.loads(Path(caminho).read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return []


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
