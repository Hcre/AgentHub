# 框架决策记录 FDR-M-A02-MCP-V1.0-20260602

> 模块：M-A02 WS Event Gateway
> 来源：[DD-M推断:依 M-A02 职责细化推断]

---

## FDR-A02-001 handlers 子包拆分 vs 单文件

```
[决策编号] FDR-A02-001
[决策标题] handlers 拆分为 connect/subscribe/ping 三文件
[决策状态] 已接受
[决策内容] 将 MD-M-A02 提及的 on_connect / on_subscribe / ping 事件处理拆分为 handlers/{connect,subscribe,ping}.py 三独立文件
[决策理由]
  1. 单文件 > 300 行违反 R24「文件职责模糊」
  2. handlers 拆分便于按事件类型单独 mock 单元测试（MD-M-A02 §测试策略 18 用例）
  3. sticky session 重连场景测试需要独立 patch connect/subscribe，不拆分无法隔离
[拒绝的替代方案]
  方案A: 合并为 handlers.py 单文件 → 拒绝（理由：违反 R24，且 handlers 内不同事件共享 fixture 会导致 mock 污染）
  方案B: 进一步拆分为 connect/subscribe/ping + acl_check.py → 拒绝（理由：acl_check 内联到 subscribe 即可，过度拆分违反 R14）
[影响范围] handlers/ 子包 + 3 个 test_*.py 文件
[相关FDR] 无
[来源标注] [DD-M推断:依 MD-M-A02 测试策略「单元 + 集成（多客户端订阅）」细化]
```

## FDR-A02-002 引入 models.py 与 exceptions.py

```
[决策编号] FDR-A02-002
[决策标题] 独立 models.py 与 exceptions.py 文件
[决策状态] 已接受
[决策内容] 在 FS-002 基础上增加 models.py（DTO/VO）与 exceptions.py（域异常），作为支撑文件
[决策理由]
  1. 4 项合规检查要求文件职责单一；models 与 handler 业务分离
  2. 域异常统一继承 AgentHubError（CS-MCP §1.6）+ 携带上下文参数便于审计（client_id, topic）
  3. SubscribeRequest 强类型校验替代 dict 传参，避免 handler 内反复手动校验
[拒绝的替代方案]
  方案A: DTO 内联到 server.py → 拒绝（理由：server 是入口，不应承担 DTO 定义）
  方案B: 异常散落在各 handler → 拒绝（理由：违反「异常统一基类」CS-MCP §1.6 + R24）
[影响范围] models.py, exceptions.py, 4 个 handler + 1 个 server
[相关FDR] FDR-A02-001
[来源标注] [DD-M推断:为满足 R24 职责单一 + CS-MCP §1.6 异常规范]
```

## FDR-A02-003 BusListener 与 handlers 解耦

```
[决策编号] FDR-A02-003
[决策标题] BusListener 直接调用 WSServer.emit，不经 handlers
[决策状态] 已接受
[决策内容] BusListener 推送路径：on_event → _dispatch → WSServer.emit(room) → socketio；不经 handlers
[决策理由]
  1. handlers 处理 client → server 方向；BusListener 处理 server → client 方向；方向不同，不复用 handler
  2. Observer 模式解耦：Event Bus 事件类型 ≠ 客户端订阅的 action 类型
  3. 推送失败时 _dispatch 内 try/except 兜底 OfflineQueue.push（MD-M-A02 §异常处理）
[拒绝的替代方案]
  方案A: BusListener 也走 on_event handler → 拒绝（理由：handler 假定 client 主动发消息，方向不匹配）
  方案B: BusListener 直连 socketio 不经 WSServer.emit → 拒绝（理由：违反单一封装入口原则，且 WSServer.emit 含统一异常处理）
[影响范围] bus_listener.py, server.py（emit 方法）
[相关FDR] 无
[来源标注] [DD-001:MD-M-A02 类设计 BusListener + MD §设计模式 Observer]
```

## FDR-A02-004 测试文件按 handler 维度拆分

```
[决策编号] FDR-A02-004
[决策标题] tests/ 按 handler 拆分为 test_handlers_{connect,subscribe,ping}.py
[决策状态] 已接受
[决策内容] 测试文件按被测单元拆分：test_server.py（集成）+ test_handlers_*.py（单 handler）+ test_subscription_store.py / test_offline_queue.py / test_bus_listener.py（子模块单元）
[决策理由]
  1. CS-MCP §1.7 要求 AAA 模式 + test_{function}_when_{scenario}_then_{expected} 命名；按单元拆分避免单文件超长
  2. MD-M-A02 §测试策略 18 用例已按事件类型分组
  3. 与 handlers/ 拆分一一对应，便于定位测试
[拒绝的替代方案]
  方案A: 合并为 test_ws_gateway.py → 拒绝（理由：单文件 > 500 行违反 R24）
  方案B: 进一步按函数拆分 test_on_connect.py 等 → 拒绝（理由：过度拆分违反 R14，且 1 个文件 1 个函数难维护）
[影响范围] tests/ 子包
[相关FDR] FDR-A02-001
[来源标注] [DD-001:MD-M-A02 §测试策略 + CS-MCP §1.7]
```

## FDR-A02-005 conftest.py 集中 fixture

```
[决策编号] FDR-A02-005
[决策标题] conftest.py 集中 fakeredis / socketio test_client / jwt_factory 等 fixture
[决策状态] 已接受
[决策内容] 将 4 类共享 fixture（event_loop / fakeredis_stream / ws_test_client / jwt_factory）集中在 conftest.py
[决策理由]
  1. CS-MCP §1.7 「Fixture 仅放 conftest.py」
  2. 6 个 test_*.py 共享 4 类 fixture，集中后减少重复代码
  3. pytest 自动发现 conftest.py
[拒绝的替代方案]
  方案A: 各 test 文件自带 fixture → 拒绝（理由：违反 CS-MCP §1.7）
  方案B: 集中到顶层 conftest.py → 拒绝（理由：本模块自给自足，跨模块 fixture 归上层 conftest）
[影响范围] tests/conftest.py
[相关FDR] 无
[来源标注] [DD-M推断:依 CS-MCP §1.7 约定]
```

## FDR-A02-006 跨模块依赖通过接口调用，禁止反向依赖

```
[决策编号] FDR-A02-006
[决策标题] M-A02 仅通过接口调用 M-D03 / M-EV01 / M-D01，禁止反向依赖
[决策状态] 已接受
[决策内容] subscription_store / offline_queue / bus_listener 通过 import 跨模块接口（RedisClusterClient / EventBus / SubscriptionRepository）调用，不创建这些模块的实现文件
[决策理由]
  1. R28 禁止跨模块操作；本 DD-M-A02 仅负责 M-A02
  2. 跨模块调用通过接口（IC-019 / IC-020 / IC-017）约束
  3. 注释中必须标注跨模块依赖关系（[DD-M洞察:跨模块依赖未标注] 风险）
[拒绝的替代方案]
  方案A: 在 M-A02 内复制 Redis / Event Bus 实现 → 拒绝（理由：违反 R28 + 重复造轮子）
[影响范围] subscription_store.py / offline_queue.py / bus_listener.py（仅 type hint + docstring 引用，不实例化）
[相关FDR] 无
[来源标注] [DD-M推断:依 soul R28 模块边界硬约束 + [DD-M洞察:跨模块依赖未标注] 类型]
```

---

**框架决策记录文档结束（共 6 项决策）**
