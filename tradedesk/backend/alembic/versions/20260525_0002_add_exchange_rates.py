"""add exchange_rates table

Revision ID: 20260525_0002
Revises: 20260524_0001
Create Date: 2026-05-25 00:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = "20260525_0002"
down_revision = "20260524_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exchange_rates",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("currency_from", sa.String(length=8), nullable=False),
        sa.Column("currency_to", sa.String(length=8), nullable=False),
        sa.Column("rate", sa.Numeric(18, 8), nullable=False),
        sa.Column("effective_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
