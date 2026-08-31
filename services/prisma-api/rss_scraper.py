"""Coleta de notícias via RSS com feedparser. Tolerante a feeds indisponíveis.

Portado do app FinNLP (`app/services/rss_scraper.py`) — mesma lógica, cópia
adaptada porque o Prisma tem venv própria e não depende do app FinNLP.
"""
from __future__ import annotations
import logging
import re
import socket
from datetime import UTC, datetime
from typing import Any

import feedparser

_log = logging.getLogger(__name__)
_HTML = re.compile(r"<[^>]+>")
_TIMEOUT_SEGUNDOS = 5

# Feeds RSS bilíngues — EN (Reuters, Financial Times, MarketWatch) + PT
# (CNN Brasil, Agência Brasil, Infomoney, Valor), mesma lista do FinNLP.
RSS_FEEDS: dict[str, str] = {
    "Reuters":         "https://feeds.reuters.com/reuters/businessNews",
    "Financial Times": "https://www.ft.com/rss/home",
    "CNN Brasil":      "https://www.cnnbrasil.com.br/economia/feed/",
    "MarketWatch":     "https://feeds.marketwatch.com/marketwatch/topstories/",
    "Agência Brasil":  "https://agenciabrasil.ebc.gov.br/economia/feed",
    "Infomoney":       "https://www.infomoney.com.br/feed/",
    "Valor":           "https://valor.globo.com/rss/home/",
}


def _strip_html(text: str) -> str:
    return _HTML.sub(" ", text or "").strip()


def parse_feed_entries(entries: list[dict], portal: str) -> list[dict[str, Any]]:
    """Normaliza entradas de um feed em dicts padronizados. Descarta sem título."""
    out: list[dict] = []
    for e in entries:
        title = _strip_html(e.get("title", ""))
        if not title:
            continue
        summary = _strip_html(e.get("summary", ""))
        published = e.get("published_parsed") or e.get("updated_parsed")
        if not published:
            # Sem horário de publicação não existe como aplicar a janela de
            # frescor de forma honesta. O item é descartado antes do Radar.
            continue
        try:
            published_at = datetime(*published[:6], tzinfo=UTC).isoformat()
        except (TypeError, ValueError):
            continue
        out.append({
            "title": title,
            "summary": summary,
            "text": f"{title}. {summary}".strip(),
            "link": e.get("link", ""),
            "portal": portal,
            "published_at": published_at,
        })
    return out


def fetch_feeds(portals: list[str] | None = None, max_per_feed: int = 15) -> list[dict[str, Any]]:
    """Busca e parseia os feeds dos portais ativos. Skip silencioso em falha.

    Decidi limitar o socket a alguns segundos porque notei, rodando contra os
    feeds reais, que um portal lento sem timeout travava o startup da API por
    dezenas de segundos — feedparser não tem parâmetro de timeout próprio, só
    respeita o timeout default do socket.
    """
    portals = list(RSS_FEEDS.keys()) if portals is None else portals
    results: list[dict] = []
    timeout_anterior = socket.getdefaulttimeout()
    socket.setdefaulttimeout(_TIMEOUT_SEGUNDOS)
    try:
        for portal in portals:
            url = RSS_FEEDS.get(portal)
            if not url:
                continue
            try:
                parsed = feedparser.parse(url)
                entries = parsed.entries[:max_per_feed]
                results.extend(parse_feed_entries(entries, portal))
            except Exception as exc:  # noqa: BLE001 — robustez: nunca derruba a API
                _log.warning("Feed '%s' falhou: %s", portal, exc)
    finally:
        socket.setdefaulttimeout(timeout_anterior)
    _log.info("RSS: %d notícias de %d portais.", len(results), len(portals))
    return results
