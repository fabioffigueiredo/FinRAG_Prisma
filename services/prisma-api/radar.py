"""Radar de Mercado: ingestão em lote, estado explícito e agregação segura."""
from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from radar_pipeline import LocalFinbertClassifier, classify_entries, status_for
from rss_scraper import fetch_feeds

_log = logging.getLogger(__name__)
JANELA_DEDUP_HORAS = 48
FEED_MAX_HORAS = int(os.environ.get("PRISMA_RADAR_MAX_AGE_HOURS", "24"))
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
    """Persiste o lote e só as manchetes que ainda não estão no banco.

    Decidi deduplicar entre lotes porque notei que, com coleta a cada 10
    minutos, a mesma manchete viva por 24h seria gravada ~144 vezes — o
    feed repetiria itens e a tabela cresceria sem necessidade. O lote em si
    continua registrando quantas foram coletadas (rastreabilidade da coleta).
    """
    from sqlalchemy import select

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
    janela = datetime.now(UTC) - timedelta(hours=JANELA_DEDUP_HORAS)
    fps = [n["fingerprint"] for n in noticias]
    # Chave = manchete + estado de classificação: a MESMA manchete não é
    # regravada, mas uma reclassificação (pendente → classificada) é.
    ja_gravadas = set(db.execute(
        select(RadarNoticia.fingerprint, RadarNoticia.estado, RadarNoticia.sentimento).where(
            RadarNoticia.fingerprint.in_(fps), RadarNoticia.coletada_em >= janela)
    ).tuples()) if fps else set()
    for noticia in noticias:
        chave = (noticia["fingerprint"], noticia["estado"], noticia["sentimento"])
        if chave in ja_gravadas:
            continue
        ja_gravadas.add(chave)
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


def podar(db, dias: int) -> int:
    """Apaga lotes (e suas manchetes) mais antigos que `dias`. Devolve quantos lotes saíram."""
    from sqlalchemy import delete, select

    from db.models import RadarLote, RadarNoticia
    corte = datetime.now(UTC) - timedelta(days=dias)
    ids = list(db.scalars(select(RadarLote.id).where(RadarLote.coletado_em < corte)))
    if not ids:
        return 0
    db.execute(delete(RadarNoticia).where(RadarNoticia.lote_id.in_(ids)))
    db.execute(delete(RadarLote).where(RadarLote.id.in_(ids)))
    db.commit()
    return len(ids)


def _noticia_dict(n) -> dict[str, Any]:
    return {
        "id": f"rss-{n.fingerprint[:16]}", "fingerprint": n.fingerprint, "titulo": n.titulo,
        "link": n.url, "portal": n.portal, "publicada_em": n.publicada_em.isoformat(),
        "coletada_em": n.coletada_em.isoformat(), "relevante": n.relevante, "estado": n.estado,
        "sentimento": n.sentimento, "confianca": n.confianca, "classificador": n.classificador,
        "estrategia": n.estrategia, "elegivel_agregado": n.elegivel_agregado, "fonte": "rss",
    }


def feed_recente(db, *, horas: int = FEED_MAX_HORAS, limite: int = 60,
                 now: datetime | None = None) -> dict[str, Any]:
    """Manchetes relevantes das últimas `horas`, mais novas primeiro, sem
    repetição. Lê do Postgres (fonte da verdade), não da memória do processo."""
    from sqlalchemy import func, select

    from db.models import RadarLote, RadarNoticia
    now = now or datetime.now(UTC)
    ultimo = db.execute(select(RadarLote.id, RadarLote.coletado_em)
                        .order_by(RadarLote.coletado_em.desc()).limit(1)).first()
    linhas = db.scalars(
        select(RadarNoticia)
        .where(RadarNoticia.relevante.is_(True), RadarNoticia.publicada_em >= now - timedelta(hours=horas))
        .order_by(RadarNoticia.publicada_em.desc(), RadarNoticia.id.desc())
        .limit(limite * 3)
    )
    itens, vistos = [], set()
    for n in linhas:
        if n.fingerprint in vistos:
            continue
        vistos.add(n.fingerprint)
        itens.append(_noticia_dict(n))
        if len(itens) >= limite:
            break
    total = db.scalar(select(func.count(RadarLote.id))) or 0
    return {
        "itens": itens,
        "lote_id": ultimo.id if ultimo else None,
        "atualizado_em": ultimo.coletado_em.isoformat() if ultimo else None,
        "lotes": int(total),
    }
