"""create memories table (memory system V3)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-05

补齐：models.py 已定义 MemoryModel（__tablename__='memories'），但前面 10 个迁移漏了
这张表——前端调用 /api/memories 触发 SELECT 时报 UndefinedTableError。

幂等：用 inspector 守卫；column 名 metadata 在 PG 里要双引号转义（SQLAlchemy
保留属性名），实际写入时用 "metadata" 名。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
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
            sa.Column("description", sa.String(300), nullable=False, server_default=""),
            sa.Column("memory_type", sa.String(20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False, server_default=""),
            sa.Column("source", sa.String(20), nullable=False, server_default="manual"),
            sa.Column("pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("hits", sa.Integer(), nullable=False, server_default="0"),
            # 列名要双引号包住（"metadata" 是 PG 保留字附近，SQLAlchemy 也要 quote）
            sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_memories_agent_id", "memories", ["agent_id"])
        op.create_index("ix_memories_user_id", "memories", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_memories_user_id", table_name="memories")
    op.drop_index("ix_memories_agent_id", table_name="memories")
    op.drop_table("memories")
