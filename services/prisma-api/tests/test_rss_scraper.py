import rss_scraper


class _FakeParsed:
    def __init__(self, entries):
        self.entries = entries


def test_fetch_feeds_tolera_portal_indisponivel(monkeypatch):
    def fake_parse(url):
        if "reuters" in url:
            raise RuntimeError("feed fora do ar")
        return _FakeParsed([{"title": "Mercado fecha em alta", "summary": "Resumo.", "link": "https://x"}])

    monkeypatch.setattr(rss_scraper.feedparser, "parse", fake_parse)
    resultado = rss_scraper.fetch_feeds(portals=["Reuters", "Valor"])
    assert len(resultado) == 1
    assert resultado[0]["portal"] == "Valor"


def test_parse_feed_entries_descarta_sem_titulo():
    entries = [{"title": "", "summary": "sem titulo"}, {"title": "Com título", "summary": "ok"}]
    out = rss_scraper.parse_feed_entries(entries, portal="Teste")
    assert len(out) == 1
    assert out[0]["title"] == "Com título"
