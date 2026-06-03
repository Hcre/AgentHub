"""M-B03 Binding Engine 路由控制器.

[文件路径] src/agenthub/application/binding/controllers.py
[文件职责] 提供 Binding API 路由层，承接来自 M-A01 网关的绑定/解绑请求
[所属模块] M-B03
[关联设计规范] MD-MCP-V1.0-20260602#M-B03 / API-120 / IC-022（in-proc）
[功能描述]
  功能1: 暴露 POST /bindings（绑定 MCP 到 workspace）
  功能2: 暴露 DELETE /bindings/{binding_id}（解绑）
  功能3: 暴露 GET /bindings（列出 workspace 内所有 binding）
  功能4: 转换 HTTP 请求/响应为 Service 层 DTO
[输入输出]
  输入: HTTP Request（BindForm / Path / Query）
  输出: HTTP Response（BindingResult / list[BindingResult]） + 统一错误格式
[依赖关系]
  依赖文件: agenthub.application.binding.services、agenthub.application.binding.schemas、
            agenthub.application.binding.exceptions、agenthub.core.logging、agenthub.core.exceptions
  被依赖文件: agenthub.application.binding.__init__、agenthub.access.api_gateway（M-A01 挂载）
[注意事项]
  注意1: Controller 严格三层架构（controllers → services → strategies/generators），禁止直接调用 strategies/generators
  注意2: 错误码 BINDING_CONFLICT (409) / CONFIG_LOCK_TIMEOUT (503) 必须由 Service 层抛出
  注意3: 必须在每个 endpoint 注入 trace_id（来自 M-A01 TraceMiddleware）
  注意4: API 性能约束 P95 ≤ 500ms（含 fcntl 锁获取）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1（Python 风格）
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B03 - 初版控制器
[作者] DD-M-B03-20260603
[来源标注] [DD-001:FS-007 + MD-MCP-V1.0-20260602#M-B03 + API:API-120]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field

from agenthub.application.binding.exceptions import (
    BindingConflictError,
    ConfigLockTimeoutError,
)
from agenthub.application.binding.schemas import BindForm, BindingResult
from agenthub.application.binding.services import BindingService
from agenthub.core.logging import get_logger
from agenthub.core.tracing import get_trace_id

if TYPE_CHECKING:
    pass

log = get_logger(__name__)


class BindingListResponse(BaseModel):
    """绑定列表响应模型.

    [类名] BindingListResponse
    [职责] 包装绑定列表与分页元数据
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: items list[BindingResult] 绑定项列表
      属性2: total int 总数
    [来源标注] [DD-M推断:FS-007 未明确分页结构，基于 RESTful 最佳实践]
    """

    items: list[BindingResult] = Field(..., description="绑定项列表")
    total: int = Field(..., ge=0, description="总条数")


class BindingController:
    """Binding API 路由控制器（FastAPI router 持有者）.

    [类名] BindingController
    [职责] 提供绑定/解绑/列表 REST 入口
    [关联设计规范] MD-MCP-V1.0-20260602#M-B03
    [属性]
      属性1: router APIRouter FastAPI 路由实例
      属性2: service BindingService 业务服务（依赖注入）
    [方法列表]
      方法1: bind(form) -> BindingResult - 创建绑定
      方法2: unbind(binding_id) -> None - 删除绑定
      方法3: list_bindings(workspace_id, page, size) -> BindingListResponse - 列出 workspace 内绑定
    [异常处理]
      异常1: BindingConflictError - 409 BINDING_CONFLICT（mcp_id, ws_id 已绑定）
      异常2: ConfigLockTimeoutError - 503 CONFIG_LOCK_TIMEOUT（fcntl 锁竞争 + 重试 1 次仍失败）
    [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
    """

    def __init__(self, service: BindingService) -> None:
        """初始化 BindingController.

        [函数名] __init__
        [职责] 注入 BindingService 并构建 FastAPI 路由
        [参数说明]
          参数1: service BindingService 必填 业务服务 实例
        [来源标注] [DD-M推断:典型 DI 模式，基于 FS-007 三层架构]
        """
        self._service = service
        self.router = APIRouter(prefix="/bindings", tags=["binding"])
        self._register_routes()

    def _register_routes(self) -> None:
        """注册路由.

        [函数名] _register_routes
        [职责] 将 REST endpoint 绑定到 self.router
        [来源标注] [DD-M推断:FS-007 controller 内部约定]
        """
        # [DD-M推断:典型 FastAPI controller 路由注册模式]
        self.router.add_api_route(
            "",
            self.bind,
            methods=["POST"],
            response_model=BindingResult,
            status_code=status.HTTP_201_CREATED,
            summary="绑定 MCP 到 workspace",
        )
        self.router.add_api_route(
            "/{binding_id}",
            self.unbind,
            methods=["DELETE"],
            status_code=status.HTTP_204_NO_CONTENT,
            summary="解绑指定 binding",
        )
        self.router.add_api_route(
            "",
            self.list_bindings,
            methods=["GET"],
            response_model=BindingListResponse,
            summary="列出 workspace 内所有 binding",
        )

    async def bind(self, form: BindForm) -> BindingResult:
        """创建 binding（POST /bindings）.

        [函数名] bind
        [职责] 处理绑定请求，调用 Service 层编排
        [关联接口契约] API-120（来自 DD-001）
        [参数说明]
          参数1: form BindForm 必填 绑定表单（含 ws_id / mcp_id / 可选 mapping）
        [返回值]
          类型: BindingResult
          描述: 绑定结果（binding_id / state / config_path / pid）
          特殊值: 无
        [错误码]
          错误码1: BINDING_CONFLICT 409 - mcp_id, ws_id 已绑定
          错误码2: CONFIG_LOCK_TIMEOUT 503 - mcp-config 写锁竞争
          错误码3: POOL_FULL 429 - 来自 M-B02 spawn（429 透传）
        [前置条件] JWT 有效；ws_id 存在；mcp_id 已在市场发布
        [后置条件] mcp-config 文件已生成；process 已 spawn
        [并发安全] 由 Service 层 fcntl SHARED LOCK 保证
        [幂等性] 否（重复请求触发 BINDING_CONFLICT）
        [性能约束] P95 ≤ 500ms
        [来源标注] [DD-001:API-120 + MD-MCP-V1.0-20260602#M-B03]
        """
        # [DD-M推断:controller 仅做 DTO 转换 + 异常映射，不实现业务]
        trace_id = get_trace_id()
        log.info(
            "binding_create_requested",
            ws_id=str(form.workspace_id),
            mcp_id=str(form.mcp_id),
            trace_id=trace_id,
        )
        try:
            result = await self._service.bind(
                ws_id=form.workspace_id,
                mcp_id=form.mcp_id,
                mapping=form.mapping,
                trace_id=trace_id,
            )
        except BindingConflictError as e:
            log.warning(
                "binding_conflict",
                ws_id=str(form.workspace_id),
                mcp_id=str(form.mcp_id),
                err=str(e),
                trace_id=trace_id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "BINDING_CONFLICT",
                    "message": str(e),
                    "trace_id": trace_id,
                },
            ) from e
        except ConfigLockTimeoutError as e:
            log.error(
                "config_lock_timeout",
                ws_id=str(form.workspace_id),
                mcp_id=str(form.mcp_id),
                err=str(e),
                trace_id=trace_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CONFIG_LOCK_TIMEOUT",
                    "message": str(e),
                    "trace_id": trace_id,
                },
            ) from e
        return result

    async def unbind(self, binding_id: UUID = Path(..., description="绑定 ID")) -> None:
        """解绑指定 binding（DELETE /bindings/{binding_id}）.

        [函数名] unbind
        [职责] 处理解绑请求，释放 mcp_id 资源
        [关联接口契约] API-121（来自 DD-001 MD-MCP#M-B03）
        [参数说明]
          参数1: binding_id UUID 必填 绑定记录 ID
        [返回值]
          类型: None
          描述: 成功解绑后返回 204 No Content
          特殊值: 无
        [错误码]
          错误码1: BINDING_NOT_FOUND 404 - binding_id 不存在
          错误码2: CONFIG_LOCK_TIMEOUT 503 - mcp-config 写锁竞争
        [前置条件] JWT 有效；binding_id 存在
        [后置条件] mcp-config 文件被原子清理；process 被 recycle
        [并发安全] Service 层 fcntl EXCLUSIVE LOCK
        [幂等性] 否（重复 unbind 返回 404）
        [性能约束] P95 ≤ 300ms
        [来源标注] [DD-001:MD-MCP-V1.0-20260602#M-B03]
        """
        trace_id = get_trace_id()
        log.info("binding_unbind_requested", binding_id=str(binding_id), trace_id=trace_id)
        # [DD-M推断:解绑由 Service 编排，包含：unlink file + M-B02 recycle + 状态置 Released]
        try:
            await self._service.unbind(binding_id=binding_id, trace_id=trace_id)
        except BindingConflictError as e:
            # [DD-M推断:解绑时若 binding 不存在，统一抛 BindingConflictError 由 controller 转 404]
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "code": "BINDING_NOT_FOUND",
                    "message": f"binding {binding_id} not found",
                    "trace_id": trace_id,
                },
            ) from e
        except ConfigLockTimeoutError as e:
            log.error(
                "config_lock_timeout_unbind",
                binding_id=str(binding_id),
                err=str(e),
                trace_id=trace_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "CONFIG_LOCK_TIMEOUT",
                    "message": str(e),
                    "trace_id": trace_id,
                },
            ) from e

    async def list_bindings(
        self,
        workspace_id: UUID = Query(..., description="workspace ID"),
        page: int = Query(1, ge=1, description="页码"),
        size: int = Query(20, ge=1, le=100, description="每页大小"),
    ) -> BindingListResponse:
        """列出 workspace 内所有 binding（GET /bindings）.

        [函数名] list_bindings
        [职责] 分页查询 workspace 内 binding 列表
        [关联接口契约] API-122（来自 DD-001 MD-MCP#M-B03）
        [参数说明]
          参数1: workspace_id UUID 必填 工作区 ID
          参数2: page int 可选 默认 1 页码
          参数3: size int 可选 默认 20 每页大小 上限 100
        [返回值]
          类型: BindingListResponse
          描述: 绑定列表 + 总数
          特殊值: 空列表时 total=0
        [错误码]
          错误码1: WORKSPACE_NOT_FOUND 404 - workspace_id 不存在
        [前置条件] JWT 有效；ws_id 存在
        [后置条件] 不变
        [并发安全] PG SELECT（无锁）
        [幂等性] 是
        [性能约束] P95 ≤ 200ms
        [来源标注] [DD-M推断:FS-007 未列 list endpoint，基于 market 模块惯例补充]
        """
        trace_id = get_trace_id()
        log.info(
            "binding_list_requested",
            ws_id=str(workspace_id),
            page=page,
            size=size,
            trace_id=trace_id,
        )
        # [DD-M推断:list 查询由 Service 内部委托给 binding repository]
        items, total = await self._service.list_bindings(
            ws_id=workspace_id, page=page, size=size, trace_id=trace_id
        )
        return BindingListResponse(items=items, total=total)


def build_controller(service: BindingService) -> BindingController:
    """工厂函数：构建 BindingController.

    [函数名] build_controller
    [职责] 供 M-A01 API Gateway 启动时调用，注册 binding 路由
    [参数说明]
      参数1: service BindingService 必填 业务服务实例
    [返回值]
      类型: BindingController
      描述: 控制器实例
    [来源标注] [DD-M推断:典型 FastAPI DI 工厂模式]
    """
    return BindingController(service)


# [DD-M推断:对外暴露的依赖注入入口，供 M-A01 启动时 wire]
__all__ = ["BindingController", "BindingListResponse", "build_controller"]


# [依赖占位] 实际实现由 DD-S（结构设计师）填充
_ = Depends  # noqa: F841 (预留 FastAPI Depends 入口)
