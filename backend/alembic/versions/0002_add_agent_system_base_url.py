"""Add agent_system and base_url columns to agents table.

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 用 Base.metadata.create_all() 从模型建表，模型更新后列可能已存在，做幂等处理
    from sqlalchemy import inspect

    conn = op.get_bind()
    inspector = inspect(conn)
    existing = {c["name"] for c in inspector.get_columns("agents")}
    if "agent_system" not in existing:
        op.add_column(
            "agents",
            sa.Column("agent_system", sa.String(32), server_default="mock", nullable=False),
        )
    if "base_url" not in existing:
        op.add_column(
            "agents",
            sa.Column("base_url", sa.String(512), nullable=True),
        )


def downgrade() -> None:
    op.drop_column("agents", "base_url")
    op.drop_column("agents", "agent_system")
