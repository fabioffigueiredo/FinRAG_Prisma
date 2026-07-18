"""Convite/ativação de conta — token de uso único (nunca senha por e-mail,
ver docs/SEGURANCA.md e a pesquisa OWASP Forgot-Password Cheat Sheet linkada
lá). Mesma primitiva de `secrets.token_urlsafe(32)` já usada pro CSRF
(auth.py), reaproveitada aqui pro token de ativação.

Cobre os dois fluxos que convergem no mesmo link:
  1. autocadastro público aprovado por um gestor;
  2. convite direto do gestor (usuário já criado, sem senha ainda).
"""
from __future__ import annotations

import logging
import os
import secrets

import requests

_logger = logging.getLogger("prisma.convite")

TOKEN_EXPIRA_HORAS = 48
SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def gerar_token() -> str:
    return secrets.token_urlsafe(32)


def enviar_email_ativacao(destino: str, nome: str, link: str) -> bool:
    """POST direto na API REST do SendGrid (sem SDK novo — `requests` já é
    dependência do projeto). Nunca lança: falha de e-mail não pode derrubar
    a rota que a chamou (mesma filosofia degrada-sem-cair de `audit.py`) —
    quem chama sempre devolve o link na resposta como rede de segurança.
    """
    api_key = os.environ.get("SENDGRID_API_KEY")
    remetente = os.environ.get("SENDGRID_FROM_EMAIL")
    if not api_key or not remetente:
        _logger.warning("SENDGRID_API_KEY/SENDGRID_FROM_EMAIL não configurados — e-mail de ativação não enviado")
        return False

    corpo_texto = (
        f"Olá, {nome}.\n\n"
        f"Sua conta no Prisma foi liberada. Para ativar, defina sua senha "
        f"neste link (válido por {TOKEN_EXPIRA_HORAS}h):\n{link}\n\n"
        f"Se você não esperava este e-mail, pode ignorá-lo."
    )
    payload = {
        "personalizations": [{"to": [{"email": destino}]}],
        "from": {"email": remetente, "name": "Prisma"},
        "subject": "Ative sua conta Prisma",
        "content": [{"type": "text/plain", "value": corpo_texto}],
    }
    try:
        resp = requests.post(
            SENDGRID_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=payload,
            timeout=10,
        )
        if resp.status_code >= 300:
            _logger.warning("SendGrid recusou o envio: status=%s", resp.status_code)
            return False
        return True
    except requests.RequestException:
        _logger.warning("falha de rede ao enviar e-mail de ativação", exc_info=True)
        return False
