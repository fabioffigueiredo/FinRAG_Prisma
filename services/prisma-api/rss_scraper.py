"""Coleta de notícias via RSS com feedparser. Tolerante a feeds indisponíveis.

Portado do app FinNLP (`app/services/rss_scraper.py`) — mesma lógica, cópia
adaptada porque o Prisma tem venv própria e não depende do app FinNLP.
"""
from __future__ import annotations
import logging
import re
from datetime import UTC, datetime
from typing import Any

import feedparser
import requests

_log = logging.getLogger(__name__)
_HTML = re.compile(r"<[^>]+>")
_TIMEOUT_SEGUNDOS = 5
_USER_AGENT = "PrismaRadar/1.0 (+https://wiki.ioi.ia.br/prisma)"

# Feeds RSS bilíngues EN + PT. Revisados em 28/10/2026: Reuters e Agência
# Brasil não resolvem mais DNS, CNN Brasil/economia dá 404 e o endereço antigo
# do Valor dá 400 — trocados por endereços que respondem (Valor via pox.globo)
# e por portais financeiros com RSS público ativo.
RSS_FEEDS: dict[str, str] = {
    "Financial Times": "https://www.ft.com/rss/home/international",
    "MarketWatch":     "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "CNBC":            "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "Infomoney":       "https://www.infomoney.com.br/feed/",
    "Valor":           "https://pox.globo.com/rss/valor/",
    "Exame":           "https://exame.com/feed/",
    "Money Times":     "https://www.moneytimes.com.br/feed/",
    "Investing.com BR": "https://br.investing.com/rss/news.rss",
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


def _baixar(url: str) -> bytes:
    """Baixa o feed com timeout POR REQUISIÇÃO.

    Decidi trocar o socket.setdefaulttimeout por requests com timeout porque
    notei que o default global valia para o processo inteiro enquanto a
    coleta rodava — inclusive para as requisições de usuários que a API
    atendia em paralelo na outra thread.
    """
    resp = requests.get(url, timeout=_TIMEOUT_SEGUNDOS, headers={"User-Agent": _USER_AGENT})
    resp.raise_for_status()
    return resp.content


def fetch_feeds(portals: list[str] | None = None, max_per_feed: int = 15) -> list[dict[str, Any]]:
    """Busca e parseia os feeds dos portais ativos. Skip silencioso em falha."""
    portals = list(RSS_FEEDS.keys()) if portals is None else portals
    results: list[dict] = []
    for portal in portals:
        url = RSS_FEEDS.get(portal)
        if not url:
            continue
        try:
            parsed = feedparser.parse(_baixar(url))
            entries = parsed.entries[:max_per_feed]
            results.extend(parse_feed_entries(entries, portal))
        except Exception as exc:  # noqa: BLE001 — robustez: nunca derruba a API
            _log.warning("Feed '%s' falhou: %s", portal, exc)
    _log.info("RSS: %d notícias de %d portais.", len(results), len(portals))
    return results
