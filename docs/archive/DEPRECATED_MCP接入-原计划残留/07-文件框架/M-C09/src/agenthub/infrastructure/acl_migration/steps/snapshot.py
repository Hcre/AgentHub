"""
[文件路径] src/agenthub/infrastructure/acl_migration/steps/snapshot.py
[文件职责] M-C09 SnapshotStep：生成 ACL 当前快照
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09（来自 DD-001）
[功能描述]
  功能1: 调用 M-C05 导出当前 workspace 的全部 ACL 规则
  功能2: 计算 snapshot_hash（SHA256）作为幂等键
  功能3: 写入 mcp_migration_snapshot 表（用于回滚）
[输入输出]
  输入: ctx{workspace_id, trace_id}
  输出: ctx 新增 snapshot / snapshot_hash
[依赖关系]
  依赖文件: .base
  跨模块依赖（仅接口）: infrastructure.network_acl（M-C05, IC-012, list）
  被依赖文件: .orchestrator
[注意事项]
  注意1: snapshot 必须在 apply 之前完成，否则 apply 失败无法回滚
  注意2: snapshot_hash 是幂等键唯一来源
  注意3: 快照表 append-only，永不 UPDATE/DELETE
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:快照表名 mcp_migration_snapshot]
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

from .base import MigrationStep


@dataclass(frozen=True)
class SnapshotData:
    """
    [类名] SnapshotData
    [职责] 快照数据不可变载体
    [关联设计规范] MD-MCP-M-C09
    [属性]
      属性1: workspace_id - 工作空间 ID
      属性2: rules - 规则列表（来自 M-C05 list）
      属性3: snapshot_hash - 规则集 SHA256
      属性4: created_at - 创建时间
    [来源标注] [DD-M推断:载体设计]
    """

    workspace_id: uuid.UUID
    rules: List[dict]
    snapshot_hash: str
    created_at: datetime = field(default_factory=datetime.utcnow)


class SnapshotStep(MigrationStep):
    """
    [类名] SnapshotStep
    [职责] 创建当前 ACL 快照
    [关联设计规范] MD-MCP-M-C09
    [属性]
      属性1: step_name = "snapshot"
      属性2: order = 0
    [方法列表]
      方法1: forward(ctx) → dict - 调 M-C05 list + 持久化
      方法2: compensate(ctx) → None - 标记为不可补偿（仅清理临时缓存）
    [异常处理]
      异常1: SnapshotFailed - M-C05 list 失败
    [并发安全] per-ws 串行
    [幂等性] 是；(ws_id, snapshot_hash) 去重
    [来源标注] [DD-001:MD-MCP-M-C09] + [DD-001:IC-012]
    """

    step_name: str = "snapshot"
    order: int = 0

    async def forward(self, ctx: dict) -> dict:
        """
        [函数名] forward
        [职责] 导出当前 ACL 规则并写入快照表
        [关联接口契约] IC-012 (M-C05 list)
        [参数说明]
          参数1: ctx dict 必填 含 workspace_id/trace_id
        [返回值] dict ctx 新增 snapshot / snapshot_hash
        [错误码] MIGRATION_SNAPSHOT_FAILED 500
        [前置条件] M-C05 可达
        [后置条件] mcp_migration_snapshot 新增条目
        [性能约束] P95 ≤ 5s
        [来源标注] [DD-001:MD-MCP-M-C09/IC-012]
        """
        ...

    async def compensate(self, ctx: dict) -> None:
        """
        [函数名] compensate
        [职责] snapshot 步骤无需反向撤销（快照本身是只读资产）
        [参数说明]
          参数1: ctx dict 必填
        [返回值] None
        [错误码] 无
        [前置条件] 步骤已 forward
        [后置条件] 无副作用
        [来源标注] [DD-M推断:snapshot 是"非副作用步骤"，compensate 为 no-op]
        """
        ...
