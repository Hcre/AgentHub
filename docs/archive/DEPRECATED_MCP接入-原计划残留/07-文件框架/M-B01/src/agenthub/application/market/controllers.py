"""Market Controller 路由层.

[文件路径] src/agenthub/application/market/controllers.py
[文件职责] FastAPI Router；接收 /market/list、/market/{id}、/market/search 请求
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005 / IC-MCP-V1.0-20260602（API-100）
[功能描述]
  功能1: 挂载 list/detail/search 三个路由，全部 POST/GET 仅 1 个写操作
  功能2: 请求/响应 Pydantic 校验（ListFilter/Page/MCPServerDTO/MCPServerDetail）
  功能3: 将领域异常 NotFoundError → HTTP 404，DBError → HTTP 503
[输入输出]
  输入: HTTP 请求（含 trace_id、Authorization、查询参数/路径参数）
  输出: JSON {code, message, trace_id, data, timestamp}（与 IC-001 统一封装层）
[依赖关系]
  依赖文件: agenthub.application.market.services.MarketService / schemas / core.exceptions
  被依赖文件: agenthub.access.api_gateway（M-A01 在 include_router 时挂载）
[注意事项]
  注意1: 控制器不持有任何状态；MarketService 通过 Depends 注入（便于测试 Mock）
  注意2: list 接口在 v1 仅做只读列表，绑定/创建等写操作由 M-B03/M-B05 负责
  注意3: 错误码统一遵循 [DD-001:IC-001] 协议 {code, message, trace_id, data, timestamp}
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.3 类型注解 / §1.4 Google 风格 docstring
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版路由定义
[作者] DD-M-B01-20260602
[来源标注] [DD-001:FS-005/MD-MCP#M-B01/IC-MCP#API-100]
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from agenthub.application.market.schemas import (
    ListFilter,
    MCPServerDetail,
    MCPServerDTO,
    Page,
)
from agenthub.application.market.services import MarketService
from agenthub.core.exceptions import AgentHubError, DBError, NotFoundError

router = APIRouter(prefix="/market", tags=["market"])


class MarketController:
    """Market 域 HTTP 路由容器.

    [类名] MarketController
    [职责] 暴露 MCP Server 市场的查询类 API
    [关联设计规范] MD-MCP-V1.0-20260602#M-B01
    [属性]
      属性1: router APIRouter FastAPI 路由实例（module-level）
      属性2: _service_factory callable 注入 MarketService 的工厂
    [方法列表]
      方法1: list(filter) -> Page[MCPServerDTO] - 分页列出 MCP Server
      方法2: detail(server_id) -> MCPServerDetail - 查询单个详情
      方法3: search(q, filter) -> Page[MCPServerDTO] - 关键词 + 标签搜索
    [异常处理]
      异常1: NotFoundError - server_id 不存在 → 404 + MARKET_NOT_FOUND
      异常2: DBError - 数据库不可用 → 503 + MARKET_DB_UNAVAILABLE
    [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
    """

    def __init__(self, service_factory: "Callable[[], MarketService]") -> None:
        """构造 MarketController.

        [函数名] __init__
        [职责] 注入服务工厂，便于测试替换
        [参数说明]
          参数1: service_factory Callable 必填 工厂函数 返回 MarketService
        [返回值] None
        [来源标注] [DD-M推断:依赖注入模式避免硬编码，便于单测]
        """
        self._service_factory = service_factory

    async def list(
        self,
        filter_payload: ListFilter,
    ) -> Page[MCPServerDTO]:
        """POST /market/list 分页列出 MCP Server.

        [函数名] list
        [职责] 根据标签/创建时间/分页参数返回 MCP Server 列表
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: filter_payload ListFilter 必填 标签/分页/排序条件
        [返回值]
          类型: Page[MCPServerDTO]
          描述: 分页结果（items + total + page + size）
        [错误码]
          错误码1: MARKET_DB_UNAVAILABLE 503 DB 故障
          错误码2: MARKET_VALIDATION 400 入参 schema 失败
        [前置条件] 客户端已通过 JWT 鉴权
        [后置条件] 返回只读视图，不修改任何状态
        [并发安全] 只读查询，无锁
        [幂等性] 是；GET/POST+相同filter 返回相同结果
        [性能约束] P95 ≤ 300ms（含 Redis 缓存命中路径）
        [来源标注] [DD-001:IC-MCP#API-100/MD-MCP#M-B01]
        """
        # 仅注释，业务代码由开发工程师实现
        ...

    async def detail(
        self,
        server_id: Annotated[UUID, Path(description="MCP Server UUID")],
    ) -> MCPServerDetail:
        """GET /market/{id} 获取单个 MCP Server 详情.

        [函数名] detail
        [职责] 根据 UUID 返回 MCP Server 完整详情（含 manifest、tag、author 等）
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: server_id UUID 必填 路径参数
        [返回值]
          类型: MCPServerDetail
          描述: 完整 DTO（无列表字段）
        [错误码]
          错误码1: MARKET_NOT_FOUND 404 UUID 不存在
          错误码2: MARKET_DB_UNAVAILABLE 503
        [前置条件] 鉴权通过
        [后置条件] 缓存代理（decorators.CachedMCPServerRepository）写入 Redis 30min
        [并发安全] 只读
        [幂等性] 是
        [性能约束] P95 ≤ 200ms（缓存命中 < 50ms）
        [来源标注] [DD-001:IC-MCP#API-100/MD-MCP#M-B01]
        """
        ...

    async def search(
        self,
        q: Annotated[str, Query(min_length=1, max_length=128, description="搜索关键词")],
        tag: Annotated[list[str] | None, Query(description="标签过滤")] = None,
        page: Annotated[int, Query(ge=1, le=1000)] = 1,
        size: Annotated[int, Query(ge=1, le=100)] = 20,
    ) -> Page[MCPServerDTO]:
        """GET /market/search 关键词 + 标签搜索.

        [函数名] search
        [职责] 在 name/description 上做 ILIKE 模糊匹配 + 标签过滤
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: q str 必填 1-128 字符
          参数2: tag list[str] 可选 多选标签
          参数3: page int 可选 默认 1
          参数4: size int 可选 默认 20
        [返回值]
          类型: Page[MCPServerDTO]
          描述: 搜索结果分页
        [错误码]
          错误码1: MARKET_VALIDATION 400 q 为空或越界
        [并发安全] 只读
        [幂等性] 是
        [性能约束] P95 ≤ 500ms
        [来源标注] [DD-001:IC-MCP#API-100/MD-MCP#M-B01]
        """
        ...


# 路由端到函数映射（FastAPI handler 适配）
@router.post(
    "/list",
    response_model=Page[MCPServerDTO],
    status_code=status.HTTP_200_OK,
    summary="列出 MCP Server",
)
async def _list_endpoint(
    filter_payload: ListFilter,
    service: Annotated[MarketService, Depends(_service_dependency_stub)],
) -> Page[MCPServerDTO]:
    """路由层 list 适配器.

    [函数名] _list_endpoint
    [职责] HTTP 层 → MarketService.list_servers 适配
    [来源标注] [DD-M推断:HTTP 边界要求 - 控制器与 FastAPI router 解耦]
    """
    try:
        return await service.list_servers(filter_payload)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "MARKET_NOT_FOUND", "message": str(e)})
    except DBError as e:
        raise HTTPException(status_code=503, detail={"code": "MARKET_DB_UNAVAILABLE", "message": str(e)})
    except AgentHubError as e:
        raise HTTPException(status_code=500, detail={"code": "MARKET_INTERNAL", "message": str(e)})


@router.get(
    "/{server_id}",
    response_model=MCPServerDetail,
    status_code=status.HTTP_200_OK,
    summary="MCP Server 详情",
)
async def _detail_endpoint(
    server_id: Annotated[UUID, Path()],
    service: Annotated[MarketService, Depends(_service_dependency_stub)],
) -> MCPServerDetail:
    """路由层 detail 适配器.

    [函数名] _detail_endpoint
    [职责] HTTP 层 → MarketService.get_detail 适配
    [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
    """
    try:
        return await service.get_detail(server_id)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail={"code": "MARKET_NOT_FOUND", "message": str(e)})
    except DBError as e:
        raise HTTPException(status_code=503, detail={"code": "MARKET_DB_UNAVAILABLE", "message": str(e)})


@router.get(
    "/search",
    response_model=Page[MCPServerDTO],
    status_code=status.HTTP_200_OK,
    summary="MCP Server 搜索",
)
async def _search_endpoint(
    q: Annotated[str, Query(min_length=1, max_length=128)],
    tag: Annotated[list[str] | None, Query()] = None,
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
    service: Annotated[MarketService, Depends(_service_dependency_stub)] = ...,  # type: ignore[assignment]
) -> Page[MCPServerDTO]:
    """路由层 search 适配器.

    [函数名] _search_endpoint
    [职责] HTTP 层 → MarketService.search 适配
    [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
    """
    return await service.search(q=q, tags=tag or [], page=page, size=size)


# 依赖注入桩（占位符，由应用工厂在启动时替换为真实工厂）
async def _service_dependency_stub() -> MarketService:
    """FastAPI Depends 桩函数.

    [函数名] _service_dependency_stub
    [职责] 由应用启动期覆写为 get_market_service
    [来源标注] [DD-M推断:解耦 FastAPI 启动配置与控制器模块]
    """
    raise NotImplementedError("Service dependency not configured")
