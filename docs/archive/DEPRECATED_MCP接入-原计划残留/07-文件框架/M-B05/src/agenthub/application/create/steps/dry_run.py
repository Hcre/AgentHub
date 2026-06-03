"""
[文件路径] src/agenthub/application/create/steps/dry_run.py
[文件职责] M-B05 Saga 第 1 步：沙箱预演（调用 M-C01 Sandbox.run）
[所属模块] M-B05
[关联设计规范] MD-MCP-V1.0-20260602 #M-B05 + IC-MCP-V1.0-20260602 #IC-008
[功能描述]
  功能1: 在 M-C01 沙箱中执行 MCP manifest 的预演命令（list 形式，[TD:S-026]）
  功能2: 验证 manifest 可执行性、依赖可达性
  功能3: 失败标 rejected（无补偿，[DDR-005]）
[输入输出]
  输入: ctx.manifest 含 pre_run 字段
  输出: StepResult(status=done|failed, payload={stdout, stderr, exit_code})
[依赖关系]
  依赖文件: agenthub.application.create.steps.base / agenthub.infrastructure.sandbox.runner
  被依赖文件: agenthub.application.create.orchestrator
[注意事项]
  注意1: pre_run 命令必须为 list[str]，禁止 str 拼接（[TD:S-026]）
  注意2: 沙箱超时 30s 标 failed；OOM 标 failed
  注意3: dry_run 失败直接标 rejected，不进入补偿链（与 K4 同，[DDR-005]）
[代码风格] 遵循CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B05 - 初始创建文件框架
[作者] DD-M-B05-20260603
[来源标注] [DD-001:MD-MCP/M-B05 + IC-MCP/IC-008 + DDR-005]
"""
from __future__ import annotations

# 注释占位：导入
# from agenthub.core.logging import get_logger
# from agenthub.application.create.steps.base import SagaStep
# from agenthub.application.create.schemas import SagaContext, StepResult
# from agenthub.infrastructure.sandbox.runner import SandboxRunner
#
# log = get_logger(__name__)


class DryRunStep(SagaStep):
    """[类名] DryRunStep
    [职责] M-B05 Saga 第 1 步：沙箱预演
    [关联设计规范] MD-MCP-V1.0-20260602 #M-B05
    [属性]
      属性1: name str = "dry_run"
      属性2: sandbox_runner SandboxRunner M-C01 沙箱执行器
    [方法列表]
      方法1: forward(ctx) -> StepResult - 预演执行
    [异常处理]
      异常1: DryRunFailed → 标 rejected + 用户提示（无补偿）
    [来源标注] [DD-001:MD-MCP/M-B05 + IC-MCP/IC-008 + DDR-005]
    """
    # 注释占位：name 属性
    # name = "dry_run"
    #
    # def __init__(self, sandbox_runner: SandboxRunner) -> None:
    #     self.sandbox_runner = sandbox_runner
    #
    # async def forward(self, ctx: SagaContext) -> StepResult:
    #     ...
    pass
