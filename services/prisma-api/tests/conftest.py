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
