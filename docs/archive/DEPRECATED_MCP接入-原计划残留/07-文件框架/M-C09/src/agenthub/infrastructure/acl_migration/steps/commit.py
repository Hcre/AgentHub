"""
[文件路径] src/agenthub/infrastructure/acl_migration/steps/commit.py
[文件职责] M-C09 CommitStep：写入 mcp_migration_history（终态）
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09 / IC-016（来自 DD-001）
[功能描述]
  功能1: 写入 mcp_migration_history（append-only）
  功能2: 标记迁移终态为 COMMITTED
  功能3: 发布 migration.committed 事件
[输入输出]
  输入: ctx{workspace_id, trace_id, snapshot_hash, applied_rule_ids, verify_result}
  输出: ctx 新增 history_id
[依赖关系]
  依赖文件: .base
  跨模块依赖（仅接口）: data.metadata（M-D01, IC-017）, eventbus（M-EV01, IC-020）
  被依赖文件: .orchestrator
[注意事项]
  注意1: commit 是终态步骤；一旦成功不可回滚
  注意2: history 表 append-only；UPDATE/DELETE 一律禁止
  注意3: 事件发布失败不阻塞 commit 主流程，仅 WARN
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:MD-MCP-M-C09/IC-016/IC-020]
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .base import MigrationStep


@dataclass(frozen=True)
class MigrationHistoryEntry:
    """
    [类名] MigrationHistoryEntry
    [职责] mcp_migration_history 不可变记录
    [关联设计规范] IC-016
    [属性]
      属性1: history_id
      属性2: workspace_id
      属性3: snapshot_hash
      属性4: applied_rule_ids
      属性5: trace_id
      属性6: committed_at
    [来源标注] [DD-001:IC-016]
    """

    history_id: uuid.UUID
    workspace_id: uuid.UUID
    snapshot_hash: str
    applied_rule_ids: List[uuid.UUID]
    trace_id: uuid.UUID
    committed_at: datetime = field(default_factory=datetime.utcnow)


class CommitStep(MigrationStep):
    """
    [类名] CommitStep
    [职责] 提交迁移记录（终态步骤）
    [关联设计规范] MD-MCP-M-C09 / IC-016
    [属性]
      属性1: step_name = "commit"
      属性2: order = 3
    [方法列表]
      方法1: forward(ctx) → dict - 写 history + 发事件
      方法2: compensate(ctx) → None - 不可补偿；raise NotCompensableError
    [异常处理]
      异常1: CommitFailed - 写 history 失败（罕见，PG 不可用）
      异常2: NotCompensableError - commit 后调用 compensate
    [并发安全] per-ws 串行
    [幂等性] 是；(ws_id, snapshot_hash) 去重
    [性能约束] P95 ≤ 2s
    [来源标注] [DD-001:MD-MCP-M-C09/IC-016]
    """

    step_name: str = "commit"
    order: int = 3

    async def forward(self, ctx: dict) -> dict:
        """
        [函数名] forward
        [职责] 写入 mcp_migration_history 并发事件
        [关联接口契约] IC-017 / IC-020
        [参数说明]
          参数1: ctx dict 必填 含 snapshot_hash/applied_rule_ids/verify_result
        [返回值] dict ctx 新增 history_id
        [错误码] MIGRATION_COMMIT_FAILED 500
        [前置条件] verify 已 forward 成功
        [后置条件] history 表新增；事件已发
        [性能约束] P95 ≤ 2s
        [来源标注] [DD-001:MD-MCP-M-C09/IC-016/IC-020]
        """
        ...

    async def compensate(self, ctx: dict) -> None:
        """
        [函数名] compensate
        [职责] commit 不可补偿；抛 NotCompensableError
        [参数说明]
          参数1: ctx dict 必填
        [返回值] None
        [错误码] MIGRATION_NOT_COMPENSABLE 500
        [前置条件] 无（防御性检查）
        [后置条件] 无
        [来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:commit 是终态不可逆]
        """
        ...
