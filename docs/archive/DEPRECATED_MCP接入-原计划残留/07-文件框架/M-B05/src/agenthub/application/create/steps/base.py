"""
[文件路径] src/agenthub/application/create/steps/base.py
[文件职责] M-B05 Saga Step 抽象基类
[所属模块] M-B05
[关联设计规范] MD-MCP-V1.0-20260602 #M-B05 + FS-MCP-V1.0-20260602 #FS-009
[功能描述]
  功能1: 定义 SagaStep 抽象基类（forward/compensate 模板方法）
  功能2: 定义步骤执行上下文协议（与 schemas.SagaContext 协作）
[输入输出]
  输入: ctx: SagaContext
  输出: StepResult（done/failed）
[依赖关系]
  依赖文件: agenthub.application.create.schemas
  被依赖文件: agenthub.application.create.steps.dry_run / k4 / secret / metadata / history
[注意事项]
  注意1: forward() 必须返回 StepResult，异常通过 result.err 表达而非直接 raise
  注意2: compensate() 仅在 K4/dry_run 之外的步骤中实现
  注意3: 子类构造不应包含 IO，仅持有依赖引用
[代码风格] 遵循CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B05 - 初始创建文件框架
[作者] DD-M-B05-20260603
[来源标注] [DD-001:MD-MCP/M-B05 + IC-MCP/IC-007]
"""
from __future__ import annotations

# 注释占位：标准库 → 第三方 → 本地
# from abc import ABC, abstractmethod
# from agenthub.core.logging import get_logger
# from agenthub.application.create.schemas import SagaContext, StepResult
#
# log = get_logger(__name__)


class SagaStep(ABC):
    """[类名] SagaStep
    [职责] Saga 步骤抽象基类
    [关联设计规范] MD-MCP-V1.0-20260602 #M-B05
    [属性]
      属性1: name str 步骤标识（与 SagaStep 枚举一致）
    [方法列表]
      方法1: forward(ctx: SagaContext) -> StepResult - 前向执行
      方法2: compensate(ctx: SagaContext) -> None - 反向补偿（默认 no-op）
    [异常处理]
      异常1: 业务异常应包装为 StepResult(status="failed", err=...) 返回，不直接 raise
    [来源标注] [DD-001:MD-MCP/M-B05]
    """
    # 注释占位：基类实现
    # name: str = ""
    #
    # @abstractmethod
    # async def forward(self, ctx: SagaContext) -> StepResult:
    #     ...
    #
    # async def compensate(self, ctx: SagaContext) -> None:
    #     """默认 no-op；K4/DryRun 无需补偿."""
    #     log.info("step_compensate_noop", step=self.name, trace_id=str(ctx.trace_id))
    pass
