"""
[文件路径] src/agenthub/infrastructure/acl_migration/steps/base.py
[文件职责] M-C09 MigrationStep 抽象基类
[所属模块] M-C09（来自 DD-001）
[关联设计规范] FS-018 / MD-MCP-M-C09（来自 DD-001）
[功能描述]
  功能1: 定义 Saga 步骤的统一接口 forward/compensate
  功能2: 提供步骤名称、状态字段、ctx 读写辅助
[输入输出]
  输入: ctx dict（步骤间共享上下文）
  输出: ctx（更新后）
[依赖关系]
  依赖文件: 无（仅基础类型）
  被依赖文件: .snapshot, .apply, .verify, .commit
[注意事项]
  注意1: 子类必须实现 forward 和 compensate；否则 raise NotImplementedError
  注意2: step_name 在 4 步中必须唯一
[代码风格] 遵循 CS-MCP Python
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-C09 - 初始版本
[作者] DD-M-C09-20260602
[来源标注] [DD-M推断:Step 接口标准化]
"""
from __future__ import annotations

import abc
from typing import Any


class MigrationStep(abc.ABC):
    """
    [类名] MigrationStep
    [职责] Saga 步骤抽象基类
    [关联设计规范] MD-MCP-M-C09
    [属性]
      属性1: step_name str 步骤名（snapshot/apply/verify/commit）
      属性2: order int 步骤序号（0/1/2/3）
    [方法列表]
      方法1: forward(ctx) → dict 抽象 前向执行
      方法2: compensate(ctx) → None 抽象 反向回滚
    [状态机] 无
    [异常处理]
      异常1: MigrationStepError - 步骤执行异常
    [来源标注] [DD-001:MD-MCP-M-C09] + [DD-M推断:abc.ABC 强制子类实现]
    """

    step_name: str = ""
    order: int = -1

    @abc.abstractmethod
    async def forward(self, ctx: dict) -> dict:
        """
        [函数名] forward
        [职责] 前向执行步骤
        [参数说明]
          参数1: ctx dict 必填 执行上下文
        [返回值] dict 更新后的 ctx
        [错误码] MigrationStepError - 步骤执行失败
        [前置条件] ctx 含 ws_id/trace_id
        [后置条件] ctx 新增该步结果字段
        [来源标注] [DD-001:MD-MCP-M-C09]
        """
        ...

    @abc.abstractmethod
    async def compensate(self, ctx: dict) -> None:
        """
        [函数名] compensate
        [职责] 反向回滚步骤
        [参数说明]
          参数1: ctx dict 必填 执行上下文
        [返回值] None
        [错误码] MigrationStepError - 回滚失败
        [前置条件] 步骤已 forward 成功
        [后置条件] 步骤产生的副作用已撤销
        [来源标注] [DD-001:MD-MCP-M-C09]
        """
        ...
