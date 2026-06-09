"""add archived column to sessions table

Revision ID: 0024
Revises: 0023
Create Date: 2026-06-10

M1#2 会话归档 — 在 sessions 表新增 archived 列。
- archived: Boolean NOT NULL DEFAULT false
- 索引: ix_sessions_archived（按 archived=false 过滤主列表用）

接 head 0023（tasks/inbox 创建后），属增量列加法，对历史数据安全。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0024"
down_revision: str | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("sessions")}
    if "archived" not in columns:
        op.add_column(
            "sessions",
            sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
        op.create_index("ix_sessions_archived", "sessions", ["archived"])


def downgrade() -> None:
    op.drop_index("ix_sessions_archived", table_name="sessions")
    op.drop_column("sessions", "archived")