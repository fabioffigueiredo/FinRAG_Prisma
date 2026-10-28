"""Feed de manchetes ao vivo (sem classificação) e coletor do Radar.

Origem: em out/2026 o gestor parou de ver notícias — a coleta estava
desligada em produção pela decisão de falha fechada de 31/08. A correção
separa o FEED (manchete pública, não classificada) do SINAL (agregado de
sentimento, que continua bloqueado sem classificador validado).
"""
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

import radar
from db.models import Base, RadarLote, RadarNoticia
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")
AGORA = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, future=True)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _reabrir(_sess, _t):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    # isola das linhas que o servidor de dev já gravou em prisma_test
    session.query(RadarNoticia).delete()
    session.query(RadarLote).delete()
    session.flush()
    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


def _noticia(fp: str, titulo: str, horas_atras: float, relevante=True) -> dict:
    pub = (AGORA - timedelta(hours=horas_atras)).isoformat()
    return {"fingerprint": fp, "titulo": titulo, "link": f"https://x/{fp}", "portal": "Teste",
            "publicada_em": pub, "coletada_em": AGORA.isoformat(), "relevante": relevante,
            "estado": "pendente_revisao", "sentimento": None, "confianca": None,
            "classificador": None, "estrategia": "Mercado geral", "elegivel_agregado": False}


def _status(n: int) -> dict:
    return {"estado": "degradado", "atualizado_em": AGORA.isoformat(), "coletadas": n,
            "elegiveis": 0, "modelo": None, "motivo": "x"}


def test_mesma_manchete_em_dois_lotes_e_gravada_uma_vez(db):
    lote = [_noticia("a" * 64, "Selic sobe", 1), _noticia("b" * 64, "Dólar cai", 2)]
    radar.persistir_lote(db, lote, _status(2))
    radar.persistir_lote(db, lote + [_noticia("c" * 64, "Ibovespa fecha em alta", 0.5)], _status(3))
    assert db.scalar(select(RadarLote.id).order_by(RadarLote.id.desc()).limit(1)) is not None
    assert len(list(db.scalars(select(RadarNoticia.fingerprint)))) == 3


def test_feed_traz_so_relevantes_recentes_mais_novas_primeiro(db):
    radar.persistir_lote(db, [
        _noticia("1" * 64, "Juros futuros recuam", 3),
        _noticia("2" * 64, "Bolsa renova máxima", 1),
        _noticia("3" * 64, "Receita de bolo", 1, relevante=False),
        _noticia("4" * 64, "Petróleo dispara", 30),  # fora da janela de 24h
    ], _status(4))
    feed = radar.feed_recente(db, now=AGORA)
    assert [i["titulo"] for i in feed["itens"]] == ["Bolsa renova máxima", "Juros futuros recuam"]
    assert feed["atualizado_em"] is not None


def test_podar_remove_lotes_antigos(db):
    radar.persistir_lote(db, [_noticia("9" * 64, "Crédito privado", 1)],
                         {**_status(1), "atualizado_em": (datetime.now(UTC) - timedelta(days=40)).isoformat()})
    radar.persistir_lote(db, [_noticia("8" * 64, "Câmbio", 1)],
                         {**_status(1), "atualizado_em": datetime.now(UTC).isoformat()})
    assert radar.podar(db, dias=30) == 1
    assert list(db.scalars(select(RadarNoticia.fingerprint))) == ["8" * 64]


# --- Endpoints ----------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    import app as app_module
    with TestClient(app_module.app) as c:
        yield c


def test_feed_exige_sessao(client):
    assert client.get("/radar/feed").status_code == 401


def test_feed_devolve_304_quando_nada_mudou(client, usuario_logado_falso, db, monkeypatch):
    import app as app_module

    @contextmanager
    def _sessao():
        yield db

    radar.persistir_lote(db, [_noticia("e" * 64, "Inflação desacelera", 1)],
                         {**_status(1), "atualizado_em": datetime.now(UTC).isoformat()})
    monkeypatch.setattr(app_module, "SessionLocal", _sessao)
    primeira = client.get("/radar/feed")
    assert primeira.status_code == 200
    corpo = primeira.json()
    assert corpo["classificacao"] == "nao_classificado"
    assert corpo["itens"][0]["titulo"] == "Inflação desacelera"
    assert "sentimento" not in corpo["itens"][0]
    etag = primeira.headers["etag"]
    assert client.get("/radar/feed", headers={"If-None-Match": etag}).status_code == 304


def test_radar_agregado_continua_em_falha_fechada(client):
    """Manchete não classificada nunca vira sinal (decisão de 31/08)."""
    import app as app_module
    app_module._definir_radar([_noticia("f" * 64, "Selic", 1)], _status(1))
    corpo = client.get("/radar").json()
    assert corpo["ok"] is False
    assert corpo["noticias"] == []
    assert corpo["agregado"] == {}


def test_ciclo_sobrevive_a_excecao(monkeypatch):
    import app as app_module
    chamadas = []

    def _falha_uma_vez():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise RuntimeError("feed quebrado")
        app_module._RADAR_STOP.set()

    monkeypatch.setattr(app_module, "_atualizar_radar", _falha_uma_vez)
    monkeypatch.setattr(app_module._RADAR_STOP, "wait", lambda _t: app_module._RADAR_STOP.is_set())
    app_module._RADAR_STOP.clear()
    app_module._ciclo_radar(imediata=True)
    assert len(chamadas) == 2
    app_module._RADAR_STOP.clear()


@pytest.mark.parametrize("titulo,esperado", [
    ("Partido acusa fraude nas eleições", False),        # "ações" dentro de "eleições"
    ("Fim da escala 6x1 no governo federal", False),     # "fed" dentro de "federal"
    ("Intercambistas buscam intercâmbio", False),        # "câmbio" dentro de "intercâmbio"
    ("Ações da Petrobras sobem", True),
    ("Fed mantém juros", True),
    ("Dólar cai e câmbio estabiliza", True),
])
def test_relevancia_casa_palavra_inteira(titulo, esperado):
    from radar_pipeline import _is_relevant
    assert _is_relevant(titulo) is esperado


@pytest.mark.parametrize("titulo", ["Bolsas asiáticas fecham em alta", "Treasury yields jump",
                                    "Emissões de debêntures batem recorde", "Dólares em queda"])
def test_relevancia_aceita_flexoes(titulo):
    from radar_pipeline import _is_relevant
    assert _is_relevant(titulo) is True


def test_reclassificacao_da_mesma_manchete_e_gravada(db):
    pendente = _noticia("r" * 64, "Selic sobe", 1)
    radar.persistir_lote(db, [pendente], _status(1))
    classificada = {**pendente, "estado": "classificado_local", "sentimento": "negativo"}
    radar.persistir_lote(db, [classificada], _status(1))
    estados = sorted(db.scalars(select(RadarNoticia.estado).where(RadarNoticia.fingerprint == "r" * 64)))
    assert estados == ["classificado_local", "pendente_revisao"]
    feed = radar.feed_recente(db, now=AGORA)
    assert [i["estado"] for i in feed["itens"] if i["fingerprint"] == "r" * 64] == ["classificado_local"]


def test_lock_do_radar_e_liberado_na_mesma_conexao(monkeypatch):
    """Regressão: com Session o unlock rodava noutra conexão do pool e o lock
    ficava órfão. Depois de um ciclo, outro try_lock tem de conseguir."""
    import app as app_module
    from sqlalchemy import text
    from db.session import engine
    monkeypatch.setattr(app_module, "refresh", lambda: ([], _status(0)))
    monkeypatch.setattr(app_module, "_persistir_lote_coletado", lambda *_a: None)
    app_module._atualizar_radar()
    with engine.connect() as c:
        pegou = c.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": app_module._RADAR_ADVISORY_KEY}).scalar()
        assert pegou is True
        c.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": app_module._RADAR_ADVISORY_KEY})
        c.commit()
