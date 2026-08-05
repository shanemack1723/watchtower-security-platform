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
    op.execute(
        """
        ALTER TABLE security_events
        ALTER COLUMN record_id TYPE BIGINT
        USING record_id::BIGINT
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE security_events
        ALTER COLUMN record_id TYPE INTEGER
        USING record_id::INTEGER
        """
    )