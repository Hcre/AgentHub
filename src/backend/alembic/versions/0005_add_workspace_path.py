"""add workspace_path to sessions

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-29
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("sessions")]
    if "workspace_path" not in columns:
        op.add_column(
            "sessions",
            sa.Column("workspace_path", sa.Text(), server_default="", nullable=False),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [c["name"] for c in inspector.get_columns("sessions")]
    if "workspace_path" in columns:
        op.drop_column("sessions", "workspace_path")
