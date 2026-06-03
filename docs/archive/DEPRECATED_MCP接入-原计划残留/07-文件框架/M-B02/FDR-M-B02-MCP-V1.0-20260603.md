# FDR-M-B02-MCP-V1.0-20260603 框架决策记录（M-B02 Process Pool Manager）

> 重大框架决策记录（DD-M-B02）
> 来源 [DD-001:MD-MCP-M-B02 + DD洞察-1 + 4.11 多方案对比]

---

## FDR-001 选择扁平单包（方案 A）而非子包分层（方案 B）

```
[决策编号] FDR-001
[决策标题] M-B02 文件结构选择扁平单包
[决策状态] 已接受
[决策内容] M-B02 文件结构采用扁平单包布局（pool/ + pool/tests/），与 DD-001 FS-006 完全一致
[决策理由]
  1. 与 DD-001 FS-006 100% 对齐，避免破坏上游规范
  2. 主方案评分 10.00 > 备选 7.85，差距 2.15 > 阈值 0.5
  3. 文件数 17 在 [14, 35] 合理范围内
  4. 子包分层（方案 B）会引入额外 __init__.py 增加维护成本
[拒绝的替代方案]
  方案 B 子包分层:
    拒绝理由: 与 FS-006 不一致；DD-001 已锁定；增加无谓复杂度
[影响范围] M-B02 全部 17 个文件
[相关FDR] 无
[来源标注] [DD-001:FS-006 + 4.11 多方案对比]
```

---

## FDR-002 DistributedLock 双层锁设计

```
[决策编号] FDR-002
[决策标题] 分布式锁采用 PG 主 + Redis Redlock 降级
[决策状态] 已接受
[决策内容] M-B02 锁采用 PG row-lock 主链路 + Redis Redlock 5 节点降级
[决策理由]
  1. [DD洞察-1] 明确要求 PG → Redis 降级链路（防止 PG 故障时 spawn 全面阻塞）
  2. EX-015 跨边界异常处理要求 PG 不可达时降级
  3. Redis Redlock 5 节点满足分布式锁安全性（参考 Redis 官方推荐）
  4. 锁租约 30s + 心跳 10s 防进程崩溃锁泄漏
[拒绝的替代方案]
  仅 PG 单层:
    拒绝理由: PG 故障时所有 spawn 阻塞；违反 [DD洞察-1] 降级要求
  仅 Redis:
    拒绝理由: Redis cluster 故障时（EX-015）无任何锁可用
[影响范围] pool/locks.py + pool/pool.py
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-M-B02 + DD洞察-1 + EX-015]
```

---

## FDR-003 状态机 7 状态设计

```
[决策编号] FDR-003
[决策标题] 状态机采用 5 业务状态 + 2 异常状态
[决策状态] 已接受
[决策内容] ProcessStateMachine 包含 IDLE / SPAWN_REQUESTED / SPAWNING / RUNNING / RECYCLING / RECYCLED + ZOMBIE
[决策理由]
  1. MD-MCP-M-B02 严格定义 5 业务状态转换
  2. 增加 ZOMBIE 状态处理 health_fail × 3 异常路径
  3. RECYCLED 为终态；RECYCLING 是中间态（区分 in-flight 与 completed）
  4. SPAWN_REQUESTED 区分用户请求与实际 fork 开始（便于审计）
[拒绝的替代方案]
  4 状态简化版:
    拒绝理由: 失去 spawn 排队与回收中间态的区分，审计困难
  8 状态细分版:
    拒绝理由: 增加 RESERVED 等状态，违反 MD-MCP-M-B02 严格定义
[影响范围] pool/lifecycle.py + pool/models.py
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-M-B02 状态机定义]
```

---

## FDR-004 64/ws 硬约束

```
[决策编号] FDR-004
[决策标题] workspace 进程池上限 64 硬约束
[决策状态] 已接受
[决策内容] ProcessPool._max_per_ws = 64（不可配置）
[决策理由]
  1. AR:TS-001 + AC:AG-006 明确 64/ws 上限
  2. 池满触发 PoolFullError + LRU 驱逐 + 重试 1 次
  3. 上限不可配置（防止误调导致资源耗尽）
[拒绝的替代方案]
  可配置上限:
    拒绝理由: 增加运维复杂度；64 是经过容量评估的最优值
[影响范围] pool/pool.py
[相关FDR] 无
[来源标注] [DD-001:AR:TS-001 + AC:AG-006]
```

---

## FDR-005 cron 相位错开

```
[决策编号] FDR-005
[决策标题] healthcheck :00 + recycle :15/:45 相位错开
[决策状态] 已接受
[决策内容] healthcheck 30s :00 触发；recycle_idle 30s :15/:45 触发
[决策理由]
  1. 错开相位避免与 cron scheduler（M-A04）冲突（[AC:AG-004]）
  2. 健康检查与回收不同时执行（避免检查到正在回收的进程）
  3. :15/:45 双频回收更及时（5min 阈值下最多 5min+15s 回收）
[拒绝的替代方案]
  全部 :00:
    拒绝理由: 健康检查与回收同时进行，资源争抢
[影响范围] pool/health.py + pool/recycle.py
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-M-B02 + AC:AG-004 + RSK-05]
```

---

## FDR-006 LRU 跨 ws 全局策略

```
[决策编号] FDR-006
[决策标题] LRU 驱逐采用跨 ws 全局策略
[决策状态] 已接受
[决策内容] LRUEvictor 维护跨 ws 全局 LRU 双链表（不仅是 per-ws）
[决策理由]
  1. MD-MCP-M-B02 明确"LRU 驱逐"为跨 ws 全局
  2. 池满时可驱逐任意 ws 的最久未使用进程
  3. 简单 O(1) 增删（dict + 双向链表）
[拒绝的替代方案]
  per-ws LRU:
    拒绝理由: 池满时仍可能无空闲槽位；违反全局 LRU 语义
[影响范围] pool/evict.py + pool/pool.py
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-M-B02]
```

---

## FDR-007 严格测试策略 30 用例

```
[决策编号] FDR-007
[决策标题] M-B02 单元测试 30 用例覆盖率 ≥ 90%
[决策状态] 已接受
[决策内容] 测试用例 30 条（5 状态 × 6 事件），覆盖率行 ≥ 90%
[决策理由]
  1. MD-MCP-M-B02 明确 30 用例
  2. M-B02 是核心模块（spawn 是关键路径）
  3. 高覆盖率减少生产事故
[拒绝的替代方案]
  15 用例精简版:
    拒绝理由: 5 状态 × 6 事件覆盖不足
[影响范围] pool/tests/*.py
[相关FDR] 无
[来源标注] [DD-001:MD-MCP-M-B02 测试策略]
```

---

## FDR 统计

| 维度 | 数量 |
|------|------|
| 已接受 FDR | 7 |
| 已拒绝方案 | 7（含 1 主方案备选 + 6 子方案备选） |
| 影响文件数 | 17 / 17 |
| 决策可追溯性 | 100% |

[来源标注] [DD-001:MD-MCP-M-B02 + DD洞察-1 + 4.13 FDR 模板]
