"""Initial schema matching SQLAlchemy models.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-14
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Greenfield: create all tables from metadata.
    # Existing installs that used create_all: stamp this revision after upgrade.
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "users" in set(insp.get_table_names()):
        return
    from finagent.db.models import Base

    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    pass
