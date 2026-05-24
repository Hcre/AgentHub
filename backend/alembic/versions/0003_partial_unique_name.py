"""Fix: agent name uniqueness only for active (non-deleted) agents.

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0003"
down_revision: str = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Drop old global unique index
    op.drop_index("ix_agents_name", table_name="agents")
    # Create partial unique index: name unique only among active (non-deleted) agents
    op.create_index(
        "ix_agents_name_active",
        "agents",
        ["name"],
        unique=True,
        postgresql_where="is_deleted = false",
    )


def downgrade() -> None:
    op.drop_index("ix_agents_name_active", table_name="agents")
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)
