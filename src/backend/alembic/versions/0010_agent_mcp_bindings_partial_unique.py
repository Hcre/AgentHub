"""agent_mcp_bindings: 唯一约束 → 部分唯一(status='active') — rebind 修复

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-03

F1 的 UNIQUE(agent_id, installation_id) 与软删并存导致解绑后无法再绑定。
改为仅对 status='active' 行唯一。（P2，见 models.py AgentMcpBindingModel）
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    if not sa.inspect(conn).has_table("agent_mcp_bindings"):
        return
    # 删旧的全量唯一约束（存在才删）
    uqs = {c["name"] for c in sa.inspect(conn).get_unique_constraints("agent_mcp_bindings")}
    if "uq_agent_mcp_bindings_agent_installation" in uqs:
        op.drop_constraint(
            "uq_agent_mcp_bindings_agent_installation", "agent_mcp_bindings", type_="unique"
        )
    # 建部分唯一索引（仅 active）
    idxs = {i["name"] for i in sa.inspect(conn).get_indexes("agent_mcp_bindings")}
    if "uq_agent_mcp_bindings_active" not in idxs:
        op.create_index(
            "uq_agent_mcp_bindings_active",
            "agent_mcp_bindings",
            ["agent_id", "installation_id"],
            unique=True,
            postgresql_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    conn = op.get_bind()
    if not sa.inspect(conn).has_table("agent_mcp_bindings"):
        return
    idxs = {i["name"] for i in sa.inspect(conn).get_indexes("agent_mcp_bindings")}
    if "uq_agent_mcp_bindings_active" in idxs:
        op.drop_index("uq_agent_mcp_bindings_active", "agent_mcp_bindings")
    op.create_unique_constraint(
        "uq_agent_mcp_bindings_agent_installation",
        "agent_mcp_bindings",
        ["agent_id", "installation_id"],
    )
