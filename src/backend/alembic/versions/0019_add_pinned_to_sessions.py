"""add pinned column to sessions table

Revision ID: 0019
Revises: 0018
Create Date: 2026-06-08

t7 B-4-P2-CL01: 会话置顶 — 在 sessions 表新增 pinned 列。
- pinned: Boolean NOT NULL DEFAULT false
- 索引: ix_sessions_pinned (按 pinned=true 排前用)

down_revision = 0018 (head before this migration)。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("sessions")}

    if "pinned" not in columns:
        op.add_column(
            "sessions",
            sa.Column(
                "pinned",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            ),
        )
        op.create_index("ix_sessions_pinned", "sessions", ["pinned"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("sessions")}

    existing_indexes = {i["name"] for i in inspector.get_indexes("sessions")}
    if "ix_sessions_pinned" in existing_indexes:
        op.drop_index("ix_sessions_pinned", table_name="sessions")
    if "pinned" in columns:
        op.drop_column("sessions", "pinned")
