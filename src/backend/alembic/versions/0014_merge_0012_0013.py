"""merge 0012 + 0013 (dual head resolution)

Revision ID: 0014
Revises: 0012, 0013
Create Date: 2026-06-07 20:50

**问题**: plan_ba86c4d0 强收时 backend-p0-p1 (0012) + backend-p2 (0013) 并行 commit,
两个都从 0011 出发 → alembic dual head race, `alembic upgrade head` 报错:

    Multiple head revisions are present for given argument 'head'

**修法**: merge migration, down_revision 同时指向 0012 + 0013, upgrade()/downgrade() 空函数
（merge pointer 即可, 不需要真改 schema — 0012 和 0013 的表都已正确创建）

**已知 gap 来源**: plan_ba86c4d0 强收 ADR-0014 第 4 节"3 Known Gap 接受"段:
> 1. P0-4 Pin session 所有权校验（backend-p0-p1 partial）: alembic 0012+0013 dual head
>    race 未修, merge 0014 migration 留 M5/M6 手动补

**Phase 2 触发**: 2026-06-07 20:50 docker compose up backend 时
docker logs agenthub-backend-1 报 "Multiple head revisions", uvicorn 没启动,
容器持续 restart, 阻塞 Phase 2 E2E。修本文件 + 重建镜像后 backend healthy。

**与 Mavis 强收决策的关系**: ADR-0014 owner override_accept 时已知此 gap 但接受
"endpoint 层 401/403/422 校验在 sessions.py:87-122 完整, 缺 alembic 0014 merge migration"。
本迁移落地后 P0-4 known gap 关闭, STATUS.md M5/M6 手动补清单可移除此条。
"""

from __future__ import annotations

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0014"
down_revision: str | tuple[str, ...] | None = ("0012", "0013")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """merge pointer — 0012 和 0013 已分别正确创建其表, 本迁移无 schema 变更。

    Alembic 仅在 alembic_version 表里把 head 记录从 0012/0013 二选一更新为 0014,
    实际 schema 状态是 0012 ∪ 0013。
    """
    pass


def downgrade() -> None:
    """downgrade 只是从 alembic_version 表移除 0014, 不会撤销 0012 或 0013。

    实际回滚需用 `alembic downgrade 0012` 或 `alembic downgrade 0013` 显式指定。
    """
    pass
