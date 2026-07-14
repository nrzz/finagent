"""Add holdings.acquired for per-lot FIFO persistence."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_holding_acquired"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("holdings") as batch:
        batch.add_column(sa.Column("acquired", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("holdings") as batch:
        batch.drop_column("acquired")
