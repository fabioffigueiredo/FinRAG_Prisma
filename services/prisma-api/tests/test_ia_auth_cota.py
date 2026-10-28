"""Honestidade do motor de IA, autenticação/CSRF das rotas cognitivas, cota
por usuário e isolamento de fundo por gestora.

Origem: em out/2026 a IA de produção caiu em modo demo sem erro visível —
chave ausente + modelos Groq retirados — e a UI rotulava texto enlatado como
"gerado ao vivo". As rotas que chamam LLM também eram públicas.
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import auth
import cota
import llm
from db.models import Base, Gestora, Papel, Usuario
from db.session import engine as _dev_engine
from finrag.models import GroqClient

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")


# --- Motor honesto ----------------------------------------------------------

def test_groq_sem_chave_levanta_em_vez_de_mock_silencioso(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(llm.MotorIndisponivel):
        llm.get_backend("groq")


def test_gerar_seguro_sem_chave_rotula_demonstracao(monkeypatch):
    import app as app_module
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    texto, degradado, motor, tokens = app_module._gerar_seguro("groq", "prompt qualquer")
    assert degradado is True
    assert motor == "demo"
    assert tokens == 0
    assert texto.startswith("(Demonstração")


def test_gerar_seguro_trata_resposta_vazia_como_falha(monkeypatch):
    """gpt-oss pode gastar o limite de saída raciocinando e devolver ""."""
    import app as app_module

    class _Vazio:
        def generate(self, *_a, **_k):
            return "   "

    monkeypatch.setattr(app_module, "get_backend", lambda _n: _Vazio())
    _, degradado, motor, _ = app_module._gerar_seguro("groq", "p")
    assert degradado is True and motor == "demo"


def test_gerar_seguro_motor_ok_nao_degrada():
    import app as app_module
    texto, degradado, motor, tokens = app_module._gerar_seguro("mock", "p")
    assert degradado is False and motor == "mock" and texto
    assert tokens > 0  # estimado quando o motor não informa uso


def test_modelo_padrao_nao_e_mais_llama_retirado(monkeypatch):
    monkeypatch.delenv("PRISMA_GROQ_MODEL", raising=False)
    assert llm.groq_model() == "openai/gpt-oss-120b"
    assert "llama" not in llm.groq_model_leve()


def _cliente_groq(modelo: str) -> GroqClient:
    c = GroqClient.__new__(GroqClient)  # sem rede nem chave
    c.model = modelo
    return c


def test_params_gpt_oss_reservam_folga_de_raciocinio():
    p = _cliente_groq("openai/gpt-oss-120b")._params_modelo(220)
    assert p["max_completion_tokens"] == 220 + GroqClient._FOLGA_RACIOCINIO
    assert p["include_reasoning"] is False
    assert p["reasoning_effort"] in {"low", "medium", "high"}
    assert "max_tokens" not in p


def test_params_modelo_sem_raciocinio_mantem_max_tokens():
    assert _cliente_groq("qwen/qwen3.8-27b")._params_modelo(100) == {"max_tokens": 100}


class _Resp:
    def __init__(self, code):
        self.status_code = code


@pytest.mark.parametrize("code,motivo", [
    (401, "revogada"),
    (404, "modelo indisponível"),
])
def test_status_texto_explica_por_que_a_nuvem_caiu(monkeypatch, code, motivo):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(llm.requests, "get", lambda *_a, **_k: _Resp(code))
    monkeypatch.setattr(llm, "ollama_disponivel", lambda: False)
    llm._groq_cache["status"] = None
    st = llm.status_texto()
    assert st["estado"] == "degradado" and st["motor"] == "demo"
    assert motivo in st["motivo"]
    llm._groq_cache["status"] = None


def test_status_texto_disponivel_quando_modelo_responde(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(llm.requests, "get", lambda *_a, **_k: _Resp(200))
    llm._groq_cache["status"] = None
    llm._ultima_falha.clear()
    assert llm.status_texto() == {"estado": "disponivel", "motor": "groq", "modelo": llm.groq_model()}
    llm._groq_cache["status"] = None


# --- Autenticação e CSRF ----------------------------------------------------

@pytest.fixture(scope="module")
def client():
    import app as app_module
    with TestClient(app_module.app) as c:
        yield c


ROTAS = ["/narrativa", "/perguntar", "/analisar", "/ingerir"]
CORPO = {"pergunta": "qual foi o retorno?", "csv": "estrategia,contribuicao_pp\nA,1",
         "backend": "mock", "fundo": "ALFA-33"}


@pytest.mark.parametrize("rota", ROTAS)
def test_rota_cognitiva_sem_sessao_e_recusada(client, rota):
    assert client.post(rota, json=CORPO).status_code == 401


@pytest.mark.parametrize("rota", ROTAS)
def test_rota_cognitiva_sem_sessao_e_401_nao_403(client, rota):
    """Sem sessão a resposta tem que ser 401 ("entre de novo"), não o 403 do
    CSRF ("recarregue a página") — auth é checada antes do CSRF."""
    assert client.post(rota, json=CORPO).status_code == 401


@pytest.mark.parametrize("rota", ROTAS)
def test_rota_cognitiva_com_sessao_sem_csrf_e_403(client, rota, usuario_logado_falso):
    # sessão por cookie (o caso do navegador) sem o header de CSRF
    client.cookies.set("prisma_session", "sessao-falsa")
    try:
        resp = client.post(rota, json=CORPO)
    finally:
        client.cookies.clear()
    assert resp.status_code == 403
    assert "CSRF" in resp.json()["detail"]


def test_rota_cognitiva_com_sessao_responde_e_informa_motor(client, sessao_ia_falsa):
    resp = client.post("/perguntar", json=CORPO)
    assert resp.status_code == 200
    data = resp.json()
    assert data["motor_solicitado"] == "mock" and data["motor_efetivo"] == "mock"
    assert data["degradado"] is False


# --- Isolamento de fundo por gestora ----------------------------------------

def test_fundo_de_outra_gestora_some_do_catalogo(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "_donos_de_fundos", lambda: {"ALFA-33": 99, "BETA-71": 1})
    usuario = auth.UsuarioAtual(matricula="X", nome="X", papel="analista", gestora_id=1, id=1)
    visiveis = app_module._fundos_visiveis(usuario)
    assert "ALFA-33" not in visiveis      # de outra gestora
    assert "BETA-71" in visiveis          # da própria gestora
    assert "GAMA-12" in visiveis          # catálogo fictício sem dono
    with pytest.raises(HTTPException) as exc:
        app_module._fundo_do_usuario(usuario, "ALFA-33")
    assert exc.value.status_code == 404


# --- Cota ---------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    eng = create_engine(TEST_DB_URL, future=True)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """SAVEPOINT que reabre após commit — somar_uso faz commit (ver skill
    prisma-test-commit-isolation)."""
    connection = engine.connect()
    trans = connection.begin()
    session = Session(bind=connection, future=True)
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _reabrir(_sess, _t):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session
    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


@pytest.fixture()
def usuario_db(db):
    g = Gestora(nome="Gestora Cota Teste")
    db.add(g)
    db.flush()
    u = Usuario(matricula="COTA-1", nome="Cota", senha_hash="x", papel=Papel.ANALISTA, gestora_id=g.id)
    db.add(u)
    db.flush()
    return auth.UsuarioAtual(matricula=u.matricula, nome=u.nome, papel="analista",
                             gestora_id=g.id, id=u.id)


def test_somar_uso_acumula_no_mesmo_dia(db, usuario_db):
    cota.somar_uso(db, usuario_db.id, usuario_db.gestora_id, 1200)
    cota.somar_uso(db, usuario_db.id, usuario_db.gestora_id, 800)
    assert cota.tokens_hoje(db, usuario_db.id) == 2000


def test_cota_diaria_estourada_devolve_429(db, usuario_db, monkeypatch):
    monkeypatch.setenv("PRISMA_COTA_TOKENS_DIA", "1000")
    cota.somar_uso(db, usuario_db.id, usuario_db.gestora_id, 1000)
    cota._janelas.pop(usuario_db.id, None)
    with pytest.raises(HTTPException) as exc:
        cota.usuario_ia(usuario=usuario_db, db=db)
    assert exc.value.status_code == 429


def test_rpm_por_usuario_devolve_429(monkeypatch):
    monkeypatch.setenv("PRISMA_COTA_RPM", "2")
    cota._janelas.pop(424242, None)
    cota._checar_rpm(424242)
    cota._checar_rpm(424242)
    with pytest.raises(HTTPException) as exc:
        cota._checar_rpm(424242)
    assert exc.value.status_code == 429
    cota._janelas.pop(424242, None)


# --- Correções da revisão cruzada (Codex) ------------------------------------

def test_fundo_desconhecido_e_404_e_nao_cai_no_primeiro_fundo(monkeypatch):
    import app as app_module
    monkeypatch.setattr(app_module, "_donos_de_fundos", lambda: {})
    usuario = auth.UsuarioAtual(matricula="X", nome="X", papel="analista", gestora_id=1, id=1)
    with pytest.raises(HTTPException) as exc:
        app_module._fundo_do_usuario(usuario, "NAO-EXISTE")
    assert exc.value.status_code == 404


def test_resposta_vazia_ainda_conta_tokens(monkeypatch):
    import app as app_module

    class _VazioComUso:
        ultimo_uso_tokens = 1500

        def generate(self, *_a, **_k):
            return ""

    monkeypatch.setattr(app_module, "get_backend", lambda _n: _VazioComUso())
    _, degradado, _, tokens = app_module._gerar_seguro("groq", "p")
    assert degradado is True
    assert tokens == 1500


def test_health_fica_degradado_apos_falha_real_mesmo_com_modelo_no_catalogo(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_fake")
    monkeypatch.setattr(llm.requests, "get", lambda *_a, **_k: _Resp(200))
    monkeypatch.setattr(llm, "ollama_disponivel", lambda: False)
    llm._groq_cache["status"] = None
    llm._ultima_falha.clear()
    llm._ultimo_sucesso.clear()
    llm.registrar_falha("groq", RuntimeError("rate limit"))
    st = llm.status_texto()
    assert st["estado"] == "degradado"
    assert "_mono" not in st.get("ultima_falha", {})
    llm.registrar_sucesso("groq")
    assert llm.status_texto()["estado"] == "disponivel"
    llm._groq_cache["status"] = None
    llm._ultima_falha.clear()
    llm._ultimo_sucesso.clear()


def test_auditoria_filtra_por_gestora(tmp_path, monkeypatch):
    import audit
    monkeypatch.setattr(audit, "_FORCAR_ARQUIVO", True)
    monkeypatch.setattr(audit, "AUDIT_PATH", tmp_path / "consultas.jsonl")
    audit.registrar(rota="/perguntar", fundo="ALFA-33", pergunta="da gestora 1", backend="mock",
                    latency_ms=1, fontes=[], bloqueados=[], resposta="r",
                    extra={"ator_matricula": "123", "gestora_id": 1})
    audit.registrar(rota="/perguntar", fundo="ALFA-33", pergunta="da gestora 2", backend="mock",
                    latency_ms=1, fontes=[], bloqueados=[], resposta="r",
                    extra={"ator_matricula": "123", "gestora_id": 2})
    perguntas = [e["pergunta"] for e in audit.ler(gestora_id=1)]
    assert perguntas == ["da gestora 1"]
    assert [e["pergunta"] for e in audit.ler(ator_matricula="123", gestora_id=2)] == ["da gestora 2"]


def test_bearer_sem_cookie_dispensa_csrf(client, sessao_ia_falsa):
    """CSRF protege credencial de cookie; cliente Bearer (scripts) não tem cookie."""
    import app as app_module
    from tests.conftest import dependencias_registradas
    # remove só o override do CSRF/cota para exercitar usuario_com_csrf de verdade
    app_module.app.dependency_overrides.pop(cota.usuario_ia, None)
    usuario = sessao_ia_falsa
    for dep in dependencias_registradas(app_module.app, "get_usuario_atual") | {auth.get_usuario_atual}:
        app_module.app.dependency_overrides[dep] = lambda: usuario
    import cota as cota_mod
    original = cota_mod.tokens_hoje
    cota_mod.tokens_hoje = lambda *_a, **_k: 0
    try:
        resp = client.post("/ingerir", json=CORPO, headers={"Authorization": "Bearer x"})
        assert resp.status_code == 200
    finally:
        cota_mod.tokens_hoje = original
        for dep in dependencias_registradas(app_module.app, "get_usuario_atual") | {auth.get_usuario_atual}:
            app_module.app.dependency_overrides.pop(dep, None)
