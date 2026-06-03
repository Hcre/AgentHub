# 设计决策记录 DDR-MCP-V1.0-20260602

> 12 条重大设计决策，含决策内容/理由/拒绝方案/影响范围/状态
> 所有 DDR 状态：已接受（不会进入实施前，DDR-009 标演进事项）

---

## DDR-001 选定分层 + Repository + Saga + 事件总线为主设计骨架

```
[决策编号] DDR-001
[决策标题] 选定主设计架构骨架
[决策状态] 已接受
[决策内容]
  - 模块分 4 层（access/application/infrastructure/data）+ eventbus 横切
  - 业务核心走 Service Layer + Repository
  - 长事务走 Saga + Compensation（M-B05 / M-C09）
  - 跨进程通信走 Event Bus（Redis Pub/Sub + 关键 topic Stream）
[决策理由]
  方案对比（DD-MCP §2.2）：主方案 8.85 vs 备选 7.05；
  原始 100 分制差值 18 ≥ 5（soul 4.11 阈值）；
  主方案在模块细化/契约/数据结构/文件结构 4 维全面胜出。
[拒绝的替代方案]
  Hexagonal + CQRS + 事件溯源：
    - 双模型复杂度高
    - 事件存储 + 快照机制对 V1.0 强一致 PG 场景过度
    - 包结构膨胀（每 bounded context 一套模型）
  违反 R14 禁止过度设计原则。
[影响范围] 全部 22 模块；30 个 DS；22 个 IC
[相关 DDR] DDR-002 / DDR-003 / DDR-005
[来源] [DD推断:soul 4.11 主备对比 + AR:ADR-001/003]
```

---

## DDR-002 关键 topic 用 Redis Stream，非关键用 Pub/Sub

```
[决策编号] DDR-002
[决策标题] Event Bus 双模式分级
[决策状态] 已接受
[决策内容]
  - 关键 topic（mcp.rollback_done / approval.timeout / mcp.created）→ Redis Stream + consumer group（至少一次）
  - 非关键 topic（process.health_changed / template.* 等）→ Redis Pub/Sub（fire-and-forget）
[决策理由]
  - Pub/Sub fire-and-forget 在客户端离线时丢失关键事件；
  - 全用 Stream 增加运维复杂度（max-len / 消费组管理）；
  - 分级降低 90% 流量的复杂度。
[拒绝方案]
  - 全用 Pub/Sub：风险 mcp.rollback_done 丢失导致 UI 与实际状态不一致
  - 全用 Stream：维护成本翻倍
  - 引入 Kafka：与 AR-001 选型不符（Redis 已是依赖）
[影响范围] M-EV01 / M-A02 WS / M-B05 Saga
[相关 DDR] DDR-001
[来源] [AR洞察-1 + DD推断:消息可靠性分级]
```

---

## DDR-003 Repository + UnitOfWork（M-D01）

```
[决策编号] DDR-003
[决策标题] 元数据存储采用 Repository + UnitOfWork
[决策状态] 已接受
[决策内容]
  - 30 个 Repository（对应 30 DE），每个继承 BaseRepository[T]
  - UnitOfWork 控制事务边界 + 自动 commit/rollback
  - 严格三层 controllers → services → repositories（禁跨层）
[决策理由]
  - 测试可 Mock Repository 而无需真 DB
  - 事务边界清晰
  - SQLAlchemy 2.x 异步原生支持
[拒绝方案]
  - Active Record：耦合度高，不利测试
  - 直接用 asyncpg：缺乏 ORM 类型安全
[影响范围] M-D01 + 全部业务模块的数据访问
[来源] [DD推断:经典 DDD 实践 + AR:TS-008]
```

---

## DDR-004 M-C03/M-C08 强制纯函数 + @in_process_only 装饰器

```
[决策编号] DDR-004
[决策标题] 纯函数模块禁止远程化
[决策状态] 已接受
[决策内容]
  - M-C03 模板引擎 / M-C08 命名转换强制 in-proc
  - 引入 @pure / @in_process_only 装饰器（agenthub.core.pure）
  - CI 静态检查（grep + ast 检查）
[决策理由]
  - 性能：< 5ms vs 远程 50ms+
  - 简化：无需序列化/反序列化/网络重试
  - 防御未来重构误为微服务
[拒绝方案]
  - 不约束：未来易被错误重构（[DD洞察-2]）
  - 改为微服务：性能回归 + 复杂度增加
[影响范围] M-C03 / M-C08 + CS 风格指南 + CI
[来源] [DD洞察-2]
```

---

## DDR-005 M-B05 Saga 中 K4 失败不补偿（直接标 rejected）

```
[决策编号] DDR-005
[决策标题] K4 失败的 Saga 补偿策略
[决策状态] 已接受
[决策内容]
  M-B05 Saga 5 步中：
  - dry_run / k4 失败 → 标 mcp_submission.status = rejected（无补偿）
  - secret / metadata / history 失败 → 反向补偿链
[决策理由]
  - K4 是分析步骤，无副作用（仅读 manifest）
  - 标 rejected 即可，无需"撤销分析"
  - dry_run 同理（沙箱执行有副作用但在沙箱内已隔离回收）
  - 简化补偿逻辑
[拒绝方案]
  - 全 Saga 都补偿：K4 无可补偿动作，浪费实现
  - K4 失败重试：K4 是确定性结果，重试无意义
[影响范围] M-B05 + EX-003
[来源] [DD洞察-3]
```

---

## DDR-006 M-B02 分布式锁双层（PG 主 + Redis Redlock 降级）

```
[决策编号] DDR-006
[决策标题] 进程池跨实例 spawn 锁的降级方案
[决策状态] 已接受
[决策内容]
  - 主路径：PG row-lock（SELECT FOR UPDATE on process_pool）
  - 降级路径：PG lock 失败 / timeout → Redis Redlock（5 节点）
  - 双层均失败 → 503 POOL_LOCK_UNAVAILABLE + CRITICAL 告警
[决策理由]
  - PG 是权威源；row-lock 性能可接受
  - PG 主库故障时若不降级，全 ws 的 spawn 全 timeout（SPOF）
  - Redlock 5 节点 quorum 提供高可用
[拒绝方案]
  - 仅 PG：SPOF
  - 仅 Redlock：与权威源不一致风险
  - ZooKeeper：增加新依赖，违反 R14
[影响范围] M-B02 + IC-004 + EX-015
[相关 DDR] DDR-001
[来源] [DD洞察-1 + AR洞察-2]
```

---

## DDR-007 公共 ArgsHasher 系统级单一实现

```
[决策编号] DDR-007
[决策标题] compute_args_hash 全系统统一实现
[决策状态] 已接受
[决策内容]
  - 函数位置：agenthub.application.approval.hasher.ArgsHasher.compute(args)
  - 算法：sorted_json(ensure_ascii=False) + SHA256
  - 全系统（Approval/Allowlist/Inbox）通过此唯一函数计算
  - 启动自检：跑 100 个已知样本对比预期 hash
[决策理由]
  - 多处实现易不一致（[AR:RSK-06]）
  - 不一致导致 allowlist 永远 miss / 重复审批
  - 启动自检防止重构引入 bug
[拒绝方案]
  - 各模块自行实现：风险高
  - 不做自检：bug 难发现
[影响范围] M-B04 + M-D03 + DS-009/011/020
[来源] [AR:ADR-006/RSK-06 + DD洞察-8]
```

---

## DDR-008 ApprovalService 启动 hash 函数自检

```
[决策编号] DDR-008
[决策标题] 审批服务启动时自检 hash 函数
[决策状态] 已接受
[决策内容]
  ApprovalService 启动时：
  1. 加载 100 个 (args_dict, expected_hash) 测试向量
  2. 跑 ArgsHasher.compute 对比
  3. 任一不一致 → fail-fast 拒绝启动 + CRITICAL 告警
[决策理由]
  - hash 函数被修改会导致历史 allowlist 全失效 + inbox 雪崩
  - 启动自检 < 1s 成本，可避免 P0 故障
[拒绝方案]
  - 不自检：风险高
  - 运行时定期校验：太晚（已造成业务影响）
[影响范围] M-B04 启动逻辑
[相关 DDR] DDR-007
[来源] [DD洞察-8 + EX-005]
```

---

## DDR-009 M-B02 子模块拆分上限（演进事项）

```
[决策编号] DDR-009
[决策标题] M-B02 子模块数监控与演进规划
[决策状态] 已接受（演进事项，V2.0 评估）
[决策内容]
  - V1.0：7 个子模块（pool/spawner/lifecycle/health/recycle/evict/locks）
  - 阈值：若 V2.0 引入 NUMA 绑核 / GPU 亲和性，子模块 > 10 时拆分子包
  - 监控指标：lines of code per submodule（CI 告警 > 800 LoC）
[决策理由]
  - 当前 7 个仍符合 soul 4.7 子模块 2-5 上限的"实质合理"范围
  - 提前规划演进路径避免一次性大重构
[拒绝方案]
  - 立即拆分：当前规模未达必要性
  - 不规划：未来重构成本高
[影响范围] M-B02 / FS-006 / 未来 V2.0 设计
[来源] [DD洞察-4]
```

---

## DDR-010 GDPR 合规：append-only 表的逻辑删除接口

```
[决策编号] DDR-010
[决策标题] append-only 表的合规删除
[决策状态] 已接受
[决策内容]
  - DS-010 inbox_decision / DS-013 mcp_submission_history / DS-019 mcp_migration_history append-only
  - 增加 `redacted` BOOLEAN 字段 + `redacted_at` TIMESTAMPTZ
  - 提供运维 API: POST /admin/redact (admin only)
  - 实施 GDPR right to erasure 时，PII 字段置 NULL 并设 redacted=true（保留行用于审计链）
[决策理由]
  - 物理删除破坏 append-only 哈希链
  - 逻辑删除保留链同时合规
[拒绝方案]
  - 物理删除：破坏审计链
  - 不实施：违反 GDPR
[影响范围] DS-010/013/019 + 新增 admin API
[来源] [AR洞察-12 + DD洞察-5]
```

---

## DDR-011 全局测试覆盖率分级

```
[决策编号] DDR-011
[决策标题] 测试覆盖率分级目标
[决策状态] 已接受
[决策内容]
  - 核心模块（M-B02/M-B04/M-B05/M-C01/M-C02/M-C06）：行 ≥ 90% / 分支 ≥ 80%
  - 一般模块：行 ≥ 80% / 分支 ≥ 70%
  - 工具/装饰器（@pure 等）：行 ≥ 95%
  - CI 强制（pytest --cov-fail-under=80 全局；核心模块独立 fail-under=90）
[决策理由]
  分级避免"为覆盖而覆盖"的低价值测试。
[拒绝方案]
  - 全 90%：成本高，部分模块（如 M-D02 仅 init）不必要
  - 全 80%：核心模块覆盖不足
[影响范围] 全部模块 + CI 配置
[来源] [DD推断:测试策略分级]
```

---

## DDR-012 健康度仪表盘与 DDI 计算公式锁定

```
[决策编号] DDR-012
[决策标题] DDI 权重与计算公式
[决策状态] 已接受
[决策内容]
  采用 soul 2.2 八维权重不变：
  D1=0.18 / D2=0.18 / D3=0.14 / D4=0.12 / D5=0.12 / D6=0.10 / D7=0.08 / D8=0.08
  最终 DDI = Σ W_i × (D_i / OPT_i)
[决策理由]
  - soul 规范固定，禁自行调权
  - 健康度仪表盘每轮输出（R25）
[影响范围] DH-MCP 文档
[来源] [soul 2.2/2.3]
```

---

## DDR 统计

| DDR | 状态 | 影响范围 |
|-----|------|---------|
| DDR-001 ~ DDR-012 | 已接受（DDR-009 演进事项） | 见各 DDR |
| 总数 | 12 |  |
| 拒绝方案数 | 平均 2.1 个/DDR |  |

**[DD 洞察-9]** DDR-006 与 DDR-008 互为护栏：DDR-006 防数据层故障，DDR-008 防逻辑层 bug。两者覆盖了 M-B02/M-B04 两大核心模块的"灾难性失效"路径，符合 soul R14 防御性编程而非过度设计。

**设计决策记录文档结束。**
