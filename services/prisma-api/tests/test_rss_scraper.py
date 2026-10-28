import rss_scraper
import time


class _FakeParsed:
    def __init__(self, entries):
        self.entries = entries


def test_fetch_feeds_tolera_portal_indisponivel(monkeypatch):
    def fake_baixar(url):
        if "ft.com" in url:
            raise RuntimeError("feed fora do ar")
        return b"<rss/>"

    def fake_parse(_conteudo):
        return _FakeParsed([{"title": "Mercado fecha em alta", "summary": "Resumo.", "link": "https://x", "published_parsed": time.gmtime()}])

    monkeypatch.setattr(rss_scraper, "_baixar", fake_baixar)
    monkeypatch.setattr(rss_scraper.feedparser, "parse", fake_parse)
    resultado = rss_scraper.fetch_feeds(portals=["Financial Times", "Valor"])
    assert len(resultado) == 1
    assert resultado[0]["portal"] == "Valor"


def test_parse_feed_entries_descarta_sem_titulo_ou_horario():
    entries = [
        {"title": "", "summary": "sem titulo", "published_parsed": time.gmtime()},
        {"title": "Sem horário", "summary": "ok"},
        {"title": "Com título", "summary": "ok", "published_parsed": time.gmtime()},
    ]
    out = rss_scraper.parse_feed_entries(entries, portal="Teste")
    assert len(out) == 1
    assert out[0]["title"] == "Com título"


def test_baixar_usa_timeout_por_requisicao(monkeypatch):
    """Nada de socket.setdefaulttimeout global (afetava a API inteira)."""
    chamadas = {}

    class _Resp:
        content = b"<rss/>"

        def raise_for_status(self):
            pass

    def fake_get(url, timeout=None, headers=None):
        chamadas.update(url=url, timeout=timeout, headers=headers)
        return _Resp()

    monkeypatch.setattr(rss_scraper.requests, "get", fake_get)
    assert rss_scraper._baixar("https://exemplo/rss") == b"<rss/>"
    assert chamadas["timeout"] == rss_scraper._TIMEOUT_SEGUNDOS
    assert "PrismaRadar" in chamadas["headers"]["User-Agent"]
