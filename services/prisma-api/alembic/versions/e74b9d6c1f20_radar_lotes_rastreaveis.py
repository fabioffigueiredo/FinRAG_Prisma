"""radar: lotes e metadados públicos rastreáveis

Revision ID: e74b9d6c1f20
Revises: da37183b664a
Create Date: 2026-08-31 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e74b9d6c1f20"
down_revision: Union[str, None] = "da37183b664a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "radar_lote",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("coletado_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("modelo", sa.String(length=220), nullable=True),
        sa.Column("total_coletadas", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_elegiveis", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("motivo", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_lote_coletado_em", "radar_lote", ["coletado_em"])
    op.create_table(
        "radar_noticia",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("lote_id", sa.Integer(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("titulo", sa.String(length=500), nullable=False),
        sa.Column("url", sa.String(length=1200), nullable=False),
        sa.Column("portal", sa.String(length=120), nullable=False),
        sa.Column("publicada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("coletada_em", sa.DateTime(timezone=True), nullable=False),
        sa.Column("relevante", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("estado", sa.String(length=30), nullable=False),
        sa.Column("sentimento", sa.String(length=16), nullable=True),
        sa.Column("confianca", sa.Float(), nullable=True),
        sa.Column("classificador", sa.String(length=220), nullable=True),
        sa.Column("estrategia", sa.String(length=120), nullable=False, server_default="Mercado geral"),
        sa.Column("elegivel_agregado", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["lote_id"], ["radar_lote.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_radar_noticia_fingerprint", "radar_noticia", ["fingerprint"])
    op.create_index("ix_radar_noticia_lote_id", "radar_noticia", ["lote_id"])
    op.create_index("ix_radar_noticia_publicada_em", "radar_noticia", ["publicada_em"])
    op.create_index("ix_radar_noticia_estado", "radar_noticia", ["estado"])
    op.create_index("ix_radar_noticia_lote_estado", "radar_noticia", ["lote_id", "estado"])


def downgrade() -> None:
    op.drop_index("ix_radar_noticia_lote_estado", table_name="radar_noticia")
    op.drop_index("ix_radar_noticia_fingerprint", table_name="radar_noticia")
    op.drop_index("ix_radar_noticia_estado", table_name="radar_noticia")
    op.drop_index("ix_radar_noticia_publicada_em", table_name="radar_noticia")
    op.drop_index("ix_radar_noticia_lote_id", table_name="radar_noticia")
    op.drop_table("radar_noticia")
    op.drop_index("ix_radar_lote_coletado_em", table_name="radar_lote")
    op.drop_table("radar_lote")
