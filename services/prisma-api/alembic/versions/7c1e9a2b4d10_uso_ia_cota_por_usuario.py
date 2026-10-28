"""uso_ia (cota diária de IA por usuário) + auditoria_evento.gestora_id

Revision ID: 7c1e9a2b4d10
Revises: e74b9d6c1f20
Create Date: 2026-10-28 10:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c1e9a2b4d10"
down_revision: Union[str, None] = "e74b9d6c1f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "uso_ia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("usuario_id", sa.Integer(), nullable=False),
        sa.Column("gestora_id", sa.Integer(), nullable=False),
        sa.Column("dia", sa.Date(), nullable=False),
        sa.Column("requisicoes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["usuario_id"], ["usuario.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["gestora_id"], ["gestora.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("usuario_id", "dia", name="uq_uso_ia_usuario_dia"),
    )
    op.create_index("ix_uso_ia_usuario_id", "uso_ia", ["usuario_id"])
    op.create_index("ix_uso_ia_gestora_id", "uso_ia", ["gestora_id"])
    op.add_column("auditoria_evento", sa.Column("gestora_id", sa.Integer(), nullable=True))
    op.create_index("ix_auditoria_evento_gestora_id", "auditoria_evento", ["gestora_id"])
    # Backfill: sem isso a trilha anterior some da tela (a leitura agora
    # filtra por gestora). Só preenche quando a matrícula é inequívoca —
    # a matrícula é única por gestora, não global; ambígua fica NULL
    # (falha fechada: invisível, nunca atribuída à gestora errada).
    op.execute("""
        UPDATE auditoria_evento a
           SET gestora_id = u.gestora_id
          FROM usuario u
         WHERE a.gestora_id IS NULL
           AND a.ator_matricula = u.matricula
           AND (SELECT count(*) FROM usuario u2 WHERE u2.matricula = a.ator_matricula) = 1
    """)


def downgrade() -> None:
    op.drop_index("ix_auditoria_evento_gestora_id", table_name="auditoria_evento")
    op.drop_column("auditoria_evento", "gestora_id")
    op.drop_index("ix_uso_ia_gestora_id", table_name="uso_ia")
    op.drop_index("ix_uso_ia_usuario_id", table_name="uso_ia")
    op.drop_table("uso_ia")
