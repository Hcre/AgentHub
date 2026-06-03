"""
[文件路径] src/agenthub/application/create/compensator.py
[文件职责] M-B05 Saga 反向补偿器（仅 secret/metadata/history 失败时触发）
[所属模块] M-B05
[关联设计规范] MD-MCP-V1.0-20260602 #M-B05 + DDR-MCP-V1.0-20260602 #DDR-005
[功能描述]
  功能1: compensate_secret() 撤销 ctx.vault_refs
  功能2: compensate_metadata() 撤销 DS-012 记录 + 触发 compensate_secret
  功能3: publish_rollback_done() 发 mcp.rollback_done 事件（Stream，[DDR-002]）
[输入输出]
  输入: ctx: SagaContext + failed_step: str
  输出: 无（副作用：删除/撤销 + 事件发布）
[依赖关系]
  依赖文件: agenthub.infrastructure.secret.vault_client / agenthub.data.metadata
  被依赖文件: agenthub.application.create.orchestrator
[注意事项]
  注意1: K4 失败不调用本补偿器（直接 rejected，[DDR-005]）
  注意2: history 失败不调用本补偿器（业务已 done，[MD-MCP/M-B05]）
  注意3: 补偿动作必须幂等（重试场景下不可重复扣减）
  注意4: mcp.rollback_done 走 Stream 模式（关键 topic，[DDR-002]）
[代码风格] 遵循CS-MCP-V1.0-20260602
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B05 - 初始创建文件框架
[作者] DD-M-B05-20260603
[来源标注] [DD-001:MD-MCP/M-B05 + DDR-005 + DDR-002]
"""
from __future__ import annotations

# 注释占位：导入
# from agenthub.core.logging import get_logger
# from agenthub.application.create.schemas import SagaContext
# from agenthub.infrastructure.secret.vault_client import VaultClient
# from agenthub.data.metadata.unit_of_work import UnitOfWork
# from agenthub.data.metadata.repositories.mcp_submission_repo import MCPSubmissionRepository
# from agenthub.eventbus.bus import EventBus
#
# log = get_logger(__name__)


class Compensator:
    """[类名] Compensator
    [职责] M-B05 Saga 反向补偿器
    [关联设计规范] MD-MCP-V1.0-20260602 #M-B05
    [属性]
      属性1: vault_client VaultClient M-C07 Vault 客户端
      属性2: uow_factory Callable[[], UnitOfWork] UoW 工厂
      属性3: eventbus EventBus 事件总线
    [方法列表]
      方法1: compensate_secret(ctx) -> None - 撤销 Vault 写入
      方法2: compensate_metadata(ctx) -> None - 撤销元数据 + 触发 secret 补偿
      方法3: publish_rollback_done(ctx, failed_step) -> None - 发 mcp.rollback_done
      方法4: run(trace_id, failed_step) -> None - 入口（依据 failed_step 选择补偿链）
    [异常处理]
      异常1: 补偿失败应记录 ERROR 并继续其他补偿动作（best-effort）
    [来源标注] [DD-001:MD-MCP/M-B05 + DDR-005 + DDR-002]
    """
    # 注释占位：实现
    # COMPENSATION_CHAIN = {
    #     "metadata": ["metadata", "secret"],
    #     "secret": ["secret"],
    #     # history 不补偿
    # }
    #
    # def __init__(
    #     self,
    #     vault_client: VaultClient,
    #     uow_factory: Callable[[], UnitOfWork],
    #     eventbus: EventBus,
    # ) -> None:
    #     self.vault_client = vault_client
    #     self.uow_factory = uow_factory
    #     self.eventbus = eventbus
    #
    # async def run(self, trace_id: UUID, failed_step: str) -> None:
    #     ...
    #
    # async def compensate_secret(self, ctx: SagaContext) -> None:
    #     ...
    #
    # async def compensate_metadata(self, ctx: SagaContext) -> None:
    #     ...
    #
    # async def publish_rollback_done(self, ctx: SagaContext, failed_step: str) -> None:
    #     ...
    pass
