"""Change event record IDs to bigint

Revision ID: b4c1ff8c0f6e
Revises: c61701677166
Create Date: 2026-08-05 12:57:21.368250

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b4c1ff8c0f6e'
down_revision: Union[str, Sequence[str], None] = 'c61701677166'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # SQLite INTEGER already supports 64-bit values.
    if bind.dialect.name == "sqlite":
        return

    op.alter_column(
        "security_events",
        "record_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "sqlite":
        return

    op.alter_column(
        "security_events",
        "record_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )