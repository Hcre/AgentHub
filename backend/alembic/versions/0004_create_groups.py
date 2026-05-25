"""create groups and group_members tables

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-25

幂等：用 inspector 守卫，兼容「create_all 已建表」与「纯 migration」两种引导路径。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "groups" not in existing:
        op.create_table(
            "groups",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), server_default="", nullable=False),
            sa.Column("coordinator_id", sa.Uuid(), nullable=False),
            sa.Column("coordinator_config", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        )
        op.create_index("ix_groups_name", "groups", ["name"], unique=True)
        op.create_index("ix_groups_coordinator_id", "groups", ["coordinator_id"])

    if "group_members" not in existing:
        op.create_table(
            "group_members",
            sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
            sa.Column(
                "group_id",
                sa.Uuid(),
                sa.ForeignKey("groups.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "agent_id",
                sa.Uuid(),
                sa.ForeignKey("agents.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("group_id", "agent_id", name="uq_group_member"),
        )
        op.create_index("ix_group_members_group_id", "group_members", ["group_id"])
        op.create_index("ix_group_members_agent_id", "group_members", ["agent_id"])


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("groups")
