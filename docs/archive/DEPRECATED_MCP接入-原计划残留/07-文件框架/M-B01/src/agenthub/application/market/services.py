"""Market Service 业务编排层.

[文件路径] src/agenthub/application/market/services.py
[文件职责] 编排 repositories + cache；提供 list_servers/get_detail/search 业务能力
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005
[功能描述]
  功能1: list_servers 根据 ListFilter 查询并返回分页结果
  功能2: get_detail 走 CachedMCPServerRepository 装饰路径（缓存 30min TTL）
  功能3: search 关键词 ILIKE + 标签过滤，结果分页
[输入输出]
  输入: 上层传入的 DTO（ListFilter / UUID / 搜索参数）
  输出: Page[MCPServerDTO] / MCPServerDetail
[依赖关系]
  依赖文件: agenthub.application.market.repositories / decorators / schemas
  被依赖文件: agenthub.application.market.controllers
[注意事项]
  注意1: Service 层禁止直接写 SQL；所有 DB 操作通过 Repository
  注意2: 缓存 key 命名空间：market:server:{id} / market:list:{filter_hash}（[DD-M推断]）
  注意3: 失败重试：DBError 触发 1 次重试 + 告警（[DD-001:MD-MCP#M-B01]）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1.6 异常链 / §1.8 async/await
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版服务层
[作者] DD-M-B01-20260602
[来源标注] [DD-001:MD-MCP#M-B01/FS-005]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from agenthub.application.market.schemas import (
    ListFilter,
    MCPServerDetail,
    MCPServerDTO,
    Page,
)
from agenthub.core.exceptions import NotFoundError
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.application.market.decorators import CachedMCPServerRepository
    from agenthub.application.market.repositories import MCPServerRepository

log = get_logger(__name__)


class MarketService:
    """Market 业务编排.

    [类名] MarketService
    [职责] 编排查询、详情、搜索三个核心方法，处理缓存与重试
    [关联设计规范] MD-MCP-V1.0-20260602#M-B01
    [属性]
      属性1: repo MCPServerRepository 基础仓储实例
      属性2: cache_repo CachedMCPServerRepository 装饰后的仓储（注入到 get_detail）
    [方法列表]
      方法1: list_servers(filter) -> Page[MCPServerDTO] - 列表查询
      方法2: get_detail(server_id) -> MCPServerDetail - 详情查询（带缓存）
      方法3: search(q, tags, page, size) -> Page[MCPServerDTO] - 搜索
    [异常处理]
      异常1: NotFoundError - server_id 不存在
      异常2: DBError - 数据库不可用，重试 1 次
    [来源标注] [DD-001:MD-MCP#M-B01/FS-005]
    """

    def __init__(
        self,
        repo: "MCPServerRepository",
        cache_repo: "CachedMCPServerRepository | None" = None,
    ) -> None:
        """构造 MarketService.

        [函数名] __init__
        [职责] 注入仓储与缓存仓储
        [参数说明]
          参数1: repo MCPServerRepository 必填
          参数2: cache_repo CachedMCPServerRepository 可选（get_detail 必须）
        [返回值] None
        [来源标注] [DD-001:MD-MCP#M-B01]
        """
        self._repo = repo
        self._cache_repo = cache_repo

    async def list_servers(self, filter_payload: ListFilter) -> Page[MCPServerDTO]:
        """分页列出 MCP Server.

        [函数名] list_servers
        [职责] 按 ListFilter 查询 MCP Server 列表
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: filter_payload ListFilter 必填 含 tags/page/size/sort
        [返回值]
          类型: Page[MCPServerDTO]
          描述: 分页结果
        [错误码]
          错误码1: MARKET_DB_UNAVAILABLE 503 DB 故障
        [前置条件] filter_payload 校验通过
        [后置条件] 列表只读，无副作用
        [并发安全] 只读
        [幂等性] 是
        [性能约束] P95 ≤ 300ms
        [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
        """
        ...

    async def get_detail(self, server_id: UUID) -> MCPServerDetail:
        """获取 MCP Server 详情（带缓存）.

        [函数名] get_detail
        [职责] 优先命中 Redis 缓存（30min TTL），未命中回源 DB 并回填
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: server_id UUID 必填
        [返回值]
          类型: MCPServerDetail
          描述: 完整详情 DTO
        [错误码]
          错误码1: MARKET_NOT_FOUND 404 server 不存在
          错误码2: MARKET_DB_UNAVAILABLE 503
        [前置条件] server_id 合法 UUID
        [后置条件] 缓存被回填（30min TTL）
        [并发安全] 只读
        [幂等性] 是
        [性能约束] 缓存命中 ≤ 50ms / 未命中 ≤ 200ms
        [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
        """
        ...

    async def search(
        self,
        q: str,
        tags: list[str],
        page: int,
        size: int,
    ) -> Page[MCPServerDTO]:
        """关键词 + 标签搜索.

        [函数名] search
        [职责] 在 name/description 上做 ILIKE 模糊匹配 + tags 数组包含
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: q str 必填 1-128 字符
          参数2: tags list[str] 可选
          参数3: page int 必填 ≥ 1
          参数4: size int 必填 1-100
        [返回值]
          类型: Page[MCPServerDTO]
          描述: 搜索结果
        [错误码]
          错误码1: MARKET_VALIDATION 400
        [并发安全] 只读
        [幂等性] 是
        [性能约束] P95 ≤ 500ms
        [来源标注] [DD-001:MD-MCP#M-B01/IC-MCP#API-100]
        """
        ...
