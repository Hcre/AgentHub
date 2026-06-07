"""add favorite columns to templates table

Revision ID: 0017
Revises: 0016
Create Date: 2026-06-08

为 templates 表新增收藏相关列：
- is_favorite: 是否收藏
- favorite_name: 收藏别名
- favorite_description: 收藏描述
- favorite_order: 收藏排序
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("templates")}

    if "is_favorite" not in columns:
        op.add_column(
            "templates",
            sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
    if "favorite_name" not in columns:
        op.add_column(
            "templates",
            sa.Column("favorite_name", sa.String(128), nullable=True),
        )
    if "favorite_description" not in columns:
        op.add_column(
            "templates",
            sa.Column("favorite_description", sa.Text(), nullable=True),
        )
    if "favorite_order" not in columns:
        op.add_column(
            "templates",
            sa.Column("favorite_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        )


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {c["name"] for c in inspector.get_columns("templates")}

    if "favorite_order" in columns:
        op.drop_column("templates", "favorite_order")
    if "favorite_description" in columns:
        op.drop_column("templates", "favorite_description")
    if "favorite_name" in columns:
        op.drop_column("templates", "favorite_name")
    if "is_favorite" in columns:
        op.drop_column("templates", "is_favorite")
