"""Engine/session factory da Meta 1.

Decidi ler a URL do banco de uma env var com um default apontando pro
Postgres de dev (`docker-compose.dev.yml`, porta 55432) porque notei que a
porta 5432 padrão já estava ocupada nesta máquina (Homebrew postgresql@14) —
outras máquinas de dev não precisam saber disso, só sobrescrever a env var.
"""
from __future__ import annotations

import os
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ.get(
    "PRISMA_DATABASE_URL",
    "postgresql+psycopg://prisma:prisma_dev@localhost:55432/prisma",
)

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def get_db() -> Iterator[Session]:
    """Dependency do FastAPI: uma sessão por request, sempre fechada no fim."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
