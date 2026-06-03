# API-M-B02-MCP-V1.0-20260603 接口注释清单（M-B02 Process Pool Manager）

> 接口契约注释化清单（DD-M-B02）
> 来源 [DD-001:IC-004 + MD-MCP-M-B02]

---

## API-001 pool.spawn（IC-004）

```
[接口编号] IC-004 / API-110
[接口名称] pool.spawn
[关联契约] IC-004
[实现文件] src/agenthub/application/pool/controllers.py
[函数签名注释]
  @router.post("/spawn", response_model=SpawnResponse)
  async def spawn(
      request: Request,
      body: SpawnRequest,
      service: PoolService = Depends(get_pool_service),
  ) -> SpawnResponse:
      """
      在指定 workspace 内 spawn MCP 子进程。

      Args:
          body.mcp_id: MCP UUID（必填）
          body.workspace_id: workspace UUID（必填）
          body.reserved_slot: 仅预留槽位不实际 fork（可选，默认 false）
          service: PoolService（DI 注入）

      Returns:
          SpawnResponse（pid / state / trace_id）

      Raises:
          HTTPException 429: POOL_FULL（池满，触发 LRU 驱逐后重试 1 次）
          HTTPException 500: POOL_SPAWN_FAILED（fork 失败，reserved slot + 告警）
          HTTPException 503: POOL_LOCK_TIMEOUT（PG + Redis 双层锁均超时）

      前置条件: mcp_id 已通过 K4 校验；ws 槽位 < 64
      后置条件: process_pool 表新增；事件 process.spawned 发布
      并发安全: DistributedLock（PG row-lock 主 + Redis Redlock 5 节点降级）
      幂等性: 是（幂等键 (ws_id, mcp_id) UNIQUE）
      性能约束: P95 ≤ 1.2s（含冷启动）

      Example:
          POST /pool/spawn
          {
            "mcp_id": "01HXX...",
            "workspace_id": "01HXX...",
            "reserved_slot": false
          }
      """
```

[来源标注] [DD-001:IC-004 + API-110]

---

## API-002 pool.spawn_reserved

```
[接口编号] API-110 扩展
[接口名称] pool.spawn_reserved
[关联契约] IC-004（POOL_RESERVED 错误码）
[实现文件] src/agenthub/application/pool/controllers.py
[函数签名注释]
  @router.post("/spawn_reserved", response_model=SpawnResponse, status_code=202)
  async def spawn_reserved(
      request: Request,
      body: SpawnRequest,
      service: PoolService = Depends(get_pool_service),
  ) -> SpawnResponse:
      """
      仅预留槽位（HTTP 202）。

      Args:
          body: spawn 请求（reserved_slot 强制 true）
          service: PoolService

      Returns:
          SpawnResponse（state="reserved"）

      Raises:
          HTTPException 429: POOL_RESERVED
              池满时仅预留槽位，客户端需轮询

      前置条件: 池满 64/ws
      后置条件: 槽位已预留；客户端轮询 GET /pool/stats/{ws_id}
      并发安全: DistributedLock
      幂等性: 是
      """
```

[来源标注] [DD-M推断:DD-001 IC-004 POOL_RESERVED 错误码]

---

## API-003 pool.stats

```
[接口编号] API-110 扩展
[接口名称] pool.stats
[关联契约] IC-004 扩展
[实现文件] src/agenthub/application/pool/controllers.py
[函数签名注释]
  @router.get("/stats/{ws_id}", response_model=PoolStats)
  async def get_stats(
      ws_id: UUID,
      service: PoolService = Depends(get_pool_service),
  ) -> PoolStats:
      """
      获取指定 workspace 的进程池统计。

      Args:
          ws_id: workspace UUID
          service: PoolService

      Returns:
          PoolStats（active / idle / zombie 计数 + max_capacity=64）

      前置条件: 无
      后置条件: 无
      并发安全: 无状态
      幂等性: 是
      性能约束: P95 ≤ 50ms
      """
```

[来源标注] [DD-001:MD-MCP-M-B02 stats 子模块]

---

## API-004 pool.evict

```
[接口编号] API-110 扩展
[接口名称] pool.evict
[关联契约] IC-004 扩展
[实现文件] src/agenthub/application/pool/controllers.py
[函数签名注释]
  @router.post("/evict", response_model=list[UUID])
  async def evict(
      body: EvictRequest,
      service: PoolService = Depends(get_pool_service),
  ) -> list[UUID]:
      """
      显式触发 LRU 驱逐。

      Args:
          body.count: 驱逐数量（1-64）
          service: PoolService

      Returns:
          被驱逐的进程 UUID 列表

      前置条件: 至少 1 个可驱逐进程
      后置条件: 进程已 SIGTERM；状态转 recycled
      并发安全: asyncio.Lock
      幂等性: 否
      性能约束: P95 ≤ 1s
      """
```

[来源标注] [DD-001:MD-MCP-M-B02 evict 子模块]

---

## 内部接口清单（in-proc，不入 IC）

```
[内部接口] ProcessPool.spawn
  文件: pool.py
  调用方: PoolService.spawn
  注释: [见 pool.py 函数签名注释]

[内部接口] ProcessSpawner.create
  文件: spawner.py
  调用方: ProcessPool.spawn
  注释: [见 spawner.py 函数签名注释]

[内部接口] ProcessStateMachine.transition
  文件: lifecycle.py
  调用方: ProcessPool / HealthChecker / IdleRecycler
  注释: [见 lifecycle.py 函数签名注释]

[内部接口] HealthChecker.check
  文件: health.py
  调用方: ProcessPool.healthcheck_all
  注释: [见 health.py 函数签名注释]

[内部接口] IdleRecycler.recycle_idle
  文件: recycle.py
  调用方: ProcessPool.healthcheck_all（cron 触发）
  注释: [见 recycle.py 函数签名注释]

[内部接口] LRUEvictor.evict_lru
  文件: evict.py
  调用方: ProcessPool.evict_lru
  注释: [见 evict.py 函数签名注释]

[内部接口] DistributedLock.acquire / release / renew
  文件: locks.py
  调用方: ProcessPool.spawn
  注释: [见 locks.py 函数签名注释]
```

[来源标注] [DD-001:IC-022 in-proc 接口约束 + MD-MCP-M-B02]
