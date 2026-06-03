# 文件框架结构 FF-M-B04-MCP-V1.0-20260603

> 模块: M-B04 Approval Engine
> 作者: DD-M-B04
> 来源: [DD-001:FS-008/MD:M-B04/IC-005/IC-006]
> 设计模式: Service Layer + Cache Proxy + Idempotency Token

---

## 1. 模块标识

| 项 | 值 |
|----|----|
| 模块编号 | M-B04 |
| 模块名称 | Approval Engine |
| 所属层级 | Layer 2 Application |
| 关联接口契约 | IC-005 (check_and_queue) / IC-006 (decide) |
| 关联设计规范 | FS-008 / MD:M-B04 / CS:Python §1 |
| 关联API | API-130 / API-131 |
| 关联 ADR | ADR-006 (hash 统一) / DDR-002 (Event Bus) |

---

## 2. 文件框架

```
src/agenthub/application/approval/         ← M-B04 根目录
├── __init__.py                            ← 模块初始化，导出 ApprovalService / ArgsHasher 公共接口
├── controllers.py                         ← FastAPI Router; HTTP 入口（IC-005/IC-006）
├── services.py                            ← ApprovalService 业务编排（check_and_queue / decide / timeout_scan）
├── hasher.py                              ← ArgsHasher 公共静态函数（ADR-006 单一来源）
├── allowlist.py                           ← AllowlistCache（Redis Cache Proxy + PG 兜底）
├── queue_repo.py                          ← InboxQueueRepository（Service Layer 与 M-D01 之间的适配）
├── schemas.py                             ← Pydantic DTO（CheckRequest / DecideRequest / Decision 等）
├── exceptions.py                          ← 模块领域异常（继承 AgentHubError）
├── scanner.py                             ← TimeoutScanner（arq 任务: pending 超时扫描）
└── tests/
    ├── __init__.py
    ├── test_controllers.py                ← 控制器层测试
    ├── test_services.py                   ← Service 业务测试（覆盖 35 用例核心）
    ├── test_hasher.py                     ← ArgsHasher 一致性/属性测试
    ├── test_allowlist.py                  ← Cache Proxy 命中/穿透/降级
    ├── test_queue_repo.py                 ← Repository 适配测试
    ├── test_scanner.py                    ← TimeoutScanner 触发测试
    └── conftest.py                        ← 模块级 fixture (fakeredis / pytest-asyncio)
```

**文件数总计**: 9 业务文件 + 7 测试文件 + 1 conftest = **17 文件**
（符合 soul 单模块文件数范围 [模块复杂度×2=8, ×5=20]）

---

## 3. 文件间依赖关系

```
controllers.py  →  services.py  →  allowlist.py  →  queue_repo.py
                       ↓                ↓                ↓
                   hasher.py     (Redis cache)    (M-D01 Repository)
                       ↓
                  schemas.py / exceptions.py
                       ↓
                  scanner.py     →  services.timeout_scan
                       ↓
              (arq worker enqueue)

外部依赖（仅声明，禁止跨模块写入）:
  ├── agenthub.core.logging          (横切日志)
  ├── agenthub.core.exceptions       (AgentHubError 基类)
  ├── agenthub.data.metadata         (M-D01: UnitOfWork + Repositories)
  ├── agenthub.data.cache            (M-D03: RedisClusterClient)
  └── agenthub.eventbus              (M-EV01: publish approval.requested/approval.decided)
```

**无循环依赖** ✓（DAG，检查通过）
**跨模块依赖均为只读引用** ✓（R28/R29 合规）

---

## 4. 设计模式落地

| 模式 | 落地文件 | 落地点 |
|------|---------|--------|
| Service Layer | services.py | ApprovalService 封装业务编排 |
| Cache Proxy | allowlist.py | AllowlistCache 包装 Repository + Redis |
| Idempotency Token | hasher.py + services.py | args_hash + (queue_id, decision_hash) UNIQUE |
| Repository | queue_repo.py | InboxQueueRepository 桥接 M-D01 |
| Pure Function | hasher.py | @staticmethod compute_args_hash（无 IO） |

---

## 5. 模块边界声明（D7=100 关键证据）

| 操作类型 | 路径范围 | 数量 |
|---------|---------|------|
| 创建文件 | `src/agenthub/application/approval/**` | 17 |
| 创建文件 | 其他模块 | **0** |
| 修改文件 | 任何模块 | **0** |
| 跨模块文件操作数 | — | **0** ✓ |

> 所有交付物路径均严格限定于 `产出物/07-文件框架/M-B04/`。

---

## 6. 来源标注汇总

- 文件清单 [DD-001:FS-008]
- 类设计 [DD-001:MD:M-B04]
- 函数签名 [DD-001:IC-005/IC-006]
- 设计模式 [DD-001:MD:M-B04 模式字段]
- 命名规范 [DD-001:CS §1.1/1.5]
- 异常基类 [DD-001:CS §1.6]
- 测试规范 [DD-001:CS §1.7]
- scanner.py 拆分 [DD-M-B04 推断: MD 中提及 timeout_scan 但未单独拆文件，按 SRP 拆出 arq 入口]
- schemas.py 单独拆分 [DD-M-B04 推断: FS-008 未列出但 IC-005/006 入出参丰富，Pydantic 集中放置利于复用]
- exceptions.py 单独拆分 [DD-M-B04 推断: CS §1.6 要求自定义异常基类，模块级集中定义便于跨文件 import]
