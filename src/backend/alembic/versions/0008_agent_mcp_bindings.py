"""create agent_mcp_bindings

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-03

agent_id FK→agents、installation_id FK→workspace_mcp_installations（均真实表）。
NOTE(P2)：UNIQUE(agent_id, installation_id) 与软删并存的 rebind 问题见 models.py。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("agent_mcp_bindings"):
        return
    op.create_table(
        "agent_mcp_bindings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("installation_id", sa.Uuid(), nullable=False),
        sa.Column("tool_subset", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("unbound_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["installation_id"], ["workspace_mcp_installations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "agent_id", "installation_id", name="uq_agent_mcp_bindings_agent_installation"
        ),
    )
    op.create_index(
        "idx_agent_mcp_bindings_installation", "agent_mcp_bindings", ["installation_id"]
    )
    op.create_index("idx_agent_mcp_bindings_agent", "agent_mcp_bindings", ["agent_id", "status"])


def downgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("agent_mcp_bindings"):
        op.drop_table("agent_mcp_bindings")
