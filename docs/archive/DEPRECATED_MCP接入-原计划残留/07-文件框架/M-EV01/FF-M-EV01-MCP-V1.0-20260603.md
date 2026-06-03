# M-EV01 文件框架结构 FF-M-EV01-MCP-V1.0-20260603

> 框架轮次 1/4；F2 文件结构创建完成
> [DD-001:FS-022 + MD-MCP-V1.0-M-EV01]

---

## [模块编号] M-EV01
## [模块名称] Event Bus

## [文件框架]

```
src/agenthub/eventbus/
├── __init__.py            ← 职责：模块初始化 + 公共导出（5 topic 枚举 + 公共类）
├── bus.py                 ← 职责：EventBus 核心（publish/subscribe 双模式入口）
├── stream_consumer.py     ← 职责：StreamConsumer 关键 topic 消费者（含 DLQ）
├── registry.py            ← 职责：TopicRegistry（5 topic + Schema 校验）
├── schemas/               ← 职责：5 topic JSON Schema（Draft 2020-12）
│   ├── __init__.py        ← 职责：schemas 包导出
│   ├── approval.py        ← 职责：approval.* 事件 schema
│   ├── template.py        ← 职责：template.* 事件 schema
│   ├── process.py         ← 职责：process.* 事件 schema
│   ├── mcp.py             ← 职责：mcp.* 事件 schema
│   └── binding.py         ← 职责：binding.* 事件 schema
└── tests/                 ← 职责：单元测试
    ├── __init__.py
    ├── test_bus.py        ← 职责：EventBus publish/subscribe 测试（28 用例）
    └── test_registry.py   ← 职责：TopicRegistry 注册/校验测试
```

## [文件间依赖关系]
```
bus.py → registry.py → schemas/*
bus.py → stream_consumer.py
stream_consumer.py → bus.py（仅类型引用）
__init__.py → bus.py / stream_consumer.py / registry.py / schemas/*
tests/ → bus.py / registry.py / stream_consumer.py
```

## [跨模块调用方（仅声明，不写代码）]
- M-A02 ws_gateway.bus_listener → EventBus.subscribe
- M-B02 pool.services → EventBus.publish(process.spawned)
- M-B04 approval.services → EventBus.publish(approval.*)
- M-B05 create.orchestrator → EventBus.publish(mcp.*)
- M-B03 binding.services → EventBus.publish(binding.*)

## [文件结构合规检查 5 项]
| 检查项 | 通过 | 依据 |
|--------|-----|------|
| 目录层级 ≥ 2 层 | ✓ | eventbus/ + schemas/ + tests/ = 3 层 |
| 文件命名 snake_case | ✓ | bus.py / registry.py / stream_consumer.py |
| 文件职责单一 | ✓ | 每个文件 1 个核心职责 |
| 依赖无循环 | ✓ | bus→registry→schemas 单向；stream_consumer 类型引用 |
| 符合最佳实践 | ✓ | Python src-layout + 包内 __init__.py |

## [主方案 vs 备选方案对比]
| 维度 | 方案A（主）| 方案B（备）|
|------|-----------|-----------|
| 文件结构合规度 (0.22) | 9 | 7 |
| 注释完整度 (0.22) | 9 | 7 |
| 接口契约注释化 (0.18) | 10 | 8 |
| 代码风格合规 (0.13) | 9 | 8 |
| 设计可追溯 (0.13) | 10 | 8 |
| 文件框架可追溯 (0.12) | 10 | 8 |
| **总分** | **9.43** | **7.59** |

**选择：方案A**（schemas 按 topic 拆 5 文件 vs 方案B 单文件 schemas.py）—— 拆文件利于跨团队并行维护 + 减小 merge 冲突。

## [DD-M洞察-1]
EventBus 同时被 6 个模块依赖（M-A02/M-B02/M-B03/M-B04/M-B05/M-D02），必须严格控制 __all__ 导出面；建议在 __init__.py 中仅暴露高频公共类型（5 类 + 1 注册表），内部 StreamConsumer 与 Schema 类改为直接 import 路径引用，避免循环导入与版本耦合。

## [阶梯退出检查]
- ①目录已创建: 是
- ②文件已创建: 是
- ③命名合规: 是
- ④D2 达成率: 100%

## [来源标注] [DD-001:FS-022 + MD-MCP-V1.0-M-EV01]
