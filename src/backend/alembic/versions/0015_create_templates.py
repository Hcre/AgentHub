"""create templates + template_sources tables, add agents.created_from_template_id

Revision ID: 0015
Revises: 0014
Create Date: 2026-06-07

新增 Agent 模板系统：
- templates 表：Agent 模板（从 wshobson/skills 等源同步）
- template_sources 表：模板源仓库注册
- agents 表新增 created_from_template_id 列
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    # --- templates ---
    if "templates" not in existing:
        op.create_table(
            "templates",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("source", sa.String(16), nullable=False, server_default="wshobson"),
            sa.Column("source_path", sa.String(1024), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("model_tier", sa.String(16), nullable=False, server_default="inherit"),
            sa.Column("tools", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("color", sa.String(7), nullable=True),
            sa.Column("display_name_zh", sa.String(128), nullable=True),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column(
                "recommended_skills",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
            sa.Column(
                "compatible_agent_systems",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
            sa.Column(
                "compatible_providers",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'[]'::json"),
            ),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_templates_name", "templates", ["name"])

    # --- template_sources ---
    if "template_sources" not in existing:
        op.create_table(
            "template_sources",
            sa.Column("id", sa.String(128), primary_key=True),
            sa.Column("url", sa.String(1024), nullable=False),
            sa.Column("branch", sa.String(128), nullable=False, server_default="main"),
            sa.Column("description_zh", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("template_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_synced", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )

    # --- agents: add created_from_template_id ---
    inspector = sa.inspect(bind)
    agent_columns = {c["name"] for c in inspector.get_columns("agents")}
    if "created_from_template_id" not in agent_columns:
        op.add_column(
            "agents",
            sa.Column("created_from_template_id", sa.Uuid(), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # Remove column from agents
    agent_columns = {c["name"] for c in inspector.get_columns("agents")}
    if "created_from_template_id" in agent_columns:
        op.drop_column("agents", "created_from_template_id")

    # Drop tables
    existing = set(inspector.get_table_names())
    if "template_sources" in existing:
        op.drop_table("template_sources")
    if "templates" in existing:
        op.drop_index("ix_templates_name", table_name="templates")
        op.drop_table("templates")
