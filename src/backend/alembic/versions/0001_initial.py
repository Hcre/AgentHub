"""initial schema — MVP 表（agents/sessions/messages/tasks/task_events/notifications）

Revision ID: 0001
Revises:
Create Date: 2026-05-21

初始迁移直接从 ORM metadata 建表，保证脚手架开箱即用；
后续变更使用 `alembic revision --autogenerate`。
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# 触发模型注册
import app.infrastructure.db.models  # noqa: F401
from app.infrastructure.db.base import Base

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
