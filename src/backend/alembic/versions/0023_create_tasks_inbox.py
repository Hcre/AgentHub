"""add task display cols + create inbox_items table (M3 看板 CRUD + M4 收件箱审批流)

Revision ID: 0023
Revises: 0022
Create Date: 2026-06-09

注：原编号 0020 与 main 链上 0020_add_agent_provider_model_columns 冲突
（preview-tabs 分支独立编号撞车），合并后重排为 0023（接在 0022 之后）。

- tasks 表（0001 create_all 已建）：补两个展示层列 assignee_label / due_label，
  容纳看板 UI 的自由文本 assignee/due（与领域列 assignee_id/due_date 解耦）。
- inbox_items 表（新）：收件箱审批流持久化。
将原 mock 骨架路由（tasks.py / inbox.py）落到真实持久化。
幂等：用 inspector 守卫（与 0011/0013 风格一致）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023"
down_revision: str | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing = set(inspector.get_table_names())

    if "tasks" in existing:
        task_cols = {c["name"] for c in inspector.get_columns("tasks")}
        if "assignee_label" not in task_cols:
            op.add_column(
                "tasks", sa.Column("assignee_label", sa.String(128), nullable=True)
            )
        if "due_label" not in task_cols:
            op.add_column(
                "tasks", sa.Column("due_label", sa.String(64), nullable=True)
            )

    if "inbox_items" not in existing:
        op.create_table(
            "inbox_items",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("type", sa.String(16), nullable=False, server_default="system"),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column("actor", sa.String(128), nullable=True),
            sa.Column("actor_name", sa.String(128), nullable=True),
            sa.Column("when_label", sa.String(64), nullable=True),
            sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("status", sa.String(16), nullable=False, server_default="unread"),
            sa.Column("resolution", sa.String(16), nullable=True),
            sa.Column("session_id", sa.Uuid(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_inbox_items_status", "inbox_items", ["status"])
        op.create_index("ix_inbox_items_type", "inbox_items", ["type"])
        op.create_index(
            "idx_inbox_items_status_created", "inbox_items", ["status", "created_at"]
        )


def downgrade() -> None:
    op.drop_index("idx_inbox_items_status_created", table_name="inbox_items")
    op.drop_index("ix_inbox_items_type", table_name="inbox_items")
    op.drop_index("ix_inbox_items_status", table_name="inbox_items")
    op.drop_table("inbox_items")
    op.drop_column("tasks", "due_label")
    op.drop_column("tasks", "assignee_label")
