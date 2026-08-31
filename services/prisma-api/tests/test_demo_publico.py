"""A demonstração pública não pode emitir sessão nem simular um provedor."""
from fastapi.testclient import TestClient

from app import app


def test_endpoint_de_login_mock_nao_existe():
    with TestClient(app) as client:
        resp = client.post("/auth/login-microsoft-demo")
    assert resp.status_code == 404


def test_status_demo_nao_expoe_segredo_ou_sessao():
    with TestClient(app) as client:
        resp = client.get("/demo/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dados"] == "fictícios"
    assert "token" not in str(body).lower()
    assert "secret" not in str(body).lower()
