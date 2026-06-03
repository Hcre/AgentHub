# M-B01 Market Service 接口注释清单

> API-M-B01-MCP-V1.0-20260602
> 负责模块：M-B01 Market Service
> 来源：[DD-001:IC-MCP#API-100/FS-005/MD-MCP#M-B01]

---

## API-100-01 list /market/list

```
[接口编号] API-100-01
[关联契约] IC-MCP-V1.0-20260602 API-100
[实现文件] src/agenthub/application/market/controllers.py:_list_endpoint
                → services.py:MarketService.list_servers
                → repositories.py:MCPServerRepository.list
[HTTP] POST /market/list
[函数签名注释]
  async def list_servers(
      filter_payload: ListFilter,  # 必填；含 tags/page/size/sort_by/order
  ) -> Page[MCPServerDTO]:        # 分页结果
      """
      列出 MCP Server.

      Args:
          filter_payload: 标签/分页/排序条件
      Returns:
          Page[MCPServerDTO]: items + total + page + size
      Raises:
          DBError: DB 不可用
      """
[参数说明]
  参数1: filter_payload ListFilter 必填 长度限制 1-1000
[返回值说明]
  类型: Page[MCPServerDTO]
  描述: items + total + page + size
[错误码说明]
  错误码1: MARKET_VALIDATION 422 Pydantic 校验失败
  错误码2: MARKET_DB_UNAVAILABLE 503 DB 故障
[来源标注] [DD-001:IC-MCP#API-100/FS-005]
```

## API-100-02 detail /market/{id}

```
[接口编号] API-100-02
[关联契约] IC-MCP-V1.0-20260602 API-100
[实现文件] src/agenthub/application/market/controllers.py:_detail_endpoint
                → services.py:MarketService.get_detail
                → decorators.py:CachedMCPServerRepository.get
[HTTP] GET /market/{server_id}
[函数签名注释]
  async def get_detail(
      server_id: UUID,  # 必填；路径参数
  ) -> MCPServerDetail:
      """
      获取 MCP Server 详情（带缓存）.

      Args:
          server_id: MCP Server UUID
      Returns:
          MCPServerDetail: 完整 DTO
      Raises:
          NotFoundError: server_id 不存在
          DBError: DB 不可用
      """
[参数说明]
  参数1: server_id UUID 必填
[返回值说明]
  类型: MCPServerDetail
  描述: id/name/manifest_json/tags/author/k4_score/version/created_at/updated_at
[错误码说明]
  错误码1: MARKET_NOT_FOUND 404
  错误码2: MARKET_DB_UNAVAILABLE 503
[缓存策略] Redis TTL 30min, key=market:server:{id}; 墓碑防穿透 TTL 30s
[来源标注] [DD-001:IC-MCP#API-100/FS-005]
```

## API-100-03 search /market/search

```
[接口编号] API-100-03
[关联契约] IC-MCP-V1.0-20260602 API-100
[实现文件] src/agenthub/application/market/controllers.py:_search_endpoint
                → services.py:MarketService.search
                → repositories.py:MCPServerRepository.search
[HTTP] GET /market/search?q=...&tag=...&page=...&size=...
[函数签名注释]
  async def search(
      q: str,           # 必填；1-128 字符
      tags: list[str],  # 可选；标签数组包含
      page: int,        # 必填；≥ 1
      size: int,        # 必填；1-100
  ) -> Page[MCPServerDTO]:
      """
      关键词 + 标签搜索.

      Args:
          q: 搜索关键词
          tags: 标签过滤
          page: 页码
          size: 每页大小
      Returns:
          Page[MCPServerDTO]
      Raises:
          DBError: DB 不可用
      """
[参数说明]
  参数1: q str 必填 1-128
  参数2: tags list[str] 可选
  参数3: page int 默认 1
  参数4: size int 默认 20
[返回值说明]
  类型: Page[MCPServerDTO]
[错误码说明]
  错误码1: MARKET_VALIDATION 422
  错误码2: MARKET_DB_UNAVAILABLE 503
[来源标注] [DD-001:IC-MCP#API-100/FS-005]
```

## in-proc 接口（IC-022 集）

```
[接口编号] IC-022-MB01
[关联契约] IC-MCP-V1.0-20260602#IC-022
[实现文件] src/agenthub/application/market/* (in-proc 内部调用)
[说明] controllers → services → repositories 三层内部调用；无需 RPC
[强制约束]
  - 100% 类型注解（PEP 484）
  - Google 风格 docstring
  - 异常链 raise X from e
[来源标注] [DD-001:IC-MCP#IC-022]
```
