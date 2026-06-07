"""usage_records + messages ownership columns (P0-4 + P1-2)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-07

P0-4 Pin 消息 session 所有权校验（spec 04-commands §6.1.6 B-1-P0-04）：
- messages.user_id：消息发送者 user，Pin 时做所有权判断
- messages.pinned_by_user_id / pinned_at：Pin 审计字段

P1-2 Token 消耗监控（spec 04-commands §6.6 B-5.3-P1-2）：
- usage_records 表：append-only 日志
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    existing_cols = (
        {col["name"] for col in sa.inspect(bind).get_columns("messages")}
        if "messages" in existing_tables
        else set()
    )

    if "messages" in existing_tables:
        if "user_id" not in existing_cols:
            op.add_column("messages", sa.Column("user_id", sa.Uuid(), nullable=True))
            op.create_index("ix_messages_user_id", "messages", ["user_id"])
        if "pinned_by_user_id" not in existing_cols:
            op.add_column("messages", sa.Column("pinned_by_user_id", sa.Uuid(), nullable=True))
        if "pinned_at" not in existing_cols:
            op.add_column("messages", sa.Column("pinned_at", sa.DateTime(timezone=True), nullable=True))

    if "usage_records" not in existing_tables:
        op.create_table(
            "usage_records",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("agent_id", sa.Uuid(), nullable=True),
            sa.Column("session_id", sa.Uuid(), nullable=False),
            sa.Column("message_id", sa.Uuid(), nullable=True),
            sa.Column("kind", sa.String(16), nullable=False),
            sa.Column("tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("model", sa.String(64), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_usage_records_agent_id", "usage_records", ["agent_id"])
        op.create_index("ix_usage_records_session_id", "usage_records", ["session_id"])
        op.create_index("ix_usage_records_created_at", "usage_records", ["created_at"])
        op.create_index(
            "idx_usage_records_agent_created", "usage_records", ["agent_id", "created_at"]
        )
        op.create_index(
            "idx_usage_records_session_created",
            "usage_records",
            ["session_id", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("idx_usage_records_session_created", table_name="usage_records")
    op.drop_index("idx_usage_records_agent_created", table_name="usage_records")
    op.drop_index("ix_usage_records_created_at", table_name="usage_records")
    op.drop_index("ix_usage_records_session_id", table_name="usage_records")
    op.drop_index("ix_usage_records_agent_id", table_name="usage_records")
    op.drop_table("usage_records")
    op.drop_index("ix_messages_user_id", table_name="messages")
    op.drop_column("messages", "pinned_at")
    op.drop_column("messages", "pinned_by_user_id")
    op.drop_column("messages", "user_id")
