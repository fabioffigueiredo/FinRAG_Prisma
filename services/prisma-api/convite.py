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


def _enviar(destino: str, assunto: str, corpo_texto: str, contexto: str) -> bool:
    """POST direto na API REST do SendGrid (sem SDK novo — `requests` já é
    dependência do projeto). Nunca lança: falha de e-mail não pode derrubar
    a rota que a chamou (mesma filosofia degrada-sem-cair de `audit.py`) —
    quem chama sempre devolve o link/segue o fluxo como rede de segurança.
    `contexto` é só pra log (ex.: "ativação", "rejeição")."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    remetente = os.environ.get("SENDGRID_FROM_EMAIL")
    if not api_key or not remetente:
        _logger.warning("SENDGRID_API_KEY/SENDGRID_FROM_EMAIL não configurados — e-mail de %s não enviado", contexto)
        return False

    payload = {
        "personalizations": [{"to": [{"email": destino}]}],
        "from": {"email": remetente, "name": "Prisma"},
        "subject": assunto,
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
            _logger.warning("SendGrid recusou o envio (%s): status=%s", contexto, resp.status_code)
            return False
        return True
    except requests.RequestException:
        _logger.warning("falha de rede ao enviar e-mail de %s", contexto, exc_info=True)
        return False


def enviar_email_ativacao(destino: str, nome: str, link: str) -> bool:
    corpo_texto = (
        f"Olá, {nome}.\n\n"
        f"Sua conta no Prisma foi liberada. Para ativar, defina sua senha "
        f"neste link (válido por {TOKEN_EXPIRA_HORAS}h):\n{link}\n\n"
        f"Se você não esperava este e-mail, pode ignorá-lo."
    )
    return _enviar(destino, "Ative sua conta Prisma", corpo_texto, "ativação")


def enviar_email_rejeicao(destino: str, nome: str) -> bool:
    """Achado #13: rejeição de cadastro era silenciosa — candidato nunca era
    notificado. Nunca revela o motivo da rejeição (decisão do gestor, não
    exposta pela API) nem oferece link de reenvio automático (ver achado #6
    — reabrir um cadastro rejeitado é ação do gestor, não self-service)."""
    corpo_texto = (
        f"Olá, {nome}.\n\n"
        f"Seu pedido de cadastro no Prisma não foi aprovado neste momento. "
        f"Se você acredita que isso é um engano, entre em contato com seu gestor."
    )
    return _enviar(destino, "Sobre seu cadastro no Prisma", corpo_texto, "rejeição")
