"""M-B04 Approval Engine — Allowlist Cache Proxy（Redis 30d + PG 兜底）.

[文件路径] src/agenthub/application/approval/allowlist.py
[文件职责] AllowlistCache 缓存代理；Redis 优先，未命中走 PG，再回填 Redis
[所属模块] M-B04
[关联设计规范] FS-008 / MD:M-B04 类设计 #4
[关联接口契约] IC-005 (allowlist 命中路径)
[功能描述]
  功能1: is_allowed(key) → bool   Cache Proxy 查询
  功能2: set_allowed(key)         写入 Redis SETEX + PG UPSERT
  功能3: invalidate(key)          失效（审批撤销场景）
[输入输出]
  输入: 哈希 key = sha256(workspace_id|mcp_id|tool|args_hash)
  输出: bool（是否在 30d allowlist 中）
[依赖关系]
  依赖文件: queue_repo (PG fallback) / hasher (key 复合算法)
  跨模块依赖（只读）:
    - agenthub.data.cache.client (RedisClusterClient, M-D03)
    - agenthub.data.metadata.repositories.allowlist (AllowlistRepository, M-D01)
  被依赖文件: services.py
[注意事项]
  注意1: Redis 不可用时必须降级直查 PG，不可 fail-fast（保守可用性）
  注意2: PG 命中后必须回填 Redis（设置 TTL 30d）以加速后续查询
  注意3: SETEX 必须使用 30d = 2592000 秒；与 allowlist_30d 表周期一致
  注意4: 失效场景：审批撤销 / workspace 删除（由上层主动调用 invalidate）
[代码风格] 遵循 CS §1.3 类型注解 + §1.8 async
[创建日期] 2026-06-03
[修改历史]
  2026-06-03: DD-M-B04 - 初始框架（仅注释）
[作者] DD-M-B04-20260603
[来源标注] [DD-001:MD:M-B04 类设计 #4 + IC-005 + AR洞察-6]
"""

from __future__ import annotations

# 实际 import 由 DD-S 阶段补全

# ---------------------------------------------------------------------------
# 类注释 — AllowlistCache
# ---------------------------------------------------------------------------
# [类名] AllowlistCache
# [职责] 允许列表的 Cache Proxy（Redis 优先 + PG 兜底）
# [关联设计规范] MD:M-B04 类设计 #4 + 设计模式 Cache Proxy
# [属性]
#   redis: RedisClusterClient    M-D03 客户端
#   repo:  AllowlistRepository   M-D01 Repository（PG 兜底）
#   ttl:   int = 2592000         30 天 (秒)
# [方法列表]
#   async is_allowed(key: str) → bool
#       - cache hit: 返回缓存值
#       - cache miss: 查 PG → 命中则回填 Redis SETEX → 返回
#       - cache + PG 均未命中: 返回 False
#   async set_allowed(key: str) → None
#       - PG UPSERT allowlist_30d + Redis SETEX 30d
#   async invalidate(key: str) → None
#       - Redis DEL + PG DELETE
#   @staticmethod
#   build_key(ws: UUID, mcp: UUID, tool: str, args_hash: str) → str
#       - 复合键: sha256(f"{ws}|{mcp}|{tool}|{args_hash}")
# [状态机] 无
# [异常处理]
#   RedisConnectionError → 降级直查 PG（WARN 日志）
#   DBError             → 上抛 ApprovalDBUnavailable
# [来源标注] [DD-001:MD:M-B04 类设计 #4 + DD-M-B04 推断: 增加 build_key 静态方法集中复合键算法]


# ---------------------------------------------------------------------------
# 函数注释 — is_allowed
# ---------------------------------------------------------------------------
# [函数名] is_allowed
# [职责] 查询 key 是否在 30d allowlist 中
# [关联接口契约] IC-005 (cache hit/miss 分支)
# [参数说明]
#   key: str  必填  AllowlistCache.build_key(...) 的输出
#       校验: 长度 = 64（SHA256 hex）
# [返回值]
#   类型: bool
#   描述: True = 在 allowlist / False = 不在
#   特殊值: Redis + PG 双不可达时 fail-safe 返回 False（保守，触发上层 pending）
# [错误码]
#   RedisConnectionError → 降级 PG 查询（WARN）
#   DBError              → 上抛 ApprovalDBUnavailable
# [前置条件] key 已通过 build_key 计算
# [后置条件]
#   - cache hit: 不变
#   - cache miss + PG hit: Redis 回填 (SETEX 30d)
#   - 双 miss: 不变
# [并发安全] Redis cluster 原子 GET；PG 只读
# [幂等性] 是（只读查询）
# [性能约束] P95 ≤ 5ms (cache hit) / P95 ≤ 50ms (PG fallback)
# [示例]
#   key = AllowlistCache.build_key(ws, mcp, tool, args_hash)
#   if await cache.is_allowed(key):
#       return Decision.allowed
# [来源标注] [DD-001:IC-005 + MD:M-B04 + AR洞察-6]


# ---------------------------------------------------------------------------
# 函数注释 — set_allowed
# ---------------------------------------------------------------------------
# [函数名] set_allowed
# [职责] 将 key 写入 allowlist（PG UPSERT + Redis SETEX）
# [关联接口契约] IC-006 (审批 allow 时调用)
# [参数说明]
#   key: str  必填  复合键
# [返回值] None
# [错误码]
#   DBError              → 上抛 ApprovalDBUnavailable（应在事务中调用，整体回滚）
#   RedisConnectionError → 仅 WARN 日志，不影响 PG 写入成功
# [前置条件] 已在 services.decide 的 UoW 事务中
# [后置条件]
#   - PG allowlist_30d 表 UPSERT
#   - Redis SETEX key, "1", 2592000 (30d)
# [并发安全] PG UPSERT 原生原子；Redis SETEX 原子
# [幂等性] 是；同 key 重复调用结果一致（TTL 刷新）
# [性能约束] P95 ≤ 20ms
# [示例]
#   async with uow:
#       await cache.set_allowed(key)
#       await uow.commit()
# [来源标注] [DD-001:IC-006 时序图 + MD:M-B04]


# ---------------------------------------------------------------------------
# 函数注释 — invalidate
# ---------------------------------------------------------------------------
# [函数名] invalidate
# [职责] 失效指定 key（审批撤销 / workspace 删除）
# [关联接口契约] 内部接口
# [参数说明]
#   key: str  必填
# [返回值] None
# [错误码] 同上
# [幂等性] 是
# [性能约束] P95 ≤ 20ms
# [来源标注] [DD-M-B04 推断: MD 未明确撤销路径，但 30d 周期内必须支持失效以应对策略变更]


# ---------------------------------------------------------------------------
# 函数注释 — build_key
# ---------------------------------------------------------------------------
# [函数名] build_key
# [职责] 复合键构造（系统级唯一算法）
# [参数说明]
#   ws:        UUID  必填
#   mcp:       UUID  必填
#   tool:      str   必填
#   args_hash: str   必填（ArgsHasher.compute_args_hash 输出）
# [返回值] str  长度 64 (SHA256 hex)
# [前置条件] args_hash 已通过 ArgsHasher 计算
# [并发安全] 纯函数线程安全
# [幂等性] 是
# [性能约束] < 1ms
# [来源标注] [DD-M-B04 推断: 避免 services 内重复拼装，集中算法]
