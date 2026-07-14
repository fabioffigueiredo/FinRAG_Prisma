"""Popula o Postgres da Meta 1 a partir do SimuladorConnector.

Substitui `python3 data/gen_seed.py` (que só gerava JSON estático de 1
período/1 dimensão) — este script escreve multi-período, 8 dimensões, VaR e
benchmark composto direto no banco.

Uso: cd services/prisma-api && ../../.venv/bin/python -m scripts.seed_db
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db.models import Base  # noqa: E402
from db.repo import popular_do_conector  # noqa: E402
from db.session import SessionLocal, engine  # noqa: E402
from ingestao.simulador import SimuladorConnector  # noqa: E402


def main() -> None:
    Base.metadata.create_all(engine)  # garante tabelas mesmo sem alembic (dev rápido)
    conector = SimuladorConnector()
    db = SessionLocal()
    try:
        popular_do_conector(db, conector)
        print(f"Banco populado: {len(conector.listar_fundos())} fundos × "
              f"{len(conector.obter_periodos(next(iter(conector.listar_fundos())).codigo))} períodos.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
