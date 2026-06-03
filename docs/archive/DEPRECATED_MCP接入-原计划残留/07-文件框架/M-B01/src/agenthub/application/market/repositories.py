"""MCPServerRepository 数据访问层.

[文件路径] src/agenthub/application/market/repositories.py
[文件职责] 封装 SQLAlchemy 查询；提供 list/get/search 三个方法
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005
[功能描述]
  功能1: list(filter) - 按 tag/page/size 拉取 MCP Server 列表
  功能2: get(id) - 按 UUID 取单个 MCP Server（不命中缓存）
  功能3: search(q) - 关键词搜索
[输入输出]
  输入: 过滤条件 / UUID / 搜索词
  输出: ORM 模型 / DTO（视实现选择）
[依赖关系]
  依赖文件: agenthub.data.metadata.models.mcp_server（ORM 35 表，跨模块）
  被依赖文件: agenthub.application.market.services / decorators
[注意事项]
  注意1: Repository 不在 M-B01 业务层定义 — 实际继承 M-D01 BaseRepository 范型（[DD-001:FS-019]）
  注意2: 跨模块依赖 M-D01，需在文件头注释显式标注（避免循环导入风险）
  注意3: 写入操作不属于 M-B01 范围（由 M-B05 负责）
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1 / §2（SQL 风格）
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版仓储
[作者] DD-M-B01-20260602
[来源标注] [DD-001:FS-005/MD-MCP#M-B01/FS-019#BaseRepository]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from agenthub.application.market.schemas import ListFilter, MCPServerDTO, MCPServerDetail, Page
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from agenthub.data.metadata.models.mcp_server import MCPServerORM  # 跨模块 M-D01

log = get_logger(__name__)


class MCPServerRepository:
    """MCP Server 仓储.

    [类名] MCPServerRepository
    [职责] 封装 mcp_servers 表的查询
    [关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-019#BaseRepository
    [属性]
      属性1: session AsyncSession SQLAlchemy 异步会话
    [方法列表]
      方法1: list(filter) -> Page[MCPServerDTO] - 分页列表
      方法2: get(server_id) -> MCPServerDetail - 单个查询
      方法3: search(q, tags, page, size) -> Page[MCPServerDTO] - 搜索
    [异常处理]
      异常1: DBError - 数据库故障，包装为领域异常
      异常2: NotFoundError - get 不到时抛出
    [来源标注] [DD-001:MD-MCP#M-B01/FS-019]
    """

    def __init__(self, session: "AsyncSession") -> None:
        """构造仓储.

        [函数名] __init__
        [职责] 注入 AsyncSession
        [参数说明]
          参数1: session AsyncSession 必填
        [返回值] None
        [来源标注] [DD-001:FS-019#BaseRepository]
        """
        self._session = session

    async def list(self, filter_payload: ListFilter) -> Page[MCPServerDTO]:
        """分页查询 MCP Server.

        [函数名] list
        [职责] SELECT FROM mcp_servers WHERE tags && filter.tags ORDER BY ... LIMIT/OFFSET
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: filter_payload ListFilter 必填
        [返回值]
          类型: Page[MCPServerDTO]
          描述: 分页结果
        [错误码]
          错误码1: MARKET_DB_UNAVAILABLE 503
        [并发安全] SELECT 无锁
        [幂等性] 是
        [性能约束] P95 ≤ 200ms
        [来源标注] [DD-001:MD-MCP#M-B01]
        """
        ...

    async def get(self, server_id: UUID) -> MCPServerDetail:
        """按 UUID 查询单个 MCP Server.

        [函数名] get
        [职责] SELECT * FROM mcp_servers WHERE id = :id
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: server_id UUID 必填
        [返回值]
          类型: MCPServerDetail
          描述: 完整 DTO
        [错误码]
          错误码1: MARKET_NOT_FOUND 404
        [并发安全] SELECT
        [幂等性] 是
        [性能约束] P95 ≤ 100ms
        [来源标注] [DD-001:MD-MCP#M-B01]
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
        [职责] SELECT WHERE name ILIKE :q OR description ILIKE :q AND tags && :tags
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: q str 必填
          参数2: tags list[str] 可选
          参数3: page int 必填
          参数4: size int 必填
        [返回值]
          类型: Page[MCPServerDTO]
        [错误码]
          错误码1: MARKET_VALIDATION 400 q 为空
        [并发安全] SELECT
        [幂等性] 是
        [性能约束] P95 ≤ 400ms
        [来源标注] [DD-001:MD-MCP#M-B01]
        """
        ...
