"""add template_name to agents table

Revision ID: 0018
Revises: 0017
Create Date: 2026-06-08

为 agents 表新增 template_name 列：
- template_name: 创建时使用的模板名称（冗余存储，方便查询）
- created_from_template_id 已在 0015 中创建，不做重复操作
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("agents")}

    if "template_name" not in columns:
        op.add_column(
            "agents",
            sa.Column("template_name", sa.String(128), nullable=True),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("agents")}

    if "template_name" in columns:
        op.drop_column("agents", "template_name")
