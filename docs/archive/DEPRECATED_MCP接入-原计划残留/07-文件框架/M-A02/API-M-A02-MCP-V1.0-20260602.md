# 接口注释清单 API-M-A02-MCP-V1.0-20260602

> 模块：M-A02 WS Event Gateway
> 关联契约：IC-002 (ws.event_gateway / API-010)
> 来源：[DD-001:IC-002] + [DD-M推断:依 M-A02 内部函数补全]

---

## 接口总览

| 接口编号 | 关联契约 | 函数签名 | 实现文件 | 状态 |
|---------|---------|---------|---------|------|
| IC-002 | ws.event_gateway | WSServer.start / emit | server.py | 已注释 |
| IC-002 | on_subscribe | async def on_subscribe(sid, data) | handlers/subscribe.py | 已注释 |
| IC-002 | on_unsubscribe | async def on_unsubscribe(sid, data) | handlers/subscribe.py | 已注释 |
| IC-002 | push_event | async def OfflineQueue.push(client_id, event) | offline_queue.py | 已注释 |
| IC-002 | replay_missed | async def OfflineQueue.replay_missed(client_id, since) | offline_queue.py | 已注释 |
| IC-002 (子) | on_connect | async def on_connect(sid, environ, auth) | handlers/connect.py | 已注释 |
| IC-002 (子) | on_disconnect | async def on_disconnect(sid) | handlers/connect.py | 已注释 |
| IC-002 (子) | verify_jwt | async def _authenticate(token, expected_agent_id, settings) | handlers/connect.py | 已注释 |
| IC-002 (子) | add (subscription) | async def SubscriptionStore.add(client_id, topic, agent_id) | subscription_store.py | 已注释 |
| IC-002 (子) | remove (subscription) | async def SubscriptionStore.remove(client_id, topic) | subscription_store.py | 已注释 |
| IC-002 (子) | list_topics | async def SubscriptionStore.list_topics(client_id) | subscription_store.py | 已注释 |
| IC-002 (子) | subscribe_all_topics | async def BusListener.subscribe_all_topics() | bus_listener.py | 已注释 |
| IC-002 (子) | on_event (bus) | async def BusListener.on_event(topic, payload) | bus_listener.py | 已注释 |

**接口契约注释化覆盖率：100%**（DD-001 定义的 IC-002 全部 5 个出/入参函数 + 8 个内部支撑函数均含完整函数签名注释）

---

## IC-002 详细函数签名注释

### IC-002 / WSServer.start

```python
async def start(self, host: str, port: int) -> None:
    """[函数名] start
    [职责] 启动 socketio 服务并注册 handler
    [关联接口契约] IC-002 ws.event_gateway
    [参数说明]
      host: str 必填 绑定地址（如 "0.0.0.0"）
      port: int 必填 监听端口（建议 8001，nginx sticky upstream）
    [前置条件] register_handlers 已调用
    [后置条件] 监听 host:port
    [性能约束] 启动 < 5s
    [来源标注] [DD-001:IC-002 接口描述]
    """
```

### IC-002 / on_subscribe

```python
async def on_subscribe(sid: str, data: dict) -> None:
    """[函数名] on_subscribe
    [职责] 处理客户端 subscribe 请求
    [关联接口契约] IC-002 msg.action=subscribe
    [参数说明]
      sid: str 必填 socketio 会话 ID
      data: dict 必填 SubscribeRequest JSON（{action, agent_id, topics}）
    [错误码]
      1008 - 越权订阅（ACLError）
    [前置条件] sid 已 on_connect 成功
    [后置条件] 订阅持久化 + 触发 replay_missed
    [幂等性] 是
    [性能约束] P95 ≤ 50ms
    [来源标注] [DD-001:MD-M-A02 on_subscribe + IC-002]
    """
```

### IC-002 / push_event

```python
async def push(self, client_id: str, event: EventEnvelope) -> bool:
    """[函数名] push
    [职责] 客户端离线时入队
    [关联接口契约] IC-002 push_event
    [参数说明]
      client_id: str 必填
      event: EventEnvelope 必填
    [返回值]
      类型: bool
      描述: True=入队；False=容量截断
    [后置条件] Stream 新增一项
    [性能约束] XADD < 5ms
    [来源标注] [DD-001:MD-M-A02 push_event + IC-002]
    """
```

### IC-002 / replay_missed

```python
async def replay_missed(self, client_id: str, since: str) -> int:
    """[函数名] replay_missed
    [职责] 客户端重连后回放离线事件
    [关联接口契约] IC-002 replay_missed
    [参数说明]
      client_id: str 必填
      since: str 必填 Redis Stream ID
    [返回值]
      类型: int
      描述: 实际回放数量
    [幂等性] 重复调用同 since 返回 0
    [性能约束] 100 事件 < 50ms
    [来源标注] [DD-001:MD-M-A02 replay_missed + IC-002]
    """
```

### 内部子接口（支撑 IC-002）

```python
# handlers/connect.py
async def on_connect(sid: str, environ: dict, auth: dict | None) -> bool:
    """[关联接口契约] IC-002 时序图 upgrade + auth"""

async def on_disconnect(sid: str) -> None:
    """[关联接口契约] IC-002 断线重连"""

async def _authenticate(token: str, expected_agent_id: str, settings: Settings) -> dict:
    """[关联接口契约] IC-002 鉴权 + SEC-008"""

# handlers/subscribe.py
async def on_unsubscribe(sid: str, data: dict) -> None:
    """[关联接口契约] IC-002 msg.action=unsubscribe"""

async def _check_acl(agent_id: str, topics: list[str]) -> None:
    """[关联接口契约] IC-002 1008"""

# subscription_store.py
async def add(self, client_id: str, topic: str, agent_id: UUID) -> None:
    """[关联接口契约] IC-002 订阅持久化"""

async def remove(self, client_id: str, topic: str) -> None:
    """[关联接口契约] IC-002 退订清理"""

async def list_topics(self, client_id: str) -> list[str]:
    """[关联接口契约] IC-002 订阅查询"""

# bus_listener.py
async def subscribe_all_topics(self) -> None:
    """[关联接口契约] IC-002 EventBus → WSGateway"""

async def on_event(self, topic: str, payload: dict) -> None:
    """[关联接口契约] IC-002 EventBus: event"""
```

---

## 与 IC-002 错误码的对应

| IC-002 错误码 | 含义 | 抛出位置 | 处理 |
|--------------|------|---------|------|
| 4401 | 认证失败 | handlers/connect.py: _authenticate | socketio 关闭 4401 |
| 1008 | 越权订阅 | handlers/subscribe.py: _check_acl | socketio 关闭 1008 |
| 1011 | 服务端错误 | server.py / bus_listener.py | 客户端重连 |
| PUSH_FAILED | 推送失败 | bus_listener.py: _dispatch | 兜底 OfflineQueue.push |
| REDIS_CONN_FAILED | Redis 不可用 | subscription_store.py / offline_queue.py | 内存兜底 + 告警 |

**接口注释清单文档结束。**
