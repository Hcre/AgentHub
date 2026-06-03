# 文件框架结构 FF-M-A02-MCP-V1.0-20260602

> 模块：M-A02 WS Event Gateway
> 设计模式：Observer + Adapter
> 来源：[DD-001:FS-002/MD-M-A02/IC-002] + [DD-M推断:依M-A02职责细化]

---

## 一、模块边界声明

```
[负责模块] M-A02 WS Event Gateway
[负责实例] DD-M-A02（agent-dd-module-designer-a02）
[模块边界]
  ✓ 仅创建/修改 产出物/07-文件框架/M-A02/ 目录内文件
  ✗ 禁止触碰其他 21 个模块的任何文件（M-A01/M-A03/M-A04/M-Bxx/M-Cxx/M-Dxx/M-EV01）
  ✗ 禁止触碰 产出物/07-文件框架/ 下其他模块子目录
  ✗ 禁止触碰 产出物/06-详细设计/、产出物/01~05-*/ 等上游/横向产物
[跨模块依赖声明]
  ↑ 依赖 M-D03（Cache & Queue / Redis Stream）—— 通过接口调用，本 DD-M 不创建 M-D03 文件
  ↑ 依赖 M-EV01（Event Bus）—— 通过 bus.subscribe 接口，本 DD-M 不创建 M-EV01 文件
  ↑ 依赖 M-D01（Metadata Store，PG DE-013 订阅持久化）—— 通过 Repository，本 DD-M 不创建 M-D01 文件
  ↓ 被 M-A01（API Gateway）路由 / 任何业务模块推送事件引用
```

## 二、文件框架目录树

```
产出物/07-文件框架/M-A02/
├── FF-M-A02-MCP-V1.0-20260602.md            ← [本文件] 文件框架结构
├── API-M-A02-MCP-V1.0-20260602.md            ← 接口注释清单
├── FC-M-A02-MCP-V1.0-20260602.md            ← 文件结构合规报告
├── FDR-M-A02-MCP-V1.0-20260602.md            ← 框架决策记录
├── FH-M-A02-MCP-V1.0-20260602.md            ← 文件框架健康度仪表盘
└── src/
    └── agenthub/
        └── access/
            └── ws_gateway/                   ← M-A02 模块源码路径
                ├── __init__.py               ← [职责：模块初始化，导出公共符号]
                ├── server.py                 ← [职责：WSServer (socketio.AsyncServer) 入口]
                ├── handlers/
                │   ├── __init__.py
                │   ├── connect.py            ← [职责：connect/disconnect 处理器 + JWT 鉴权]
                │   ├── subscribe.py          ← [职责：subscribe/unsubscribe + ACL 校验]
                │   └── ping.py               ← [职责：心跳与 ping_timeout 处理]
                ├── subscription_store.py     ← [职责：SubscriptionStore（PG + Redis hash 持久化）]
                ├── offline_queue.py          ← [职责：OfflineQueue（Redis Stream 离线缓冲）]
                ├── bus_listener.py           ← [职责：BusListener（Event Bus → WS 转推 Observer）]
                ├── models.py                 ← [职责：DTO 与领域模型（SubscribeRequest/EventEnvelope）]
                ├── exceptions.py             ← [职责：WS 网关域异常（AuthError/ACLError/RedisConnError）]
                └── tests/
                    ├── __init__.py
                    ├── conftest.py            ← [职责：fixture 集中（fakeredis stream/socketio test_client）]
                    ├── test_server.py         ← [职责：server 集成测试（多客户端重连）]
                    ├── test_handlers_connect.py
                    ├── test_handlers_subscribe.py
                    ├── test_handlers_ping.py
                    ├── test_subscription_store.py
                    ├── test_offline_queue.py
                    └── test_bus_listener.py
```

## 三、文件清单与职责

| 序号 | 文件路径 | 职责 | 关联类/函数 | 关联设计规范 | 来源标注 |
|------|---------|------|------------|------------|---------|
| 1 | `src/agenthub/access/ws_gateway/__init__.py` | 模块初始化，导出 WSServer / SubscriptionStore / OfflineQueue / BusListener | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 2 | `src/agenthub/access/ws_gateway/server.py` | WSServer(socketio.AsyncServer) 启动入口，连接/断开/订阅/退订注册 | WSServer, register_handlers | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 3 | `src/agenthub/access/ws_gateway/handlers/connect.py` | connect/disconnect 事件，JWT 校验、sid 绑定 agent_id、ping_timeout | on_connect, on_disconnect, _authenticate | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 4 | `src/agenthub/access/ws_gateway/handlers/subscribe.py` | subscribe/unsubscribe 事件，ACL 校验 + 持久化 + 触发回放 | on_subscribe, on_unsubscribe, _check_acl | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 5 | `src/agenthub/access/ws_gateway/handlers/ping.py` | 心跳 ping/pong、ping_timeout 30s 状态机驱动 | on_ping, on_pong, mark_timeout | MD-M-A02 | [DD-001:MD-M-A02] |
| 6 | `src/agenthub/access/ws_gateway/subscription_store.py` | 订阅持久化：PG DE-013 主存 + Redis hash 加速查询 | SubscriptionStore, add, remove, list_topics, list_subscribers | MD-M-A02 | [DD-001:MD-M-A02] |
| 7 | `src/agenthub/access/ws_gateway/offline_queue.py` | Redis Stream 离线缓冲：push/pull by client_id | OfflineQueue, push, pull, replay_missed | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 8 | `src/agenthub/access/ws_gateway/bus_listener.py` | 订阅 AG-022 Event Bus 全部 topic，按订阅关系转推 WS | BusListener, subscribe_all_topics, on_event, _dispatch | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 9 | `src/agenthub/access/ws_gateway/models.py` | DTO / Value Object：SubscribeRequest / EventEnvelope / WSMessage | SubscribeRequest, EventEnvelope, WSMessage, ConnectionState | MD-M-A02 | [DD-001:MD-M-A02] |
| 10 | `src/agenthub/access/ws_gateway/exceptions.py` | WS 网关域异常（继承 AgentHubError） | AuthError, ACLError, RedisConnectionError, PushFailedError | MD-M-A02 | [DD-001:MD-M-A02] |
| 11 | `src/agenthub/access/ws_gateway/tests/conftest.py` | 共享 fixture（fakeredis stream / socketio test_client / agent JWT） | event_loop, fakeredis_stream, ws_test_client, jwt_factory | MD-M-A02 | [DD-M推断:为单元/集成测试提供共享 fixture] |
| 12 | `src/agenthub/access/ws_gateway/tests/test_server.py` | server 集成测试 | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 13 | `src/agenthub/access/ws_gateway/tests/test_handlers_connect.py` | connect 鉴权测试 | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 14 | `src/agenthub/access/ws_gateway/tests/test_handlers_subscribe.py` | subscribe ACL/持久化测试 | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 15 | `src/agenthub/access/ws_gateway/tests/test_handlers_ping.py` | ping/pong/ping_timeout 测试 | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 16 | `src/agenthub/access/ws_gateway/tests/test_subscription_store.py` | 订阅存储单元测试 | — | MD-M-A02 | [DD-001:MD-M-A02] |
| 17 | `src/agenthub/access/ws_gateway/tests/test_offline_queue.py` | 离线队列 Redis Stream 测试 | — | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |
| 18 | `src/agenthub/access/ws_gateway/tests/test_bus_listener.py` | Event Bus 转推 WS Observer 测试 | — | MD-M-A02 + IC-002 | [DD-001:MD-M-A02/IC-002] |

**文件数：18**（符合 FS-002 规范的 7 个源码 + 7 个测试 + 4 个辅助文件；模块复杂度估算为「中等」，文件数处于 [复杂度×2, 复杂度×5] 范围内）

## 四、文件依赖关系

```
                    ┌──────────────────────┐
                    │   server.py          │ ← 启动入口、handler 注册
                    │   (WSServer)         │
                    └──────┬───────────────┘
                           │ 注册
              ┌────────────┼────────────┐
              ▼            ▼            ▼
       ┌──────────┐ ┌──────────┐ ┌──────────┐
       │ handlers/│ │ handlers/│ │ handlers/│
       │ connect  │ │subscribe │ │   ping   │
       └────┬─────┘ └────┬─────┘ └──────────┘
            │            │
            │   ┌────────┴─────────┐
            ▼   ▼                  ▼
   ┌──────────────────┐   ┌─────────────────┐
   │ subscription_    │   │ offline_queue   │
   │ store.py         │   │ .py             │
   │ (PG+Redis hash)  │   │ (Redis Stream)  │
   └────────┬─────────┘   └────────┬────────┘
            │                      │
            ▼                      ▼
   ┌─────────────────────────────────────────┐
   │        M-D03 Cache & Queue              │ ← 跨模块（仅通过接口调用，不直接依赖实现）
   └─────────────────────────────────────────┘

   ┌──────────────────┐
   │ bus_listener.py  │ ← 订阅 Event Bus
   │ (Observer)       │
   └────────┬─────────┘
            ▼
   ┌─────────────────────────────────────────┐
   │        M-EV01 Event Bus                 │ ← 跨模块
   └─────────────────────────────────────────┘

   所有文件共同依赖：
     - agenthub.core.exceptions  (M-Core)
     - agenthub.core.logging     (M-Core)
     - agenthub.core.config      (M-Core)
     - agenthub.data.cache.client (M-D03)
```

**依赖规则：**
- 严格分层：server → handlers → store/offline → M-D03
- 无循环依赖
- 跨模块调用仅通过接口（`agenthub.data.cache`、`agenthub.eventbus`），禁止反向依赖
- `bus_listener.py` 不依赖 `handlers/`，而是直接调用 `WSServer.emit`（Observer 模式：观察 Event Bus 事件，分发给已订阅客户端）

## 五、子模块与 MD-M-A02 对应

| FS-002 子模块 | DD-M-A02 物理文件 | 类归属 | 备注 |
|--------------|------------------|--------|------|
| ws_server/ | server.py | WSServer | 启动入口 |
| ws_server/ | handlers/connect.py, handlers/ping.py | （事件处理函数） | 拆分为独立文件便于测试 |
| subscription/ | subscription_store.py | SubscriptionStore | PG DE-013 + Redis hash |
| offline/ | offline_queue.py | OfflineQueue | Redis Stream |
| bus_adapter/ | bus_listener.py | BusListener | Observer 模式 |
| （公共） | models.py, exceptions.py, __init__.py | DTO + 域异常 | [DD-M推断:为遵循「单一职责」，从 MD 抽离] |

## 六、与上游文档的对齐

| 上游文档 | 引用内容 | 本框架落实 |
|---------|---------|-----------|
| FS-002 (DD-001) | 7 个源码文件结构 | 物理 10 个文件（含 __init__/models/exceptions）—— [DD-M推断:增加 models.py 与 exceptions.py 以满足 5 项合规检查] |
| MD-M-A02 (DD-001) | 4 类、3 函数签名、状态机、异常、日志、测试 | 每个类/函数均有对应文件 + 注释覆盖 |
| IC-002 (DD-001) | ws.event_gateway 接口契约 | server.py + handlers/ + offline_queue.py 体现 |
| CS-MCP §1 (DD-001) | Python 风格 | 所有文件遵循 snake_case / Google docstring / 4 空格 / 类型注解 |

## 七、方案对比（多方案对比 4.11）

**主方案 A（倾向）：** FS-002 规定的 7 源码文件 + 拆分 handlers 子包 + 增加 models/exceptions/conftest（DD-M 推断）
**备选方案 B：** 将 handlers/ 合并入 server.py 单文件，节省 3 个文件

| 对比维度 | 权重 | 方案A 得分 | 方案B 得分 |
|---------|------|-----------|-----------|
| 文件结构合规度 | 0.22 | 9（5/5 项检查通过） | 7（handlers 单文件 > 300 行违反 R24 职责模糊） |
| 注释完整度 | 0.22 | 10（每个 handler 独立注释） | 6（合并后单文件注释难以导航） |
| 接口契约注释化完整度 | 0.18 | 9 | 8 |
| 代码风格合规度 | 0.13 | 9 | 7（违反 CS §1.4 文件头 docstring 必须） |
| 设计可追溯性 | 0.13 | 10 | 6（合并后无法单独追溯 connect/subscribe/ping 设计） |
| 文件框架可追溯性 | 0.12 | 9 | 6 |
| **加权总分** | — | **9.27** | **6.79** |

**选择：** 方案A（差距 2.48 ≥ 5？不，2.48 < 5 → 标注差异）—— 方案A 在测试隔离和职责单一性上显著优于方案B，尤其 handlers/ 拆分对 sticky session 重连场景测试至关重要；故选 A。

**文件框架结构文档结束。**
