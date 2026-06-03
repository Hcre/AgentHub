"""create mcp_tool_call_logs

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-03

R1 workspace_id 暂存 session_id 裸 Uuid；R4 trace_id 净新增；
id 为 BigInteger（PG BIGSERIAL 等价，autoincrement）。
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("mcp_tool_call_logs"):
        return
    op.create_table(
        "mcp_tool_call_logs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(32), nullable=False),
        sa.Column("binding_id", sa.Uuid(), nullable=False),
        sa.Column("agent_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("mcp_id", sa.Uuid(), nullable=False),
        sa.Column("tool_name", sa.String(128), nullable=False),
        sa.Column("args_hash", sa.String(64), nullable=False),
        sa.Column("result_code", sa.String(32), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["binding_id"], ["agent_mcp_bindings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mcp_id"], ["mcp_servers.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_mcp_tool_call_logs_created", "mcp_tool_call_logs", ["created_at"])
    op.create_index(
        "idx_mcp_tool_call_logs_workspace_created",
        "mcp_tool_call_logs",
        ["workspace_id", "created_at"],
    )
    op.create_index(
        "idx_mcp_tool_call_logs_agent_created", "mcp_tool_call_logs", ["agent_id", "created_at"]
    )
    op.create_index("idx_mcp_tool_call_logs_trace", "mcp_tool_call_logs", ["trace_id"])


def downgrade() -> None:
    conn = op.get_bind()
    if sa.inspect(conn).has_table("mcp_tool_call_logs"):
        op.drop_table("mcp_tool_call_logs")
