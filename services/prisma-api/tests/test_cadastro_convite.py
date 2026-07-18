"""Cadastro/convite/ativação de conta: autocadastro público + aprovação de
gestor, convite direto do gestor, e o step-up de senha na troca de
dispositivo de 2FA self-service. Nenhum dos dois fluxos de cadastro emite
senha por e-mail — só um token de uso único (ver docs/SEGURANCA.md).
"""
import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

import auth
from db.models import Base, Gestora, Papel, StatusCadastro, Usuario
from db.session import engine as _dev_engine

TEST_DB_URL = _dev_engine.url.set(database="prisma_test")


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
    def _reabrir_savepoint(sess, transacao):
        nonlocal nested
        if not nested.is_active:
            nested = connection.begin_nested()

    yield session

    session.close()
    if trans.is_active:
        trans.rollback()
    connection.close()


@pytest.fixture(scope="module")
def test_app():
    import app as app_module
    with TestClient(app_module.app) as c:
        yield app_module, c


@pytest.fixture()
def client(test_app, db):
    """Limpa cookies a cada teste — mesmo motivo de test_2fa.py: o
    TestClient é reaproveitado pelo módulo inteiro, então um cookie de
    sessão de um teste anterior vazaria pro próximo sem isso."""
    app_module, c = test_app
    app_module.app.dependency_overrides[app_module.get_db] = lambda: db
    c.cookies.clear()
    yield c
    app_module.app.dependency_overrides.clear()


def _gestora_com_usuario(db, matricula="G-CAD-000", papel=Papel.GESTOR, gestora_nome="Gestora Cadastro") -> tuple[Gestora, Usuario]:
    gestora = Gestora(nome=gestora_nome)
    db.add(gestora)
    db.flush()
    usuario = Usuario(matricula=matricula, nome="Gestor Cadastro", senha_hash=auth.hash_senha("Senha-123!"),
                      papel=papel, gestora_id=gestora.id, ativo=True)
    db.add(usuario)
    db.flush()
    return gestora, usuario


def _login(client, matricula: str, senha: str = "Senha-123!"):
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    return client.post("/auth/login", json={"matricula": matricula, "senha": senha},
                       headers={"x-csrf-token": csrf})


def _csrf_headers(client) -> dict:
    return {"x-csrf-token": client.cookies.get("prisma_csrf")}


def _login_completo_2fa(client, matricula: str, segredo: str, senha: str = "Senha-123!"):
    """Gestor/compliance com totp_ativado=True fica preso na etapa 1/2 até
    confirmar o código — `_login` sozinho NÃO abre sessão completa nesse
    caso (só emite o cookie pre2fa). Testar o step-up de troca de
    dispositivo precisa de uma sessão de verdade, senão o 401 que a rota
    devolve é "não autenticado", não "senha atual incorreta" — mascarando
    o próprio comportamento que o teste quer provar."""
    resp = _login(client, matricula, senha)
    assert resp.json()["requer_2fa"] is True
    codigo = pyotp.TOTP(segredo).now()
    resp = client.post("/auth/2fa/verificar", json={"codigo": codigo}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    return resp


def _bootstrap_csrf_publico(client) -> dict:
    """Pra rotas públicas (sem sessão ainda) — o double-submit ainda exige o
    cookie prisma_csrf setado antes, mesmo o /auth/login já faz isso."""
    client.get("/auth/csrf")
    return _csrf_headers(client)


# --- autocadastro -------------------------------------------------------------

def test_autocadastro_cria_usuario_pendente_analista_inativo(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-001")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-1", "nome": "Fulano Pendente", "email": "fulano@example.com",
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 201, resp.text

    novo = db.query(Usuario).filter(Usuario.matricula == "NOVO-CAD-1").one()
    assert novo.status_cadastro == StatusCadastro.PENDENTE
    assert novo.papel == Papel.ANALISTA
    assert novo.ativo is False


def test_autocadastro_matricula_duplicada_retorna_409(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-002")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-2", "nome": "Fulano", "email": "a@example.com",
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 201

    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-2", "nome": "Outro", "email": "b@example.com",
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 409


def test_autocadastro_sem_csrf_e_rejeitado(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-003")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-3", "nome": "Fulano", "email": "a@example.com",
    })
    assert resp.status_code == 403


def test_analista_nao_pode_listar_pendentes(client, db):
    _gestora_com_usuario(db, matricula="A-CAD-001", papel=Papel.ANALISTA)
    _login(client, "A-CAD-001")
    resp = client.get("/usuarios/pendentes")
    assert resp.status_code == 403


def test_gestor_lista_apenas_pendentes_da_propria_gestora(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-004")
    db.add(Usuario(matricula="PEND-A", nome="Pendente A", senha_hash=auth.hash_senha("x"),
                   papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                   status_cadastro=StatusCadastro.PENDENTE))
    outra, _ = _gestora_com_usuario(db, matricula="G-CAD-005", gestora_nome="Outra Gestora Cadastro")
    db.add(Usuario(matricula="PEND-B", nome="Pendente B", senha_hash=auth.hash_senha("x"),
                   papel=Papel.ANALISTA, gestora_id=outra.id, ativo=False,
                   status_cadastro=StatusCadastro.PENDENTE))
    db.flush()

    _login(client, "G-CAD-004")
    resp = client.get("/usuarios/pendentes")
    assert resp.status_code == 200
    matriculas = {u["matricula"] for u in resp.json()["usuarios"]}
    assert matriculas == {"PEND-A"}


# --- aprovação / rejeição ------------------------------------------------------

def test_aprovar_gera_token_e_link_de_ativacao(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-006")
    pendente = Usuario(matricula="PEND-C", nome="Pendente C", senha_hash=auth.hash_senha("x"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                       status_cadastro=StatusCadastro.PENDENTE)
    db.add(pendente)
    db.flush()

    _login(client, "G-CAD-006")
    resp = client.post(f"/usuarios/{pendente.id}/aprovar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    corpo = resp.json()
    assert "/ativar-conta/" in corpo["link_ativacao"]

    db.refresh(pendente)
    assert pendente.status_cadastro == StatusCadastro.APROVADO
    assert pendente.ativo is True
    assert pendente.convite_token is not None
    assert pendente.convite_expira_em is not None


def test_aprovar_pode_ajustar_papel(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-007")
    pendente = Usuario(matricula="PEND-D", nome="Pendente D", senha_hash=auth.hash_senha("x"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                       status_cadastro=StatusCadastro.PENDENTE)
    db.add(pendente)
    db.flush()

    _login(client, "G-CAD-007")
    resp = client.post(f"/usuarios/{pendente.id}/aprovar", json={"papel": "compliance"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    db.refresh(pendente)
    assert pendente.papel == Papel.COMPLIANCE


def test_aprovar_cadastro_ja_aprovado_retorna_400(client, db):
    gestora, admin = _gestora_com_usuario(db, matricula="G-CAD-008")
    _login(client, "G-CAD-008")
    resp = client.post(f"/usuarios/{admin.id}/aprovar", headers=_csrf_headers(client))
    assert resp.status_code == 400


def test_aprovar_usuario_de_outra_gestora_e_rejeitado(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-009")
    outra, pendente_outra = _gestora_com_usuario(db, matricula="G-CAD-010", gestora_nome="Gestora Cadastro Outra")
    pendente_outra.status_cadastro = StatusCadastro.PENDENTE
    db.flush()

    _login(client, "G-CAD-009")
    resp = client.post(f"/usuarios/{pendente_outra.id}/aprovar", headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_rejeitar_cadastro_pendente(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-011")
    pendente = Usuario(matricula="PEND-E", nome="Pendente E", senha_hash=auth.hash_senha("x"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                       status_cadastro=StatusCadastro.PENDENTE)
    db.add(pendente)
    db.flush()

    _login(client, "G-CAD-011")
    resp = client.post(f"/usuarios/{pendente.id}/rejeitar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    db.refresh(pendente)
    assert pendente.status_cadastro == StatusCadastro.REJEITADO
    assert pendente.ativo is False


# --- validação do link / ativação ----------------------------------------------

def test_validar_convite_token_inexistente_retorna_404(client, db):
    resp = client.get("/auth/convite/token-que-nao-existe")
    assert resp.status_code == 404


def test_validar_convite_token_expirado_retorna_410(client, db):
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-012")
    alvo = Usuario(matricula="PEND-F", nome="Pendente F", senha_hash=auth.hash_senha("x"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                  status_cadastro=StatusCadastro.APROVADO,
                  convite_token="token-expirado-123",
                  convite_expira_em=datetime.now(timezone.utc) - timedelta(hours=1))
    db.add(alvo)
    db.flush()

    resp = client.get("/auth/convite/token-expirado-123")
    assert resp.status_code == 410


def test_validar_convite_token_valido_devolve_nome_e_matricula(client, db):
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-013")
    alvo = Usuario(matricula="PEND-G", nome="Pendente G", senha_hash=auth.hash_senha("x"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                  status_cadastro=StatusCadastro.APROVADO,
                  convite_token="token-valido-123",
                  convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(alvo)
    db.flush()

    resp = client.get("/auth/convite/token-valido-123")
    assert resp.status_code == 200
    assert resp.json() == {"nome": "Pendente G", "matricula": "PEND-G"}


def test_ativar_conta_com_token_valido_seta_senha_e_loga(client, db):
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-014")
    alvo = Usuario(matricula="PEND-H", nome="Pendente H", senha_hash=auth.hash_senha("senha-antiga-inutilizavel"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                  status_cadastro=StatusCadastro.APROVADO, trocar_senha_no_proximo_login=True,
                  convite_token="token-ativar-123",
                  convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(alvo)
    db.flush()

    resp = client.post("/auth/ativar-conta", json={"token": "token-ativar-123", "nova_senha": "Senha-Nova-123!"},
                       headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 200, resp.text
    assert "prisma_session" in client.cookies

    db.refresh(alvo)
    assert auth.verificar_senha("Senha-Nova-123!", alvo.senha_hash)
    assert alvo.trocar_senha_no_proximo_login is False
    assert alvo.convite_token is None
    assert alvo.convite_expira_em is None


def test_ativar_conta_token_ja_usado_e_rejeitado(client, db):
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-015")
    alvo = Usuario(matricula="PEND-I", nome="Pendente I", senha_hash=auth.hash_senha("x"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                  status_cadastro=StatusCadastro.APROVADO,
                  convite_token="token-uso-unico-123",
                  convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(alvo)
    db.flush()

    resp = client.post("/auth/ativar-conta", json={"token": "token-uso-unico-123", "nova_senha": "Senha-Nova-123!"},
                       headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 200

    # a 1ª ativação já loga (emitir_cookies_sessao rotaciona o CSRF) — precisa
    # reler o cookie antes da 2ª chamada, senão o 403 de CSRF mascara o 404
    # de token já consumido que este teste quer provar.
    resp = client.post("/auth/ativar-conta", json={"token": "token-uso-unico-123", "nova_senha": "Outra-Senha-123!"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 404


def test_ativar_conta_senha_fraca_e_rejeitada(client, db):
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-016")
    alvo = Usuario(matricula="PEND-J", nome="Pendente J", senha_hash=auth.hash_senha("x"),
                  papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                  status_cadastro=StatusCadastro.APROVADO,
                  convite_token="token-fraco-123",
                  convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(alvo)
    db.flush()

    resp = client.post("/auth/ativar-conta", json={"token": "token-fraco-123", "nova_senha": "123"},
                       headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 422


# --- convite direto do gestor ---------------------------------------------------

def test_analista_nao_pode_criar_convite(client, db):
    _gestora_com_usuario(db, matricula="A-CAD-002", papel=Papel.ANALISTA)
    _login(client, "A-CAD-002")
    resp = client.post("/usuarios/convite", json={
        "matricula": "CONVIDADO-1", "nome": "Convidado", "papel": "analista", "email": "c@example.com",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 403


def test_gestor_cria_convite_direto_ja_aprovado(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-017")
    _login(client, "G-CAD-017")
    resp = client.post("/usuarios/convite", json={
        "matricula": "CONVIDADO-2", "nome": "Convidado Dois", "papel": "gestor", "email": "c2@example.com",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 201, resp.text
    corpo = resp.json()
    assert "/ativar-conta/" in corpo["link_ativacao"]

    convidado = db.query(Usuario).filter(Usuario.matricula == "CONVIDADO-2").one()
    assert convidado.status_cadastro == StatusCadastro.APROVADO
    assert convidado.ativo is True
    assert convidado.papel == Papel.GESTOR
    assert convidado.convite_token is not None
    assert convidado.gestora_id == gestora.id


def test_criar_convite_papel_invalido_retorna_422(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-018")
    _login(client, "G-CAD-018")
    resp = client.post("/usuarios/convite", json={
        "matricula": "CONVIDADO-3", "nome": "Convidado", "papel": "super-admin", "email": "c@example.com",
    }, headers=_csrf_headers(client))
    assert resp.status_code == 422


# --- step-up de senha na troca de dispositivo de 2FA ---------------------------

def test_iniciar_2fa_sem_2fa_ativo_nao_exige_senha(client, db):
    _gestora_com_usuario(db, matricula="G-CAD-019")
    _login(client, "G-CAD-019")
    resp = client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text


def test_trocar_dispositivo_com_senha_errada_e_rejeitado(client, db):
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-020")
    segredo = pyotp.random_base32()
    usuario.totp_secret = segredo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-020", segredo)
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "senha-errada"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "senha atual incorreta"


def test_trocar_dispositivo_com_senha_correta_sobrescreve_segredo(client, db):
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-021")
    segredo_antigo = pyotp.random_base32()
    usuario.totp_secret = segredo_antigo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-021", segredo_antigo)
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "Senha-123!"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(usuario)
    assert usuario.totp_secret != segredo_antigo
    assert usuario.totp_ativado is False  # precisa confirmar de novo com o código do novo segredo


def test_trocar_dispositivo_sem_senha_e_rejeitado(client, db):
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-022")
    segredo = pyotp.random_base32()
    usuario.totp_secret = segredo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-022", segredo)
    resp = client.post("/auth/2fa/iniciar", headers=_csrf_headers(client))
    assert resp.status_code == 401
    assert resp.json()["detail"] == "senha atual incorreta"
