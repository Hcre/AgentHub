"""create mcp_servers

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-03

二次对账口径（README-REVISION §9）：R2 created_by 裸 Uuid 无 FK；
R10 可移植类型（JSON / String / 无 GIN）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("mcp_servers"):
        return
    op.create_table(
        "mcp_servers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("slug", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("transport", sa.String(32), nullable=False),
        sa.Column("config_schema", sa.JSON(), nullable=False),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("args_hash", sa.String(64), nullable=False),
        sa.Column("version", sa.String(32), server_default="1.0.0", nullable=False),
        sa.Column("latest", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("official", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), server_default="draft", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("dry_run_result", sa.JSON(), nullable=True),
        sa.Column("dry_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("install_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("name", name="uq_mcp_servers_name"),
        sa.UniqueConstraint("slug", name="uq_mcp_servers_slug"),
    )
    op.create_index("idx_mcp_servers_name", "mcp_servers", ["name"])
    op.create_index("idx_mcp_servers_slug", "mcp_servers", ["slug"])
    op.create_index("idx_mcp_servers_args_hash", "mcp_servers", ["args_hash"])
    op.create_index("idx_mcp_servers_status", "mcp_servers", ["status"])
    op.create_index("idx_mcp_servers_status_latest", "mcp_servers", ["status", "latest"])


def downgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("mcp_servers"):
        op.drop_table("mcp_servers")
