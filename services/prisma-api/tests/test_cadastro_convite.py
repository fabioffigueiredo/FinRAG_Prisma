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
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-001")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-1", "nome": "Fulano Pendente", "email": "fulano@example.com",
        "gestora_id": gestora.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 201, resp.text

    novo = db.query(Usuario).filter(Usuario.matricula == "NOVO-CAD-1").one()
    assert novo.status_cadastro == StatusCadastro.PENDENTE
    assert novo.papel == Papel.ANALISTA
    assert novo.ativo is False
    assert novo.gestora_id == gestora.id


def test_autocadastro_com_duas_gestoras_respeita_a_escolhida(client, db):
    """Regressão: autocadastro antes caía sempre na gestora de menor id,
    ignorando qual tenant o candidato escolheu."""
    _gestora_com_usuario(db, matricula="G-CAD-001B", gestora_nome="Gestora Cadastro Primeira")
    segunda, _ = _gestora_com_usuario(db, matricula="G-CAD-001C", gestora_nome="Gestora Cadastro Segunda")

    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-1B", "nome": "Fulano da Segunda", "email": "fulano2@example.com",
        "gestora_id": segunda.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 201, resp.text

    novo = db.query(Usuario).filter(Usuario.matricula == "NOVO-CAD-1B").one()
    assert novo.gestora_id == segunda.id


def test_autocadastro_com_gestora_inexistente_retorna_422(client, db):
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-1D", "nome": "Fulano", "email": "fulano3@example.com",
        "gestora_id": 999999,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 422


def test_listar_gestoras_publico_devolve_id_e_nome(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-001E", gestora_nome="Gestora Cadastro Listagem")
    resp = client.get("/auth/gestoras")
    assert resp.status_code == 200, resp.text
    nomes = {g["nome"]: g["id"] for g in resp.json()}
    assert nomes.get("Gestora Cadastro Listagem") == gestora.id


def test_autocadastro_matricula_duplicada_retorna_409(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-002")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-2", "nome": "Fulano", "email": "a@example.com",
        "gestora_id": gestora.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 201

    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-2", "nome": "Outro", "email": "b@example.com",
        "gestora_id": gestora.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 409


def test_autocadastro_sem_csrf_e_rejeitado(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-003")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-3", "nome": "Fulano", "email": "a@example.com",
        "gestora_id": gestora.id,
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


def test_desativar_conta_convidada_invalida_o_convite(client, db):
    """Regressão: desativar um convite pendente (PATCH ativo=false) tem
    que revogar o token — senão o convidado reativa a própria conta
    sozinho, desfazendo a decisão do admin."""
    from datetime import datetime, timedelta, timezone
    gestora, admin = _gestora_com_usuario(db, matricula="G-CAD-023")
    convidado = Usuario(matricula="PEND-K", nome="Pendente K", senha_hash=auth.hash_senha("x"),
                        papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                        status_cadastro=StatusCadastro.APROVADO,
                        convite_token="token-revogar-123",
                        convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1))
    db.add(convidado)
    db.flush()
    convidado_id = convidado.id

    _login(client, "G-CAD-023")
    resp = client.patch(f"/usuarios/{convidado_id}", json={"ativo": False}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(convidado)
    assert convidado.ativo is False
    assert convidado.convite_token is None
    assert convidado.convite_expira_em is None

    resp = client.post("/auth/ativar-conta", json={"token": "token-revogar-123", "nova_senha": "Senha-Nova-123!"},
                       headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 404


def test_ativar_conta_zera_bloqueio_acumulado_antes_da_ativacao(client, db):
    """Regressão: a conta convidada já existe ativa (com senha
    inutilizável) desde a criação do convite, então um atacante pode
    esgotar tentativas de login contra ela antes do dono ativar. A
    ativação por token prova posse mais forte que a senha antiga e não
    pode herdar esse bloqueio."""
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-024")
    convidado = Usuario(matricula="PEND-L", nome="Pendente L", senha_hash=auth.hash_senha("x"),
                        papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                        status_cadastro=StatusCadastro.APROVADO,
                        convite_token="token-lockout-123",
                        convite_expira_em=datetime.now(timezone.utc) + timedelta(hours=1),
                        tentativas_falhas=5,
                        bloqueado_ate=datetime.now(timezone.utc) + timedelta(minutes=15))
    db.add(convidado)
    db.flush()

    resp = client.post("/auth/ativar-conta", json={"token": "token-lockout-123", "nova_senha": "Senha-Nova-123!"},
                       headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 200, resp.text

    db.refresh(convidado)
    assert convidado.bloqueado_ate is None
    assert convidado.tentativas_falhas == 0


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


def test_trocar_dispositivo_com_senha_correta_gera_segredo_pendente_sem_desativar(client, db):
    """iniciar não sobrescreve o 2FA ativo — só cria um segredo em staging.
    Abandonar o fluxo aqui não pode deixar a conta sem 2º fator (achado de
    revisão: essa era exatamente a regressão que este teste antes fixava
    como esperada, com `assert totp_ativado is False`)."""
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
    assert usuario.totp_secret == segredo_antigo
    assert usuario.totp_ativado is True
    assert usuario.totp_secret_pendente is not None
    assert usuario.totp_secret_pendente != segredo_antigo


def test_abandonar_troca_de_dispositivo_nao_desativa_2fa(client, db):
    """Regressão: fechar a aba depois do QR (sem confirmar) não pode
    deixar a conta logando só com senha."""
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-021B")
    segredo_antigo = pyotp.random_base32()
    usuario.totp_secret = segredo_antigo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-021B", segredo_antigo)
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "Senha-123!"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    resp = client.post("/auth/logout", headers=_csrf_headers(client))
    resp = _login(client, "G-CAD-021B")
    assert resp.status_code == 200, resp.text
    assert resp.json()["requer_2fa"] is True

    codigo_antigo = pyotp.TOTP(segredo_antigo).now()
    resp = client.post("/auth/2fa/verificar", json={"codigo": codigo_antigo}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text


def test_confirmar_troca_de_dispositivo_promove_segredo_pendente(client, db):
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-021C")
    segredo_antigo = pyotp.random_base32()
    usuario.totp_secret = segredo_antigo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-021C", segredo_antigo)
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "Senha-123!"},
                       headers=_csrf_headers(client))
    segredo_novo = pyotp.parse_uri(resp.json()["otpauth_uri"]).secret

    codigo_novo = pyotp.TOTP(segredo_novo).now()
    resp = client.post("/auth/2fa/confirmar", json={"codigo": codigo_novo}, headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    db.refresh(usuario)
    assert usuario.totp_secret == segredo_novo
    assert usuario.totp_secret_pendente is None
    assert usuario.totp_ativado is True


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


def test_sexta_chamada_a_iniciar_2fa_em_um_minuto_leva_429(client, db):
    """Regressão: /auth/2fa/iniciar não tinha rate limit — um cookie de
    sessão roubado permitia brute force ilimitado da senha via step-up."""
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-025")
    segredo = pyotp.random_base32()
    usuario.totp_secret = segredo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-025", segredo)
    for _ in range(5):
        resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "senha-errada"},
                           headers=_csrf_headers(client))
        assert resp.status_code == 401
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "senha-errada"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 429


# --- plano 008 — achados #5, #6, #9, #10, #11, #12(frontend), #13, #16 --------

def test_aprovar_reabre_cadastro_rejeitado(client, db):
    """Achado #6: um cadastro rejeitado ficava bloqueado pra sempre — agora
    o gestor pode reverter a rejeição aprovando depois."""
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-026")
    rejeitado = Usuario(matricula="PEND-H", nome="Pendente H", senha_hash=auth.hash_senha("x"),
                        papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                        status_cadastro=StatusCadastro.REJEITADO)
    db.add(rejeitado)
    db.flush()

    _login(client, "G-CAD-026")
    resp = client.post(f"/usuarios/{rejeitado.id}/aprovar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    db.refresh(rejeitado)
    assert rejeitado.status_cadastro == StatusCadastro.APROVADO
    assert rejeitado.ativo is True


def test_reenviar_convite_gera_novo_token(client, db):
    """Achado #5: convite expirado não tinha como ser reemitido."""
    from datetime import datetime, timedelta, timezone
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-027")
    aprovado = Usuario(matricula="PEND-I", nome="Pendente I", senha_hash=auth.hash_senha("x"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                       status_cadastro=StatusCadastro.APROVADO,
                       convite_token="token-antigo-123",
                       convite_expira_em=datetime.now(timezone.utc) - timedelta(hours=1))
    db.add(aprovado)
    db.flush()

    _login(client, "G-CAD-027")
    resp = client.post(f"/usuarios/{aprovado.id}/reenviar-convite", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    db.refresh(aprovado)
    assert aprovado.convite_token is not None
    assert aprovado.convite_token != "token-antigo-123"
    assert aprovado.convite_expira_em > datetime.now(timezone.utc)


def test_reenviar_convite_de_conta_ja_ativada_retorna_400(client, db):
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-028")
    ativado = Usuario(matricula="PEND-J", nome="Pendente J", senha_hash=auth.hash_senha("x"),
                      papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=True,
                      status_cadastro=StatusCadastro.APROVADO,
                      convite_token=None, convite_expira_em=None)
    db.add(ativado)
    db.flush()

    _login(client, "G-CAD-028")
    resp = client.post(f"/usuarios/{ativado.id}/reenviar-convite", headers=_csrf_headers(client))
    assert resp.status_code == 400


def test_vigesima_primeira_chamada_a_validar_convite_em_um_minuto_leva_429(client, db):
    """Achado #10: GET /auth/convite/{token} não tinha rate limit, ao
    contrário das outras rotas públicas do fluxo de cadastro/convite."""
    for _ in range(20):
        resp = client.get("/auth/convite/token-que-nao-existe")
        assert resp.status_code == 404
    resp = client.get("/auth/convite/token-que-nao-existe")
    assert resp.status_code == 429


def test_cadastro_com_nome_muito_longo_retorna_422_nao_500(client, db):
    """Achado #11: sem max_length, um nome maior que a coluna Postgres
    (String(120)) gerava DataError não tratado -> 500, não 422."""
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-029")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-29", "nome": "N" * 200, "email": "a@example.com",
        "gestora_id": gestora.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 422


def test_cadastro_com_email_invalido_retorna_422(client, db):
    """Achado #14: email era `str` solto, sem EmailStr."""
    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-030")
    resp = client.post("/auth/cadastro", json={
        "matricula": "NOVO-CAD-30", "nome": "Fulano", "email": "não-é-email",
        "gestora_id": gestora.id,
    }, headers=_bootstrap_csrf_publico(client))
    assert resp.status_code == 422


def test_rejeitar_cadastro_envia_email_de_notificacao(client, db, monkeypatch):
    """Achado #13: rejeição era silenciosa — candidato nunca era
    notificado."""
    chamadas = []
    monkeypatch.setattr("convite.enviar_email_rejeicao",
                        lambda destino, nome: chamadas.append((destino, nome)) or True)

    gestora, _ = _gestora_com_usuario(db, matricula="G-CAD-031")
    pendente = Usuario(matricula="PEND-K", nome="Pendente K", senha_hash=auth.hash_senha("x"),
                       papel=Papel.ANALISTA, gestora_id=gestora.id, ativo=False,
                       email="pendente-k@example.com",
                       status_cadastro=StatusCadastro.PENDENTE)
    db.add(pendente)
    db.flush()

    _login(client, "G-CAD-031")
    resp = client.post(f"/usuarios/{pendente.id}/rejeitar", headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text
    assert chamadas == [("pendente-k@example.com", "Pendente K")]


def test_confirmar_2fa_apos_muitas_chamadas_leva_429(client, db):
    """Achado #16: /auth/2fa/confirmar não tinha rate limit, ao contrário
    da rota irmã /auth/2fa/verificar."""
    gestora, usuario = _gestora_com_usuario(db, matricula="G-CAD-032")
    segredo = pyotp.random_base32()
    usuario.totp_secret = segredo
    usuario.totp_ativado = True
    db.flush()

    _login_completo_2fa(client, "G-CAD-032", segredo)
    resp = client.post("/auth/2fa/iniciar", json={"senha_atual": "Senha-123!"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 200, resp.text

    for _ in range(5):
        resp = client.post("/auth/2fa/confirmar", json={"codigo": "000000"},
                           headers=_csrf_headers(client))
        assert resp.status_code == 401
    resp = client.post("/auth/2fa/confirmar", json={"codigo": "000000"},
                       headers=_csrf_headers(client))
    assert resp.status_code == 429


# --- plano 009 — achado #15: matrícula única por gestora, não globalmente ----

def test_mesma_matricula_em_duas_gestoras_cada_uma_loga_com_a_propria_senha(client, db):
    """Prova de verdade da resolução da ambiguidade: duas gestoras
    diferentes têm cada uma um usuário de matrícula "COLIDE-01" com senhas
    diferentes — gestora_id no login desambigua qual delas."""
    gestora_a = Gestora(nome="Gestora Colisão A")
    gestora_b = Gestora(nome="Gestora Colisão B")
    db.add_all([gestora_a, gestora_b])
    db.flush()
    usuario_a = Usuario(matricula="COLIDE-01", nome="Fulano A", senha_hash=auth.hash_senha("SenhaA-123!"),
                        papel=Papel.ANALISTA, gestora_id=gestora_a.id, ativo=True)
    usuario_b = Usuario(matricula="COLIDE-01", nome="Fulano B", senha_hash=auth.hash_senha("SenhaB-123!"),
                        papel=Papel.ANALISTA, gestora_id=gestora_b.id, ativo=True)
    db.add_all([usuario_a, usuario_b])
    db.flush()

    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={
        "gestora_id": gestora_a.id, "matricula": "COLIDE-01", "senha": "SenhaA-123!",
    }, headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text
    assert resp.json()["nome"] == "Fulano A"

    client.post("/auth/logout", headers={"x-csrf-token": csrf})
    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={
        "gestora_id": gestora_a.id, "matricula": "COLIDE-01", "senha": "SenhaB-123!",
    }, headers={"x-csrf-token": csrf})
    assert resp.status_code == 401, "senha da gestora B não pode logar na gestora A"

    resp = client.post("/auth/login", json={
        "gestora_id": gestora_b.id, "matricula": "COLIDE-01", "senha": "SenhaB-123!",
    }, headers={"x-csrf-token": csrf})
    assert resp.status_code == 200, resp.text
    assert resp.json()["nome"] == "Fulano B"


def test_login_sem_gestora_id_com_matricula_ambigua_e_recusado_sem_erro_500(client, db):
    """Sem gestora_id (chamador antigo), se a matrícula existir em mais de
    uma gestora o login é recusado (mensagem genérica), nunca uma exceção
    ou o usuário errado."""
    gestora_a = Gestora(nome="Gestora Ambígua A")
    gestora_b = Gestora(nome="Gestora Ambígua B")
    db.add_all([gestora_a, gestora_b])
    db.flush()
    db.add_all([
        Usuario(matricula="AMBIGUO-01", nome="X", senha_hash=auth.hash_senha("Senha-123!"),
               papel=Papel.ANALISTA, gestora_id=gestora_a.id, ativo=True),
        Usuario(matricula="AMBIGUO-01", nome="Y", senha_hash=auth.hash_senha("Senha-123!"),
               papel=Papel.ANALISTA, gestora_id=gestora_b.id, ativo=True),
    ])
    db.flush()

    csrf = client.get("/auth/csrf").json()["csrf_token"]
    resp = client.post("/auth/login", json={"matricula": "AMBIGUO-01", "senha": "Senha-123!"},
                       headers={"x-csrf-token": csrf})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "matrícula ou senha inválidas"


def test_login_sem_gestora_id_com_matricula_unica_continua_funcionando(client, db):
    """Compatibilidade: chamador antigo sem gestora_id continua logando
    normalmente quando não há ambiguidade (caso comum, uma matrícula só
    existe numa gestora)."""
    _gestora_com_usuario(db, matricula="G-CAD-033")
    resp = _login(client, "G-CAD-033")
    assert resp.status_code == 200, resp.text
