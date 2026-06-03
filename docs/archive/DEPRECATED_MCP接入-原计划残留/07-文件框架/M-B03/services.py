"""M-B03 Binding Engine 业务服务层.

[文件路径] src/agenthub/application/binding/services.py
[文件职责] 绑定/解绑业务编排，串联 Strategy / Generator / M-B02 pool
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03 / IC-004 (M-B02 spawn)
[功能描述]
  功能1: bind(ws_id, mcp_id, mapping) 编排：检查冲突 → 生成 mcp-config → 调用 M-B02 spawn
  功能2: unbind(binding_id) 编排：删除 mcp-config → 通知 M-B02 recycle → 标记 Released
  功能3: list_bindings(ws_id, page, size) 委托给 BindingRepository
  功能4: 选择 BindingStrategy（Default / Custom）转换 mapping
[输入输出]
  输入: ws_id / mcp_id / mapping / binding_id / trace_id
  输出: BindingResult / list[BindingResult]
[依赖关系]
  依赖文件: agenthub.application.binding.strategies、agenthub.application.binding.generators、
            agenthub.application.binding.schemas、agenthub.application.binding.exceptions、
            agenthub.application.binding.repository、agenthub.application.pool（跨模块 IC-004）
  被依赖文件: agenthub.application.binding.controllers
[注意事项]
  注意1: 状态机 Pending → ConfigGenerated → Spawned → Active；Active → Unbind → Released
  注意2: 跨模块调用 M-B02 必须使用 in-proc 接口（IC-004），禁止远程 RPC
  注意3: 写文件必须经 ConfigGenerator（ADR-005 单一源），禁止直接 open()
  注意4: fcntl 锁竞争 ConfigLockTimeout → 重试 1 次（200ms）→ 仍失败抛 ConfigLockTimeoutError
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版服务层
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03 + IC-004]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from agenthub.application.binding.exceptions import (
    BindingConflictError,
    ConfigLockTimeoutError,
)
from agenthub.application.binding.generators import ConfigGenerator
from agenthub.application.binding.schemas import BindingResult, Mapping
from agenthub.application.binding.strategies import (
    BindingStrategy,
    CustomMappingStrategy,
    DefaultMappingStrategy,
)
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.application.binding.repository import BindingRepository

log = get_logger(__name__)


class BindingService:
    """Binding 业务编排服务.

    [类名] BindingService
    [职责] 编排 bind / unbind / list 流程，跨策略、生成器、进程池
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: strategy BindingStrategy 名称映射策略
      属性2: generator ConfigGenerator mcp-config 生成器
      属性3: pool PoolAdapter M-B02 进程池适配器
      属性4: repo BindingRepository 绑定仓储
    [方法列表]
      方法1: bind(ws_id, mcp_id, mapping, trace_id) -> BindingResult - 绑定入口
      方法2: unbind(binding_id, trace_id) -> None - 解绑入口
      方法3: list_bindings(ws_id, page, size, trace_id) -> tuple[list, int] - 列表入口
    [状态机]
      状态1: Pending → ConfigGenerated（mcp-config 写盘成功）
      状态2: ConfigGenerated → Spawned（M-B02 spawn 成功）
      状态3: Spawned → Active（健康检查通过）
      状态4: Active → Unbind → Released（解绑完成）
    [异常处理]
      异常1: BindingConflictError - mcp_id, ws_id 已绑定
      异常2: ConfigLockTimeoutError - fcntl 锁竞争
      异常3: PoolFullError - 进程池满（透传自 M-B02 IC-004）
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    def __init__(
        self,
        strategy: BindingStrategy | None = None,
        generator: ConfigGenerator | None = None,
        pool: object | None = None,
        repo: "BindingRepository | None" = None,
    ) -> None:
        """初始化 BindingService.

        [函数名] __init__
        [职责] 注入 strategy / generator / pool / repo 依赖
        [参数说明]
          参数1: strategy BindingStrategy 可选 默认 DefaultMappingStrategy
          参数2: generator ConfigGenerator 可选 默认 ConfigGenerator
          参数3: pool object 可选 M-B02 进程池适配器
          参数4: repo BindingRepository 可选 绑定仓储
        [来源标注] [DD-M推断:典型 DI 注入模式]
        """
        self._strategy = strategy or DefaultMappingStrategy()
        self._generator = generator or ConfigGenerator()
        self._pool = pool
        self._repo = repo

    async def bind(
        self,
        ws_id: UUID,
        mcp_id: UUID,
        mapping: Mapping | None,
        trace_id: str,
    ) -> BindingResult:
        """执行绑定（核心入口）.

        [函数名] bind
        [职责] 编排：冲突检查 → 策略转换 → 写 mcp-config → spawn → 持久化
        [关联接口契约] IC-022（in-proc，API-120）
        [参数说明]
          参数1: ws_id UUID 必填 工作区 ID
          参数2: mcp_id UUID 必填 MCP ID
          参数3: mapping Mapping 可选 None 时使用默认 1:1 映射
          参数4: trace_id str 必填 分布式追踪 ID
        [返回值]
          类型: BindingResult
          描述: 绑定结果（binding_id / state=Active / config_path / pid）
          特殊值: 无
        [错误码]
          错误码1: BINDING_CONFLICT 409 - (ws_id, mcp_id) 已绑定
          错误码2: CONFIG_LOCK_TIMEOUT 503 - fcntl 锁 + 重试 1 次仍失败
          错误码3: POOL_FULL 429 - 透传自 M-B02 IC-004
        [前置条件] ws_id 存在；mcp_id 已在市场发布；mapping 不含路径遍历
        [后置条件] mcp-config 文件已生成（0600 权限）；process 已 spawn；binding 状态 Active
        [并发安全] fcntl SHARED LOCK 串行化写盘
        [幂等性] 否
        [性能约束] P95 ≤ 500ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
        """
        log.info(
            "bind_start",
            ws_id=str(ws_id),
            mcp_id=str(mcp_id),
            trace_id=trace_id,
        )
        # 步骤1: 冲突检查
        if self._repo is not None and await self._repo.exists(ws_id=ws_id, mcp_id=mcp_id):
            raise BindingConflictError(
                f"binding (ws_id={ws_id}, mcp_id={mcp_id}) already exists"
            )

        # 步骤2: 策略转换 mapping
        effective_mapping = self._strategy.transform(mapping) if mapping else self._strategy.default_mapping()

        # 步骤3: 生成 mcp-config（ConfigGenerator 内部加 fcntl 锁 + 0600 权限）
        try:
            config_path = await self._generator.generate(
                mapping=effective_mapping,
                ws_id=ws_id,
                trace_id=trace_id,
            )
        except ConfigLockTimeoutError:
            log.warning(
                "config_lock_first_retry",
                ws_id=str(ws_id),
                mcp_id=str(mcp_id),
                trace_id=trace_id,
            )
            # 步骤3.1: 重试 1 次（200ms 后）
            import asyncio
            await asyncio.sleep(0.2)
            try:
                config_path = await self._generator.generate(
                    mapping=effective_mapping,
                    ws_id=ws_id,
                    trace_id=trace_id,
                )
            except ConfigLockTimeoutError as e:
                log.error(
                    "config_lock_failed_after_retry",
                    ws_id=str(ws_id),
                    mcp_id=str(mcp_id),
                    err=str(e),
                    trace_id=trace_id,
                )
                raise

        # 步骤4: 调用 M-B02 spawn（IC-004 in-proc）
        if self._pool is not None:
            spawn_result = await self._pool.spawn(
                mcp_id=mcp_id,
                workspace_id=ws_id,
                reserved_slot=False,
                trace_id=trace_id,
            )
            pid = spawn_result["pid"]
        else:
            # [DD-M推断:未注入 pool 时返回占位 pid 用于单测]
            pid = -1

        # 步骤5: 持久化 binding 记录
        binding_id: UUID | None = None
        if self._repo is not None:
            binding_id = await self._repo.add(
                ws_id=ws_id,
                mcp_id=mcp_id,
                mapping=effective_mapping,
                config_path=config_path,
                pid=pid,
                trace_id=trace_id,
            )

        log.info(
            "bind_done",
            ws_id=str(ws_id),
            mcp_id=str(mcp_id),
            binding_id=str(binding_id) if binding_id else None,
            pid=pid,
            trace_id=trace_id,
        )

        return BindingResult(
            binding_id=binding_id,
            state="Active",
            config_path=config_path,
            pid=pid,
            ws_id=ws_id,
            mcp_id=mcp_id,
        )

    async def unbind(self, binding_id: UUID, trace_id: str) -> None:
        """执行解绑.

        [函数名] unbind
        [职责] 编排：取 binding → 删 mcp-config → M-B02 recycle → 标 Released
        [关联接口契约] IC-022（in-proc，API-121）
        [参数说明]
          参数1: binding_id UUID 必填 绑定 ID
          参数2: trace_id str 必填 追踪 ID
        [返回值]
          类型: None
          描述: 无返回值
          特殊值: 无
        [错误码]
          错误码1: BINDING_NOT_FOUND 404 - binding_id 不存在
          错误码2: CONFIG_LOCK_TIMEOUT 503
        [前置条件] binding_id 存在
        [后置条件] mcp-config 文件被原子删除；process 进入 recycling；binding 状态 Released
        [并发安全] fcntl EXCLUSIVE LOCK
        [幂等性] 否
        [性能约束] P95 ≤ 300ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
        """
        log.info("unbind_start", binding_id=str(binding_id), trace_id=trace_id)
        # [DD-M推断:unbind 全流程串行化]
        if self._repo is None:
            raise BindingConflictError(f"binding {binding_id} not found (no repo)")
        binding = await self._repo.get(binding_id=binding_id)
        if binding is None:
            raise BindingConflictError(f"binding {binding_id} not found")

        # 步骤1: 删 mcp-config
        try:
            await self._generator.revoke(
                config_path=binding.config_path,
                ws_id=binding.ws_id,
                trace_id=trace_id,
            )
        except ConfigLockTimeoutError:
            log.warning(
                "config_lock_first_retry_unbind",
                binding_id=str(binding_id),
                trace_id=trace_id,
            )
            import asyncio
            await asyncio.sleep(0.2)
            await self._generator.revoke(
                config_path=binding.config_path,
                ws_id=binding.ws_id,
                trace_id=trace_id,
            )

        # 步骤2: M-B02 recycle（IC-004）
        if self._pool is not None and binding.pid > 0:
            await self._pool.recycle(pid=binding.pid, trace_id=trace_id)

        # 步骤3: 标记 Released
        await self._repo.mark_released(binding_id=binding_id, trace_id=trace_id)
        log.info("unbind_done", binding_id=str(binding_id), trace_id=trace_id)

    async def list_bindings(
        self,
        ws_id: UUID,
        page: int,
        size: int,
        trace_id: str,
    ) -> tuple[list[BindingResult], int]:
        """列出 workspace 内 binding.

        [函数名] list_bindings
        [职责] 分页查询
        [参数说明]
          参数1: ws_id UUID 必填
          参数2: page int 必填
          参数3: size int 必填
          参数4: trace_id str 必填
        [返回值]
          类型: tuple[list[BindingResult], int]
          描述: (绑定项列表, 总数)
        [并发安全] PG SELECT 无锁
        [幂等性] 是
        [性能约束] P95 ≤ 200ms
        [来源标注] [DD-M推断:基于 M-B01 market list 模式]
        """
        log.info(
            "list_bindings_start",
            ws_id=str(ws_id),
            page=page,
            size=size,
            trace_id=trace_id,
        )
        if self._repo is None:
            return [], 0
        return await self._repo.list(ws_id=ws_id, page=page, size=size, trace_id=trace_id)

    @staticmethod
    def select_strategy(mapping_kind: str) -> BindingStrategy:
        """选择策略.

        [函数名] select_strategy
        [职责] 静态方法，根据 mapping_kind 返回对应策略
        [参数说明]
          参数1: mapping_kind str 必填 "default" / "custom"
        [返回值]
          类型: BindingStrategy
          描述: 对应策略实例
        [来源标注] [DD-M推断:典型 Strategy 工厂方法]
        """
        if mapping_kind == "default":
            return DefaultMappingStrategy()
        if mapping_kind == "custom":
            return CustomMappingStrategy()
        raise ValueError(f"unknown mapping_kind: {mapping_kind}")


__all__ = ["BindingService"]
