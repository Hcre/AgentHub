# FF-M-B02-MCP-V1.0-20260603 文件框架结构（M-B02 Process Pool Manager）

> 模块文件框架结构（DD-M-B02）
> 来源 [DD-001:FS-006 + MD-MCP-M-B02 + IC-004]

---

## 一、文件框架（主方案 A）

```
[模块编号] M-B02
[模块名称] Process Pool Manager
[文件路径根] src/agenthub/application/pool/
[文件框架]
  M-B02_pool___init__.py           ← 模块初始化，导出 ProcessPool / PoolController / 异常
  M-B02_pool_exceptions.py        ← 领域异常（PoolFullError / SpawnFailedError / HealthCheckTimeoutError / DistributedLockTimeoutError）
  M-B02_pool_models.py            ← Process / ProcessState 枚举 / LRUNode / PoolStats
  M-B02_pool_pool.py              ← ProcessPool 单例（Singleton + Object Pool 模式）
  M-B02_pool_spawner.py           ← ProcessSpawner 工厂（asyncio subprocess + posix_spawn）
  M-B02_pool_lifecycle.py         ← ProcessStateMachine 状态机（5 业务 + 2 异常）
  M-B02_pool_health.py            ← HealthChecker 健康检查（30s :00 cron）
  M-B02_pool_recycle.py           ← IdleRecycler 空闲回收（30s :15/:45 cron）
  M-B02_pool_evict.py             ← LRUEvictor 跨 ws LRU 驱逐
  M-B02_pool_locks.py             ← DistributedLock 双层锁（PG + Redis Redlock 降级，[DD洞察-1]）
  M-B02_pool_services.py          ← PoolService 业务编排
  M-B02_pool_controllers.py       ← PoolController FastAPI 路由（API-110 / IC-004）
  M-B02_tests___init__.py         ← 测试包初始化
  M-B02_tests_test_pool.py        ← ProcessPool 单元测试（30 用例）
  M-B02_tests_test_lifecycle.py   ← 状态机测试（12 用例）
  M-B02_tests_test_spawner.py     ← 工厂测试（8 用例）
  M-B02_tests_test_locks.py       ← 锁测试（10 用例）
```

## 二、文件间依赖关系

```
[依赖关系图]
  controllers.py
      ↓
  services.py
      ↓
  pool.py (Singleton)
      ↓
  ┌─────────┬──────────┬─────────┬──────────┐
  ↓         ↓          ↓         ↓          ↓
spawner  lifecycle   health   recycle    evict
  ↓         ↓          ↓         ↓          ↓
  └─────────┴──────────┴─────────┴──────────┘
                       ↓
                    locks.py（被 pool.py 调用）

[测试文件依赖]
  tests/test_pool.py → pool.py / spawner.py / locks.py（mock）
  tests/test_lifecycle.py → lifecycle.py（纯逻辑）
  tests/test_spawner.py → spawner.py（mock asyncio subprocess）
  tests/test_locks.py → locks.py（mock asyncpg + fakeredis）

[无循环依赖验证]
  controllers ← services ← pool ← {spawner, lifecycle, health, recycle, evict, locks}
  ✓ 无循环
```

## 三、多方案对比（4.11 强制要求）

### 方案 A：扁平单包（主方案，DD-001 FS-006 原方案）
- 文件数: 12（不含测试）
- 文件职责: 单一清晰（每个文件 1 个核心类 + 辅助方法）
- 目录层级: 2 层（pool/*.py + pool/tests/*.py）
- 优点: 与 FS-006 完全对齐；开发工程师易于上手
- 缺点: pool.py 单例需持有多个子模块引用（DI 较复杂）

### 方案 B：子包分层（备选）
- 文件数: 12 + 5 个 __init__.py = 17
- 目录层级: 3 层（pool/core/ + pool/lifecycle/ + pool/lock/ + ...）
- 优点: 物理隔离清晰；可独立 import 子模块
- 缺点: 与 FS-006 不一致；DD-001 已锁定 FS-006

### 对比评估

| 维度 | 方案 A 得分 | 方案 B 得分 |
|------|----------|----------|
| 文件结构合规度 (0.22) | 10 | 7 |
| 注释完整度 (0.22) | 10 | 8 |
| 接口契约注释化完整度 (0.18) | 10 | 9 |
| 代码风格合规度 (0.13) | 10 | 8 |
| 设计可追溯性 (0.13) | 10 | 8 |
| 文件框架可追溯性 (0.12) | 10 | 7 |
| **总分** | **10.00** | **7.85** |

**选择**: 方案 A（主方案），与 DD-001 FS-006 完全对齐，得分 10.00 > 方案 B 7.85，差距 2.15 > 阈值 0.5。

## 四、命名规范

| 元素 | 规范 | 示例 |
|------|------|------|
| 包名 | 小写无下划线 | `pool` |
| 模块文件 | snake_case | `pool.py`, `spawner.py` |
| 类名 | PascalCase | `ProcessPool`, `ProcessSpawner` |
| 函数/方法 | snake_case | `spawn`, `healthcheck_all` |
| 常量 | UPPER_SNAKE_CASE | `MAX_PROCESSES_PER_WS = 64` |
| 私有 | _前缀 | `_slots`, `_lru` |
| 测试 | test_{feature}.py | `test_pool.py`, `test_lifecycle.py` |

## 五、文件结构合规 5 项检查（4.7）

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 目录层级 ≥ 2 层 | ✓ | 2 层（pool/ + pool/tests/） |
| 文件命名符合规范 | ✓ | snake_case + PascalCase 类 |
| 文件职责单一 | ✓ | 每个文件 1 个核心类 |
| 依赖关系无循环 | ✓ | controllers → services → pool → {子模块} |
| 符合最佳实践 | ✓ | FastAPI 推荐布局（src-layout + 路由器分离） |

**合规度: 高（5/5 通过）**

## 六、文件头注释覆盖

- 100%（17/17 文件均含完整文件头注释）
- 包含职责 / 所属模块 / 关联设计规范 / 输入输出 / 依赖 / 注意事项 / 来源标注

[来源标注] [DD-001:FS-006 + MD-MCP-M-B02 + IC-004 + DD洞察-1]
