import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """O rate limiter (Meta 5) é global no processo, não por teste — sem
    isso, dezenas de chamadas a /auth/login em toda a suíte estourariam o
    limite de 5/minuto e passariam a devolver 429 pra testes que não têm
    nada a ver com rate limiting."""
    try:
        import app as app_module
        app_module.limiter.reset()
    except Exception:
        pass
    yield


def dependencias_registradas(app, nome: str) -> set:
    """Funções de dependência com esse __name__ como as ROTAS as guardaram.
    test_auth.py faz importlib.reload(auth); depois disso auth.verificar_csrf
    é outro objeto e um override por referência ao módulo não casa mais."""
    achadas = set()
    pilha = [getattr(r, "dependant", None) for r in app.routes]
    while pilha:
        dep = pilha.pop()
        if dep is None:
            continue
        if getattr(dep.call, "__name__", "") == nome:
            achadas.add(dep.call)
        pilha.extend(dep.dependencies)
    return achadas


@pytest.fixture()
def sessao_ia_falsa(monkeypatch):
    """Sessão autenticada falsa para testes que exercitam o COMPORTAMENTO das
    rotas cognitivas (guardrails, degradação), não a autenticação em si —
    essa tem testes próprios em test_ia_auth_cota.py. Desliga CSRF, cota e o
    registro de consumo, e expõe o catálogo fictício inteiro."""
    import app as app_module
    import auth
    import cota

    usuario = auth.UsuarioAtual(matricula="TESTE-IA", nome="Teste IA", papel="analista",
                                gestora_id=1, id=1)
    csrf = dependencias_registradas(app_module.app, "verificar_csrf") | {auth.verificar_csrf}
    app_module.app.dependency_overrides[cota.usuario_ia] = lambda: usuario
    for dep in csrf:
        app_module.app.dependency_overrides[dep] = lambda: None
    monkeypatch.setattr(cota, "registrar", lambda *_a, **_k: None)
    monkeypatch.setattr(app_module, "_donos_de_fundos", lambda: {})
    yield usuario
    app_module.app.dependency_overrides.pop(cota.usuario_ia, None)
    for dep in csrf:
        app_module.app.dependency_overrides.pop(dep, None)


@pytest.fixture()
def usuario_logado_falso():
    """Sessão válida falsa (sem CSRF/cota) para rotas GET autenticadas."""
    import app as app_module
    import auth

    usuario = auth.UsuarioAtual(matricula="TESTE", nome="Teste", papel="analista", gestora_id=1, id=1)
    deps = dependencias_registradas(app_module.app, "get_usuario_atual") | {auth.get_usuario_atual}
    for dep in deps:
        app_module.app.dependency_overrides[dep] = lambda: usuario
    yield usuario
    for dep in deps:
        app_module.app.dependency_overrides.pop(dep, None)
