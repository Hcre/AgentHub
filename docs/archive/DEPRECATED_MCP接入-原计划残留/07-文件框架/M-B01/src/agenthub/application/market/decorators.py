"""CachedMCPServerRepository 缓存装饰器（Cache Proxy）.

[文件路径] src/agenthub/application/market/decorators.py
[文件职责] 在 MCPServerRepository 上叠加 Redis 读穿透/写回缓存（TTL 30min）
[所属模块] M-B01
[关联设计规范] MD-MCP-V1.0-20260602#M-B01 / FS-MCP-V1.0-20260602#FS-005
[功能描述]
  功能1: get 路径先查 Redis，未命中回源 DB 并回填
  功能2: 缓存击穿保护：单飞（in-proc asyncio.Lock 短路）
  功能3: 缓存 key 命名空间：market:server:{uuid}
[输入输出]
  输入: server_id (UUID)
  输出: MCPServerDetail（来自缓存或 DB）
[依赖关系]
  依赖文件: agenthub.application.market.repositories / agenthub.data.cache（M-D03）
  被依赖文件: agenthub.application.market.services
[注意事项]
  注意1: 缓存失效策略：M-B05 创建成功事件触发 DEL（事件驱动，由 M-EV01 订阅）
  注意2: 缓存击穿：使用 SETNX 短路 + 短 TTL 兜底
  注意3: 跨模块依赖 M-D03 的 RedisClusterClient（[DD-001:FS-021]），需在导入层显式声明
[代码风格] 遵循 CS-MCP-V1.0-20260602 §1
[创建日期] 2026-06-02
[修改历史]
  2026-06-02: DD-M-B01 - 初版缓存代理
[作者] DD-M-B01-20260602
[来源标注] [DD-001:FS-005/MD-MCP#M-B01/FS-021#CacheProxy]
"""
from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from agenthub.application.market.repositories import MCPServerRepository
from agenthub.application.market.schemas import MCPServerDetail
from agenthub.core.logging import get_logger

if TYPE_CHECKING:
    from agenthub.data.cache.client import RedisClusterClient  # 跨模块 M-D03

log = get_logger(__name__)

CACHE_TTL_SEC: int = 1800  # 30 分钟
CACHE_KEY_PREFIX: str = "market:server:"
CACHE_BLANK_KEY: str = "market:server:__null__"  # 防穿透墓碑
BLANK_TTL_SEC: int = 30  # 墓碑短 TTL


class CachedMCPServerRepository(MCPServerRepository):
    """缓存代理（装饰 MCPServerRepository）.

    [类名] CachedMCPServerRepository
    [职责] 在 get 路径前置 Redis 读穿透，写路径无效化（仅 M-B05 触发）
    [关联设计规范] MD-MCP-V1.0-20260602#M-B01
    [属性]
      属性1: inner MCPServerRepository 被装饰的仓储
      属性2: cache RedisClusterClient Redis 客户端（跨模块 M-D03）
    [方法列表]
      方法1: get(server_id) - 缓存优先 + 回源 + 回填
      方法2: invalidate(server_id) - 主动失效（订阅 mcp.created 事件后调用）
    [状态机] 缓存项状态：MISS → LOADING → HIT → EXPIRED
    [异常处理]
      异常1: RedisConnectionError - 降级为直接 DB 查询 + WARN 日志
    [来源标注] [DD-001:MD-MCP#M-B01/FS-021]
    """

    def __init__(
        self,
        inner: MCPServerRepository,
        cache: "RedisClusterClient",
    ) -> None:
        """构造缓存代理.

        [函数名] __init__
        [职责] 注入内层仓储与 Redis 客户端
        [参数说明]
          参数1: inner MCPServerRepository 必填
          参数2: cache RedisClusterClient 必填
        [返回值] None
        [来源标注] [DD-001:FS-021]
        """
        super().__init__(session=inner._session)  # type: ignore[arg-type]
        self._inner = inner
        self._cache = cache

    async def get(self, server_id: UUID) -> MCPServerDetail:
        """缓存优先的 get.

        [函数名] get
        [职责] 1)查 Redis; 2)命中反序列化; 3)未命中回源 + 回填 + 写入墓碑防穿透
        [关联接口契约] IC-MCP-V1.0-20260602 API-100
        [参数说明]
          参数1: server_id UUID 必填
        [返回值]
          类型: MCPServerDetail
        [错误码]
          错误码1: MARKET_NOT_FOUND 404（墓碑命中视为 not-found）
        [并发安全] 同一 server_id 短暂单飞（in-proc lock）
        [幂等性] 是
        [性能约束] 命中 ≤ 50ms / 未命中 ≤ 200ms
        [来源标注] [DD-001:MD-MCP#M-B01]
        """
        ...

    async def invalidate(self, server_id: UUID) -> None:
        """主动失效缓存.

        [函数名] invalidate
        [职责] DEL market:server:{id}（M-B05 创建/更新事件触发）
        [参数说明]
          参数1: server_id UUID 必填
        [返回值] None
        [并发安全] 单 key 无锁
        [幂等性] 是（DEL 重复无副作用）
        [来源标注] [DD-M推断:M-B05 mcp.created 事件订阅触发]
        """
        ...
