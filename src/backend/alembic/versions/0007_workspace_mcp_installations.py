"""create workspace_mcp_installations

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-03

二次对账口径（README-REVISION §9）：R1 workspace_id 暂存 session_id 裸 Uuid 无 FK；
R2 installed_by 裸 Uuid 无 FK；仅 mcp_id FK→mcp_servers（真实表）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("workspace_mcp_installations"):
        return
    op.create_table(
        "workspace_mcp_installations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("mcp_id", sa.Uuid(), nullable=False),
        sa.Column("installed_by", sa.Uuid(), nullable=True),
        sa.Column("instance_name", sa.String(128), nullable=False),
        sa.Column("config_overrides", sa.JSON(), nullable=False),
        sa.Column("args_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), server_default="installing", nullable=False),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_health_check_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["mcp_id"], ["mcp_servers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "workspace_id", "instance_name", name="uq_workspace_mcp_installations_workspace_mcp_name"
        ),
    )
    op.create_index("idx_workspace_mcp_installations_mcp", "workspace_mcp_installations", ["mcp_id"])
    op.create_index(
        "idx_workspace_mcp_installations_workspace",
        "workspace_mcp_installations",
        ["workspace_id", "status"],
    )
    op.create_index(
        "idx_workspace_mcp_installations_idempotent",
        "workspace_mcp_installations",
        ["workspace_id", "mcp_id", "args_hash"],
    )


def downgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("workspace_mcp_installations"):
        op.drop_table("workspace_mcp_installations")
