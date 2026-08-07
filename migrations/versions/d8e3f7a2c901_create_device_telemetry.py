"""Create device telemetry table.

Revision ID: d8e3f7a2c901
Revises: b4c1ff8c0f6e
Create Date: 2026-08-06
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e3f7a2c901"
down_revision: Union[str, Sequence[str], None] = "b4c1ff8c0f6e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "device_telemetry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("cpu_percent", sa.Float(), nullable=False),
        sa.Column("memory_percent", sa.Float(), nullable=False),
        sa.Column("disk_total_gb", sa.Float(), nullable=False),
        sa.Column("disk_free_gb", sa.Float(), nullable=False),
        sa.Column("uptime_seconds", sa.BigInteger(), nullable=False),
        sa.Column(
            "collected_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["device_id"],
            ["devices.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index(
        op.f("ix_device_telemetry_device_id"),
        "device_telemetry",
        ["device_id"],
        unique=False,
    )

    op.create_index(
        op.f("ix_device_telemetry_collected_at"),
        "device_telemetry",
        ["collected_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_device_telemetry_collected_at"),
        table_name="device_telemetry",
    )

    op.drop_index(
        op.f("ix_device_telemetry_device_id"),
        table_name="device_telemetry",
    )

    op.drop_table("device_telemetry")