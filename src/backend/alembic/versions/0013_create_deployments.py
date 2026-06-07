"""create deployments table (P2 deploy card, BDD B-5-P2-DP01)

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-07

补齐：models.py 已定义 DeploymentModel（__tablename__='deployments'），新增此表。
幂等：用 inspector 守卫（与 0011 风格一致）。

字段：
- id (UUID, PK)
- session_id (UUID, index) — R1 裸 UUID 无 FK（沿用 MCP 口径）
- owner_id (UUID, nullable) — R2 JWT sub 裸 UUID 无 FK
- target (String 32) — static_site / container / package
- entry_file (String 256, nullable) — 入口文件
- framework (String 64, nullable) — 框架提示
- status (String 16, default 'queued', index) — 状态机
- stage (String 32, nullable) — 阶段（WS 推送）
- progress (Float, default 0.0) — 0.0-1.0
- preview_url (String 512, nullable) — 静态/容器预览
- download_url (String 512, nullable) — 源码包下载
- build_logs (JSON, default []) — 阶段日志
- error_code / error_message (String/Text, nullable) — 失败时回填
- ttl (Integer, default 3600) — 过期秒数
- created_at / updated_at (DateTime timezone=True)

索引：
- ix_deployments_session_id（FK 列）
- ix_deployments_status（状态过滤）
- ix_deployments_session_status（组合：list 端点）
- ix_deployments_owner_created（owner 维度 list）
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())

    if "deployments" not in existing:
        op.create_table(
            "deployments",
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("session_id", sa.Uuid(), nullable=False),
            sa.Column("owner_id", sa.Uuid(), nullable=True),
            sa.Column("target", sa.String(32), nullable=False),
            sa.Column("entry_file", sa.String(256), nullable=True),
            sa.Column("framework", sa.String(64), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="queued"),
            sa.Column("stage", sa.String(32), nullable=True),
            sa.Column("progress", sa.Float(), nullable=False, server_default="0"),
            sa.Column("preview_url", sa.String(512), nullable=True),
            sa.Column("download_url", sa.String(512), nullable=True),
            sa.Column("build_logs", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
            sa.Column("error_code", sa.String(64), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("ttl", sa.Integer(), nullable=False, server_default="3600"),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
        )
        op.create_index("ix_deployments_session_id", "deployments", ["session_id"])
        op.create_index("ix_deployments_status", "deployments", ["status"])
        op.create_index(
            "idx_deployments_session_status", "deployments", ["session_id", "status"]
        )
        op.create_index(
            "idx_deployments_owner_created", "deployments", ["owner_id", "created_at"]
        )


def downgrade() -> None:
    op.drop_index("idx_deployments_owner_created", table_name="deployments")
    op.drop_index("idx_deployments_session_status", table_name="deployments")
    op.drop_index("ix_deployments_status", table_name="deployments")
    op.drop_index("ix_deployments_session_id", table_name="deployments")
    op.drop_table("deployments")
