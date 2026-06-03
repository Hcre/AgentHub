"""
[文件路径] src/agenthub/infrastructure/acl_migration/steps/apply.py
[文件职责] M-C09 ApplyStep：向 M-C05 提交新规则集
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09 / IC-012（来自 DD-001）
[功能描述]
  功能1: 接收待应用规则集（从 ctx.rules 读取）
  功能2: 调用 M-C05 apply 写入后端（iptables/docker/ipset）
  功能3: 记录 applied_rule_ids 供后续 verify/commit/compensate 使用
[输入输出]
  输入: ctx{workspace_id, trace_id, rules, snapshot}
  输出: ctx 新增 applied_rule_ids / apply_error
[依赖关系]
  依赖文件: .base
  跨模块依赖（仅接口）: infrastructure.network_acl（M-C05, IC-012, apply）
  被依赖文件: .orchestrator, .compensator
[注意事项]
  注意1: 必须在 snapshot 之后执行
  注意2: apply 失败时回退到 snapshot 恢复（由 Compensator 触发）
  注意3: 写入必须事务性（要么全成功要么全失败）
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:MD-MCP-M-C09/IC-012]
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from .base import MigrationStep


@dataclass(frozen=True)
class ApplyPayload:
    """
    [类名] ApplyPayload
    [职责] Apply 步骤入参载体
    [关联设计规范] IC-012
    [属性]
      属性1: workspace_id
      属性2: rules - 待应用规则
      属性3: trace_id
    [来源标注] [DD-001:IC-012]
    """

    workspace_id: uuid.UUID
    rules: List[dict]
    trace_id: uuid.UUID


class ApplyStep(MigrationStep):
    """
    [类名] ApplyStep
    [职责] 应用新规则集到 ACL 后端
    [关联设计规范] MD-MCP-M-C09 / IC-012
    [属性]
      属性1: step_name = "apply"
      属性2: order = 1
    [方法列表]
      方法1: forward(ctx) → dict - 调 M-C05 apply
      方法2: compensate(ctx) → None - 调 M-C05 revoke
    [异常处理]
      异常1: ApplyFailed - 调 M-C05 失败 → 触发 snapshot 恢复
      异常2: ACLConflict (409) - 规则冲突 → 直接 rollback
    [并发安全] M-C05 per-ws 串行
    [幂等性] 是；rule_hash 去重
    [性能约束] P95 ≤ 10s
    [来源标注] [DD-001:MD-MCP-M-C09] + [DD-001:IC-012]
    """

    step_name: str = "apply"
    order: int = 1

    async def forward(self, ctx: dict) -> dict:
        """
        [函数名] forward
        [职责] 调 M-C05 apply 应用规则集
        [关联接口契约] IC-012 (apply)
        [参数说明]
          参数1: ctx dict 必填 含 workspace_id/rules/snapshot_hash
        [返回值] dict ctx 新增 applied_rule_ids
        [错误码]
          错误码1: MIGRATION_APPLY_FAILED 500
          错误码2: ACL_CONFLICT 409 - 透传 M-C05
        [前置条件] snapshot 已生成
        [后置条件] M-C05 后端规则已生效
        [性能约束] P95 ≤ 10s
        [来源标注] [DD-001:MD-MCP-M-C09/IC-012]
        """
        ...

    async def compensate(self, ctx: dict) -> None:
        """
        [函数名] compensate
        [职责] 撤销已应用的规则（调 M-C05 revoke）
        [关联接口契约] IC-012 (revoke)
        [参数说明]
          参数1: ctx dict 必填 含 applied_rule_ids
        [返回值] None
        [错误码] MIGRATION_REVOKE_FAILED 500
        [前置条件] apply 已 forward
        [后置条件] M-C05 后端规则已撤销
        [来源标注] [DD-001:MD-MCP-M-C09/IC-012]
        """
        ...
