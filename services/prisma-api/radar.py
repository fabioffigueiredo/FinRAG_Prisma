"""Radar de Mercado: ingestão em lote, estado explícito e agregação segura."""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from radar_pipeline import LocalFinbertClassifier, classify_entries, status_for
from rss_scraper import fetch_feeds

_log = logging.getLogger(__name__)
_runtime_classifier: LocalFinbertClassifier | None = None
_runtime_classifier_initialized = False


def classifier_for_runtime():
    """Só habilita o modelo após avaliação e configuração explícita."""
    global _runtime_classifier, _runtime_classifier_initialized
    if os.environ.get("PRISMA_RADAR_SENTIMENT_ENABLED", "0") != "1":
        return None
    # O runner em lote não deve recarregar os pesos a cada ciclo de 30 min.
    # Um erro posterior de inferência continua falhando fechado no pipeline.
    if not _runtime_classifier_initialized:
        _runtime_classifier = LocalFinbertClassifier()
        _runtime_classifier_initialized = True
    return _runtime_classifier


def carregar_noticias(_: Path | None = None, *, classifier=None, now: datetime | None = None) -> list[dict[str, Any]]:
    """Busca e classifica um lote. Não usa seed como falso dado ao vivo."""
    try:
        entries = fetch_feeds()
    except Exception:  # noqa: BLE001 - o Radar deve degradar sem derrubar a API
        _log.exception("RSS falhou; Radar sem lote atual.")
        entries = []
    runtime_classifier = classifier if classifier is not None else classifier_for_runtime()
    return classify_entries(entries, classifier=runtime_classifier, now=now)


def agregar(noticias: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Agrega exclusivamente classificação local de alta confiança."""
    out: dict[str, dict[str, Any]] = {}
    for n in noticias:
        if not n.get("elegivel_agregado"):
            continue
        e = n.get("estrategia", "Mercado geral")
        g = out.setdefault(e, {"pos": 0, "neg": 0, "neu": 0, "total": 0, "liquido": 0.0})
        s = n.get("sentimento")
        if s not in {"positivo", "negativo", "neutro"}:
            continue
        g["pos" if s == "positivo" else "neg" if s == "negativo" else "neu"] += 1
        g["total"] += 1
    for g in out.values():
        g["liquido"] = round((g["pos"] - g["neg"]) / g["total"], 2) if g["total"] else 0.0
    return out


def refresh(*, classifier=None, now: datetime | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    now = now or datetime.now(UTC)
    runtime_classifier = classifier if classifier is not None else classifier_for_runtime()
    noticias = carregar_noticias(classifier=runtime_classifier, now=now)
    status = status_for(noticias, runtime_classifier)
    status["atualizado_em"] = now.isoformat()
    return noticias, status


def persistir_lote(db, noticias: list[dict[str, Any]], status: dict[str, Any]) -> None:
    """Persiste metadados mínimos de cada lote, inclusive reclassificações."""
    from db.models import RadarLote, RadarNoticia

    lote = RadarLote(
        coletado_em=datetime.fromisoformat(status["atualizado_em"]),
        estado=status["estado"],
        modelo=status.get("modelo"),
        total_coletadas=status["coletadas"],
        total_elegiveis=status["elegiveis"],
        motivo=status.get("motivo"),
    )
    db.add(lote)
    db.flush()
    for noticia in noticias:
        db.add(RadarNoticia(
            lote_id=lote.id,
            fingerprint=noticia["fingerprint"],
            titulo=noticia["titulo"],
            url=noticia["link"],
            portal=noticia["portal"],
            publicada_em=datetime.fromisoformat(noticia["publicada_em"]),
            coletada_em=datetime.fromisoformat(noticia["coletada_em"]),
            relevante=noticia["relevante"],
            estado=noticia["estado"],
            sentimento=noticia["sentimento"],
            confianca=noticia["confianca"],
            classificador=noticia["classificador"],
            estrategia=noticia["estrategia"],
            elegivel_agregado=noticia["elegivel_agregado"],
        ))
    db.commit()
