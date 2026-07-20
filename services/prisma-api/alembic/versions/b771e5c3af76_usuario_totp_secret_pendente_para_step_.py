"""usuario totp_secret_pendente para step-up de troca de dispositivo

Revision ID: b771e5c3af76
Revises: 6350f4a6ba31
Create Date: 2026-07-20 10:24:07.139151

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b771e5c3af76'
down_revision: Union[str, None] = '6350f4a6ba31'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuario', sa.Column('totp_secret_pendente', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('usuario', 'totp_secret_pendente')
