"""create memories table

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-02

幂等：用 inspector 守卫，兼容「create_all 已建表」与「纯 migration」两种引导路径。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "memories" not in existing:
        op.create_table(
            "memories",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column(
                "agent_id",
                sa.Uuid(),
                sa.ForeignKey("agents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "group_id",
                sa.Uuid(),
                sa.ForeignKey("groups.id", ondelete="CASCADE"),
                nullable=True,
            ),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("scope", sa.String(10), nullable=False),
            sa.Column("name", sa.String(150), nullable=False),
            sa.Column("description", sa.String(300), nullable=False),
            sa.Column("memory_type", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
            sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.CheckConstraint("scope IN ('agent', 'group')", name="ck_memories_scope"),
            sa.CheckConstraint(
                "memory_type IN ('facts', 'preferences', 'procedures', 'context')",
                name="ck_memories_type",
            ),
            sa.CheckConstraint(
                "source IN ('manual', 'chat', 'system')", name="ck_memories_source"
            ),
        )
        op.create_index("idx_memories_agent_scope", "memories", ["agent_id", "scope", "memory_type"])
        op.create_index(
            "idx_memories_group",
            "memories",
            ["group_id"],
            postgresql_where=sa.text("group_id IS NOT NULL"),
        )
        op.create_index(
            "idx_memories_pinned",
            "memories",
            ["agent_id", "scope", "pinned"],
            postgresql_where=sa.text("pinned = true"),
        )
        op.create_index(
            "idx_memories_updated",
            "memories",
            ["agent_id", "scope", sa.text("updated_at DESC")],
        )


def downgrade() -> None:
    op.drop_table("memories")
