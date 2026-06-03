"""
[文件路径] src/agenthub/infrastructure/acl_migration/compensator.py
[文件职责] M-C09 失败补偿器（反向撤销已执行步骤）
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09（来自 DD-001）
[功能描述]
  功能1: 根据已执行步骤列表构建补偿计划
  功能2: 按反向顺序执行各步的 rollback 子方法
  功能3: 记录补偿执行审计到 mcp_migration_history
[输入输出]
  输入: completed_steps(list[StepResult])、snapshot(SnapshotData)、workspace_id
  输出: 补偿执行结果（成功/部分失败/全失败）
[依赖关系]
  依赖文件: .steps.snapshot, .steps.apply, .steps.verify, .steps.commit
  跨模块依赖（仅接口）: infrastructure.network_acl（M-C05, IC-012, revoke）
  被依赖文件: .orchestrator（仅在 _on_failure 中调用）
[注意事项]
  注意1: 补偿必须幂等（同 snapshot 重复补偿不产生副作用）
  注意2: 补偿失败不应抛异常阻断后续步骤，最多 WARN 记日志
  注意3: 验证步骤（Verify）通常无需回滚（仅校验），仅清理临时探针
  注意4: 提交步骤（Commit）一旦执行不可回滚（终态），出现异常需人工介入
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:补偿链反向序列由 build_plan 生成]
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

# [DD-M推断] 同 orchestrator；保留接口位
# from agenthub.core.logging import get_logger


@dataclass
class CompensationPlan:
    """
    [类名] CompensationPlan
    [职责] 补偿计划（步骤 → rollback handler 映射）
    [关联设计规范] MD-MCP-M-C09
    [属性]
      属性1: plan_id - 计划 UUID
      属性2: workspace_id - 工作空间 ID
      属性3: rollback_chain - 反向步骤列表（已排序）
      属性4: snapshot - 原始快照（用于 restore）
      属性5: trace_id - 关联追踪 ID
    [方法列表]
      方法1: reverse(steps) → list - 私有：反转步骤列表
    [来源标注] [DD-M推断:补偿计划数据载体]
    """

    plan_id: uuid.UUID
    workspace_id: uuid.UUID
    rollback_chain: list = field(default_factory=list)
    snapshot: object = None
    trace_id: Optional[uuid.UUID] = None


class Compensator:
    """
    [类名] Compensator
    [职责] 失败回滚执行器：构建计划 + 顺序执行 rollback
    [关联设计规范] MD-MCP-M-C09
    [属性]
      属性1: step_handlers - 步骤名 → rollback handler 映射
    [方法列表]
      方法1: build_plan(workspace_id, completed_steps, snapshot) → CompensationPlan
      方法2: execute(plan) → bool - 顺序执行；任一失败 WARN 但不中断
      方法3: _rollback_apply(plan) - 内部：撤销 apply（调用 M-C05 revoke）
      方法4: _rollback_snapshot(plan) - 内部：恢复 snapshot
    [异常处理]
      异常1: ApplyRevokeFailed - WARN + 记录；继续后续
      异常2: SnapshotRestoreFailed - ERROR + 人工介入告警
    [并发安全] 调用方保证 per-ws 串行
    [幂等性] 是；同 plan_id 重复执行结果一致
    [来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:handler 注册表避免硬编码 if/else]
    """

    def __init__(self) -> None:
        """
        [函数名] __init__
        [职责] 初始化补偿器（注册步骤 rollback handler）
        [参数说明] 无
        [返回值] None
        [前置条件] 无
        [后置条件] self.step_handlers 已填充
        [来源标注] [DD-M推断:handler 映射表]
        """
        ...

    def build_plan(
        self,
        workspace_id: uuid.UUID,
        completed_steps: list,
        snapshot: object,
        trace_id: Optional[uuid.UUID] = None,
    ) -> CompensationPlan:
        """
        [函数名] build_plan
        [职责] 构造补偿计划（反向步骤链）
        [参数说明]
          参数1: workspace_id UUID 必填
          参数2: completed_steps list 必填 已成功完成的步骤
          参数3: snapshot object 必填 原始快照
          参数4: trace_id UUID 可选
        [返回值] CompensationPlan
        [错误码] 无
        [前置条件] completed_steps 顺序正确
        [后置条件] rollback_chain 已逆序排列
        [来源标注] [DD-M推断:仅做顺序反转，DD-S 据此填充]
        """
        ...

    async def execute(self, plan: CompensationPlan) -> bool:
        """
        [函数名] execute
        [职责] 顺序执行补偿计划
        [参数说明]
          参数1: plan CompensationPlan 必填
        [返回值] bool 全成功 True；任一失败 False
        [错误码] 内部不抛异常；失败仅 WARN
        [前置条件] plan.rollback_chain 非空
        [后置条件] 审计日志已写
        [并发安全] 调用方负责
        [幂等性] 是
        [性能约束] P95 ≤ 10s
        [来源标注] [DD-M推断:失败容忍策略]
        """
        ...

    async def _rollback_apply(self, plan: CompensationPlan) -> None:
        """
        [函数名] _rollback_apply
        [职责] 内部：撤销 apply 步骤（调用 M-C05 revoke）
        [参数说明]
          参数1: plan CompensationPlan 必填
        [返回值] None
        [错误码] ApplyRevokeFailed - WARN 不抛
        [前置条件] plan.snapshot 含 applied_rule_ids
        [后置条件] M-C05 后端规则已撤销
        [来源标注] [DD-001:IC-012] + [DD-M推断:跨模块调用封装]
        """
        ...

    async def _rollback_snapshot(self, plan: CompensationPlan) -> None:
        """
        [函数名] _rollback_snapshot
        [职责] 内部：从 snapshot 恢复 ACL 状态
        [参数说明]
          参数1: plan CompensationPlan 必填
        [返回值] None
        [错误码] SnapshotRestoreFailed - ERROR
        [前置条件] plan.snapshot 非空
        [后置条件] ACL 后端已恢复至 snapshot 状态
        [来源标注] [DD-M推断:最终兜底]
        """
        ...
