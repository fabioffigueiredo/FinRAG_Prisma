"""Headers de segurança básicos (Meta 5) — nunca CSP estrita aqui de
propósito: Next.js (payload RSC inline) + Tailwind runtime precisam de
nonce/allowlist cuidadosos que merecem sua própria rodada de testes, não uma
adição apressada. Ver docs/SEGURANCA.md.
"""
from __future__ import annotations

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        # Mesmo gate de PRISMA_ENV que já protege o `secure=` do cookie em auth.py
        if os.environ.get("PRISMA_ENV", "dev") == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response
